import re
import sqlite3
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
repo = root / "data/httpx"
relative_path = "docs/advanced/timeouts.md"
document = repo / relative_path
database = root / "indexes/requirements.sqlite"

commit = subprocess.check_output(
    ["git", "-C", str(repo), "rev-parse", "HEAD"],
    text=True,
).strip()

lines = document.read_text(encoding="utf-8").splitlines()
sections = []
heading = "Introduction"
start = 1

for number, line in enumerate(lines, start=1):
    if re.match(r"^#{1,6} ", line):
        body = "\n".join(lines[start - 1:number - 1]).strip()
        if body:
            sections.append((heading, body, start, number - 1))
        heading = line.lstrip("# ").strip()
        start = number

body = "\n".join(lines[start - 1:]).strip()
if body:
    sections.append((heading, body, start, len(lines)))

database.parent.mkdir(exist_ok=True)
with sqlite3.connect(database) as connection:
    connection.execute("DROP TABLE IF EXISTS requirements")
    connection.execute("""
        CREATE VIRTUAL TABLE requirements USING fts5(
            heading, body,
            path UNINDEXED,
            start_line UNINDEXED,
            end_line UNINDEXED,
            commit_sha UNINDEXED
        )
    """)
    connection.executemany(
        "INSERT INTO requirements VALUES (?, ?, ?, ?, ?, ?)",
        [
            (heading, body, relative_path, first, last, commit)
            for heading, body, first, last in sections
        ],
    )

print(f"Indexed {len(sections)} requirement sections from {commit[:7]}")
