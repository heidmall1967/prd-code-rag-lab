import ast
import sqlite3
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
repo = root / "data/httpx"
database = root / "indexes/tests.sqlite"

commit = subprocess.check_output(
    ["git", "-C", str(repo), "rev-parse", "HEAD"],
    text=True,
).strip()

records = []

for path in sorted((repo / "tests").rglob("test_*.py")):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    relative_path = str(path.relative_to(repo))

    def add(name, node):
        body = ast.get_source_segment(source, node)
        if body:
            records.append((
                name, body, relative_path,
                node.lineno, node.end_lineno, commit,
            ))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                add(node.name, node)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if (
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name.startswith("test_")
                ):
                    add(f"{node.name}.{child.name}", child)

database.parent.mkdir(exist_ok=True)
with sqlite3.connect(database) as connection:
    connection.execute("DROP TABLE IF EXISTS tests")
    connection.execute("""
        CREATE VIRTUAL TABLE tests USING fts5(
            name, body,
            path UNINDEXED,
            start_line UNINDEXED,
            end_line UNINDEXED,
            commit_sha UNINDEXED
        )
    """)
    connection.executemany(
        "INSERT INTO tests VALUES (?, ?, ?, ?, ?, ?)",
        records,
    )

print(f"Indexed {len(records)} test records from {commit[:7]}")
