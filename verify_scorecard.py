import json
import sqlite3
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
case = json.loads(
    (root / "cases/scorecard_branch_protection.json").read_text()
)

records = (
    [case["requirement"]]
    + case["implementation"]
    + case["tests"]
)

print(f"Loaded {len(records)} citations")
for record in records:
    print(record["path"])

requirement = case["requirement"]
repo = (root / "data/scorecard").resolve()


def resolve_path(path):
    resolved = (repo / path).resolve()
    assert resolved.is_relative_to(repo), f"Path escapes repository: {path}"
    return resolved


def verify_source_body(path, start_line, end_line, body):
    lines = resolve_path(path).read_text().splitlines()
    assert 1 <= start_line <= end_line <= len(lines), f"Invalid lines: {path}"

    source_span = "\n".join(lines[start_line - 1 : end_line])
    assert body.strip() in source_span, f"Indexed body differs from source: {path}"


with sqlite3.connect(root / "indexes/scorecard_requirements.sqlite") as db:
    row = db.execute(
        """
        SELECT end_line, commit_sha, body
        FROM requirements
        WHERE path = ? AND start_line = ?
        """,
        (requirement["path"], requirement["start_line"]),
    ).fetchone()

assert row is not None, "Requirement missing from index"
assert row[0] == requirement["end_line"], "Requirement line range differs"

full_commit = subprocess.check_output(
    ["git", "-C", str(repo), "rev-parse", "HEAD"],
    text=True,
).strip()

assert full_commit.startswith(case["commit"]), "Case commit differs from repository"
assert row[1] == full_commit, "Indexed commit differs from repository"

source_lines = resolve_path(requirement["path"]).read_text().splitlines()

source_body = "\n".join(
    source_lines[requirement["start_line"] - 1 : row[0]]
)

assert row[2].strip() == source_body.strip(), (
    "Indexed requirement text differs from source"
)

print("Requirement provenance passed")

with sqlite3.connect(root / "indexes/scorecard_code.sqlite") as db:
    for citation in case["implementation"]:
        row = db.execute(
            """
            SELECT start_line, end_line, commit_sha, body
            FROM code
            WHERE path = ? AND symbol = ?
            """,
            (citation["path"], citation["symbol"]),
        ).fetchone()

        assert row is not None, f"Missing code: {citation['symbol']}"

        start, end = citation["focus"]
        assert row[0] <= start <= end <= row[1], (
            f"Focus outside indexed code: {citation['symbol']}"
        )
        assert row[2] == full_commit, (
            f"Commit differs: {citation['symbol']}"
        )
        verify_source_body(citation["path"], row[0], row[1], row[3])

        print(f"Verified code: {citation['symbol']}")

with sqlite3.connect(root / "indexes/scorecard_tests.sqlite") as db:
    for citation in case["tests"]:
        row = db.execute(
            """
            SELECT start_line, end_line, commit_sha, body
            FROM tests
            WHERE path = ? AND symbol = ?
            """,
            (citation["path"], citation["symbol"]),
        ).fetchone()

        assert row is not None, f"Missing test: {citation['symbol']}"

        start, end = citation["focus"]
        assert row[0] <= start <= end <= row[1], (
            f"Focus outside indexed test: {citation['symbol']}"
        )
        assert row[2] == full_commit, (
            f"Commit differs: {citation['symbol']}"
        )
        verify_source_body(citation["path"], row[0], row[1], row[3])

        print(f"Verified test: {citation['symbol']}")
