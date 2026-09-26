import re
import sqlite3
import sys
from pathlib import Path

sources = {
    "tests": ("tests.sqlite", "tests", "name"),
    "requirements": ("requirements.sqlite", "requirements", "heading"),
    "code": ("code.sqlite", "code", "symbol"),
    "scorecard_requirements": (
    "scorecard_requirements.sqlite", "requirements", "heading"
  ) ,
    "scorecard_code": ("scorecard_code.sqlite", "code", "symbol"),
    "scorecard_tests": ("scorecard_tests.sqlite", "tests", "symbol"),
    "pluggy_requirements": ("pluggy_requirements.sqlite", "requirements", "heading"),
    "pluggy_code": ("pluggy_code.sqlite", "code", "symbol"),
    "pluggy_tests": ("pluggy_tests.sqlite", "tests", "name"),

}

if len(sys.argv) < 3 or sys.argv[1] not in sources:
    raise SystemExit("Usage: python3 search.py code DEFAULT_TIMEOUT_CONFIG")

filename, table, label = sources[sys.argv[1]]
terms = re.findall(r"[a-z0-9_]+", " ".join(sys.argv[2:]).lower())
query = " AND ".join(f'"{term}"' for term in terms)
database = Path(__file__).resolve().parent / "indexes" / filename

with sqlite3.connect(database) as connection:
    rows = connection.execute(
        f"""
        SELECT {label}, body, path, start_line, end_line,
                commit_sha, bm25({table}) AS rank
        FROM {table}
        WHERE {table} MATCH ?
        ORDER BY rank
        LIMIT 5
        """,
        (query,),
    ).fetchall()

for name, body, path, first, last, commit, rank in rows:
    print(f"\n{name} | score={rank:.3f}")
    print(f"{path}:{first}-{last} @ {commit[:7]}")
    print(body[:220].replace("\n", " "))

if not rows:
    print("No matches.")
