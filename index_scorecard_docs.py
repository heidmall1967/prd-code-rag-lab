import sqlite3
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
repo = root / "data/scorecard"
relative_path = "docs/checks.md"
lines = (repo / relative_path).read_text(encoding="utf-8").splitlines()

commit = subprocess.check_output(
    ["git", "-C", str(repo), "rev-parse", "HEAD"],
    text=True,
).strip()

section_start = next(
    number for number, line in enumerate(lines, 1)
    if line.strip() == "## Branch-Protection"
)
section_end = next(
    (
        number for number in range(section_start + 1, len(lines) + 1)
        if lines[number - 1].startswith("## ")
    ),
    len(lines) + 1,
)

blocks = []
current = []
first = None

for number in range(section_start + 1, section_end):
    line = lines[number - 1]
    if line.strip():
        if first is None:
            first = number
        current.append(line)
    elif current:
        blocks.append(("\n".join(current).strip(), first, number - 1))
        current = []
        first = None

if current:
    blocks.append(("\n".join(current).strip(), first, section_end - 1))

database = root / "indexes/scorecard_requirements.sqlite"
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
            ("Branch-Protection", body, relative_path, first, last, commit)
            for body, first, last in blocks
        ],
    )

print(f"Indexed {len(blocks)} requirement blocks from {commit[:7]}")
for body, first, last in blocks:
    if "force push" in body.lower():
        print(f"Force-push candidate: {relative_path}:{first}-{last}")
