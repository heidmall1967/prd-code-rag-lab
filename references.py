import re
import sqlite3
import sys
from pathlib import Path

if len(sys.argv) != 2 or not re.fullmatch(r"[A-Za-z_]\w*", sys.argv[1]):
    raise SystemExit("Usage: python3 references.py DEFAULT_TIMEOUT_CONFIG")

identifier = sys.argv[1]
database = Path(__file__).resolve().parent / "indexes/code.sqlite"

with sqlite3.connect(database) as connection:
    rows = connection.execute(
        """
        SELECT symbol, path, start_line, end_line, commit_sha, body
        FROM code
        WHERE body LIKE ?
        ORDER BY path, symbol
        """,
        (f"%{identifier}%",),
    ).fetchall()

for symbol, path, first, last, commit, body in rows:
    if re.search(rf"\b{re.escape(identifier)}\b", body):
        print(f"{symbol} | {path}:{first}-{last} @ {commit[:7]}")
