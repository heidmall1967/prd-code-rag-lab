import json
from pathlib import Path

root = Path(__file__).resolve().parent
case = json.loads(
    (root / "cases/scorecard_branch_protection.json").read_text()
)

repo = (root / "data/scorecard").resolve()


def resolve_path(path):
    resolved = (repo / path).resolve()
    assert resolved.is_relative_to(repo), f"Path escapes repository: {path}"
    return resolved


def render(label, citation):
    if "focus" in citation:
        start, end = citation["focus"]
    else:
        start, end = citation["start_line"], citation["end_line"]

    lines = resolve_path(citation["path"]).read_text().splitlines()
    excerpt = "\n".join(
        f"{number}: {lines[number - 1]}"
        for number in range(start, end + 1)
    )
    return f"{label} | {citation['path']}:{start}-{end}\n{excerpt}"

parts = [
    f"Claim: {case['claim']}",
    f"Commit: {case['commit']}",
    render("Requirement", case["requirement"]),
]

parts += [render("Code", item) for item in case["implementation"]]
parts += [render("Test", item) for item in case["tests"]]

packet = "\n\n".join(parts)
print(packet)
print(f"\nContext used: {len(packet)} characters")
