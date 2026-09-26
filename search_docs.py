import re
import sqlite3
import sys
from pathlib import Path

terms = re.findall(r"[a-z0-9_]+", " ".join(sys.argv[1:]).lower())
if not terms:
    raise SystemExit("Usage: python3 search_docs.py default timeout")

query = " AND ".join(f'"{term}"' for term in terms)
database = Path(__file__).resolve().parent / "indexes/requirements.sqlite"

with sqlite3.connect(database) as connection:
    rows = connection.execute(
        """
        SELECT heading, body, path, start_line, end_line,
                commit_sha, bm25(requirements) AS rank
        FROM requirements
        WHERE requirements MATCH ?
        ORDER BY rank
        LIMIT 5
        """,
        (query,),
    ).fetchall()

for heading, body, path, first, last, commit, rank in rows:
    print(f"\n{heading} | score={rank:.3f}")
    print(f"{path}:{first}-{last} @ {commit[:7]}")
    print(body[:240].replace("\n", " "))

if not rows:
    print("No matching section found.")
