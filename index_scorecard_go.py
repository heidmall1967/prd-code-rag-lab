import json
import sqlite3
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
repo = root / "data/scorecard"
input_file = root / "indexes/scorecard_samples.jsonl"

commit = subprocess.check_output(
    ["git", "-C", str(repo), "rev-parse", "HEAD"],
    text=True,
).strip()

records = [
    json.loads(line)
    for line in input_file.read_text(encoding="utf-8").splitlines()
    if line.strip()
]

for kind, filename, table in (
    ("code", "scorecard_code.sqlite", "code"),
    ("test", "scorecard_tests.sqlite", "tests"),
):
    selected = [record for record in records if record["kind"] == kind]
    database = root / "indexes" / filename

    with sqlite3.connect(database) as connection:
        connection.execute(f"DROP TABLE IF EXISTS {table}")
        connection.execute(f"""
            CREATE VIRTUAL TABLE {table} USING fts5(
                symbol, body,
                path UNINDEXED,
                start_line UNINDEXED,
                end_line UNINDEXED,
                commit_sha UNINDEXED
            )
        """)
        connection.executemany(
            f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    record["symbol"], record["body"], record["path"],
                    record["start_line"], record["end_line"], commit,
                )
                for record in selected
            ],
        )

    print(f"Indexed {len(selected)} Scorecard {kind} functions from {commit[:7]}")
