import ast
import sqlite3
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
repo = root / "data/httpx"
database = root / "indexes/code.sqlite"

commit = subprocess.check_output(
    ["git", "-C", str(repo), "rev-parse", "HEAD"],
    text=True,
).strip()

records = []

for path in sorted((repo / "httpx").rglob("*.py")):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    relative_path = str(path.relative_to(repo))

    def add(symbol, node):
        body = ast.get_source_segment(source, node)
        if body:
            records.append((
                symbol, body, relative_path,
                node.lineno, node.end_lineno, commit,
            ))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node.name, node)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(f"{node.name}.{child.name}", child)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    add(target.id, node)

database.parent.mkdir(exist_ok=True)
with sqlite3.connect(database) as connection:
    connection.execute("DROP TABLE IF EXISTS code")
    connection.execute("""
    CREATE VIRTUAL TABLE code USING fts5(
        symbol, body,
        path UNINDEXED,
        start_line UNINDEXED,
        end_line UNINDEXED,
        commit_sha UNINDEXED
    )
    """)
    connection.executemany(
        "INSERT INTO code VALUES (?, ?, ?, ?, ?, ?)",
        records,
    )

print(f"Indexed {len(records)} code records from {commit[:7]}")