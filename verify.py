import json
import sqlite3
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
repo = (root / "data/httpx").resolve()
case = json.loads((root / "cases/default_timeout.json").read_text())

commit = subprocess.check_output(
    ["git", "-C", str(repo), "rev-parse", "HEAD"],
    text=True,
).strip()
if not commit.startswith(case["commit"]):
    raise SystemExit("Case commit does not match the repository.")

def verify(filename, table, key_column, entry):
    path = entry["path"]
    source_file = (repo / path).resolve()
    if not source_file.is_relative_to(repo):
        raise SystemExit(f"Path escapes repository: {path}")

    if table == "requirements":
        condition = "path = ? AND start_line = ? AND end_line = ?"
        values = (path, entry["start_line"], entry["end_line"])
        label = path
    else:
        label = entry["symbol"] if table == "code" else entry["name"]
        condition = f"path = ? AND {key_column} = ?"
        values = (path, label)

    with sqlite3.connect(root / "indexes" / filename) as connection:
        rows = connection.execute(
            f"""SELECT body, start_line, end_line, commit_sha
                FROM {table} WHERE {condition}""",
            values,
        ).fetchall()

    if len(rows) != 1:
        raise SystemExit(f"Expected one indexed record for {label}; found {len(rows)}.")

    body, first, last, indexed_commit = rows[0]
    lines = source_file.read_text(encoding="utf-8").splitlines()
    source_span = "\n".join(lines[first - 1:last]).strip()

    if indexed_commit != commit:
        raise SystemExit(f"Stale index for {label}.")
    if body.strip() != source_span:
        raise SystemExit(f"Indexed text differs from source lines for {label}.")

    print(f"Verified {label}: {path}:{first}-{last}")

verify("requirements.sqlite", "requirements", "heading", case["requirement"])
for entry in case["implementation"]:
    verify("code.sqlite", "code", "symbol", entry)
for entry in case["related_tests"]:
    verify("tests.sqlite", "tests", "name", entry)

print(f"Provenance passed; direct test status: {case['direct_test_status']}")
