"""Build three independent FTS5 indexes from pinned Pluggy source data."""

import ast
import re
import sqlite3
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT / "data/pluggy"
INDEXES = ROOT / "indexes"


def source_commit():
    return subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
    ).strip()


def rst_sections(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    headings = []
    adornments = set("=-~^\"`:+*#")
    for index in range(len(lines) - 1):
        title = lines[index].strip()
        underline = lines[index + 1].strip()
        if (title and underline and len(set(underline)) == 1
                and underline[0] in adornments
                and len(underline) >= len(title)):
            headings.append((index, title))
    for number, (first, title) in enumerate(headings):
        last = (headings[number + 1][0] - 1
                if number + 1 < len(headings) else len(lines) - 1)
        while last > first and not lines[last].strip():
            last -= 1
        if re.fullmatch(r"\.\. _[^:]+:", lines[last].strip()):
            last -= 1
            while last > first and not lines[last].strip():
                last -= 1
        yield (title, "\n".join(lines[first:last + 1]),
               path.relative_to(REPO).as_posix(), first + 1, last + 1)


def python_symbols(path, tests=False):
    lines = path.read_text(encoding="utf-8").splitlines()
    tree = ast.parse("\n".join(lines), filename=str(path))
    relative = path.relative_to(REPO).as_posix()
    prefix = path.stem

    def record(node, symbol):
        return (symbol, "\n".join(lines[node.lineno - 1:node.end_lineno]),
                relative, node.lineno, node.end_lineno)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not tests or node.name.startswith("test_"):
                yield record(node, node.name if tests else f"{prefix}.{node.name}")
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not tests or member.name.startswith("test_"):
                        name = f"{node.name}.{member.name}"
                        yield record(member, name if tests else f"{prefix}.{name}")


def write_index(filename, table, label, records, commit):
    database = INDEXES / filename
    with sqlite3.connect(database) as connection:
        connection.execute(f"DROP TABLE IF EXISTS {table}")
        connection.execute(f"""
            CREATE VIRTUAL TABLE {table} USING fts5(
                {label}, body,
                path UNINDEXED,
                start_line UNINDEXED,
                end_line UNINDEXED,
                commit_sha UNINDEXED
            )
        """)
        connection.executemany(
            f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)",
            [(*record, commit) for record in records],
        )
    print(f"Indexed {len(records)} Pluggy {table} records from {commit[:7]}")


def main():
    commit = source_commit()
    INDEXES.mkdir(exist_ok=True)
    docs = list(rst_sections(REPO / "docs/index.rst"))
    code = [record for path in sorted((REPO / "src/pluggy").glob("*.py"))
            for record in python_symbols(path)]
    tests = [record for path in sorted((REPO / "testing").glob("test_*.py"))
             for record in python_symbols(path, tests=True)]
    write_index("pluggy_requirements.sqlite", "requirements", "heading", docs,
                commit)
    write_index("pluggy_code.sqlite", "code", "symbol", code, commit)
    write_index("pluggy_tests.sqlite", "tests", "name", tests, commit)


if __name__ == "__main__":
    main()
