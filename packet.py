import json
import sqlite3
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
case = json.loads((root / "cases/default_timeout.json").read_text())
budget = int(sys.argv[1]) if len(sys.argv) > 1 else 1800

def fetch(filename, table, key, entry):
    if table == "requirements":
        where = "path = ? AND start_line = ? AND end_line = ?"
        values = (entry["path"], entry["start_line"], entry["end_line"])
    else:
        where = f"path = ? AND {key} = ?"
        values = (entry["path"], entry[key])

    with sqlite3.connect(root / "indexes" / filename) as connection:
        row = connection.execute(
            f"SELECT body, start_line, commit_sha FROM {table} WHERE {where}",
            values,
        ).fetchone()

    if row is None or not row[2].startswith(case["commit"]):
        raise SystemExit(f"Missing or stale evidence: {entry['path']}")
    return row

def numbered_excerpt(body, first_line, focus=None):
    lines = body.splitlines()
    if focus:
        hits = [i for i, line in enumerate(lines) if focus in line]
        positions = sorted({
            j for i in hits
            for j in range(max(0, i - 1), min(len(lines), i + 2))
        })
    else:
        positions = range(len(lines))
    return "\n".join(f"{first_line + i}: {lines[i]}" for i in positions)

blocks = []

def add(kind, filename, table, key, entry, focus=None):
    body, first, commit = fetch(filename, table, key, entry)
    excerpt = numbered_excerpt(body, first, focus)
    blocks.append(
        f"{kind} | {entry['path']} @ {commit[:7]}\n{excerpt}"
    )

add("Requirement", "requirements.sqlite", "requirements",
    "heading", case["requirement"])

focus_term = case["implementation"][0]["symbol"]
for entry in case["implementation"]:
    focus = None if entry["symbol"] == focus_term else focus_term
    add("Code", "code.sqlite", "code", "symbol", entry, focus)

for entry in case["related_tests"]:
    add("Test", "tests.sqlite", "tests", "name", entry)

used = 0
for block in blocks:
    if used + len(block) <= budget:
        print(f"\n{block}")
        used += len(block)
    else:
        print(f"\nOMITTED: {block.splitlines()[0]}")

print(f"\nContext used: {used}/{budget} characters")
