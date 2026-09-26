import re
import sqlite3
import sys
from pathlib import Path

sources = {
    "Requirements": ("requirements.sqlite", "requirements", "heading"),
    "Code": ("code.sqlite", "code", "symbol"),
    "Tests": ("tests.sqlite", "tests", "name"),
}

terms = re.findall(r"[a-z0-9_]+", " ".join(sys.argv[1:]).lower())
if not terms:
    raise SystemExit("Usage: python3 trace.py default timeout")

query = " AND ".join(f'"{term}"' for term in terms)
index_dir = Path(__file__).resolve().parent / "indexes"

for title, (filename, table, label) in sources.items():
    print(f"\n{title} candidates")
    with sqlite3.connect(index_dir / filename) as connection:
        rows = connection.execute(
            f"""
            SELECT {label}, body, path, start_line, end_line,
                    commit_sha, bm25({table}) AS rank
            FROM {table}
            WHERE {table} MATCH ?
            ORDER BY rank
            LIMIT 3
            """,
            (query,),
        ).fetchall()

    for name, body, path, first, last, commit, rank in rows:
        print(f"- {name} | score={rank:.3f}")
        print(f"  {path}:{first}-{last} @ {commit[:7]}")
        print(f"  {body[:160].replace(chr(10), ' ')}")

    if not rows:
        print("- No lexical matches")
