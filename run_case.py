import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
stages = [
    ("Provenance verifier", "verify.py"),
    ("Implementation verifier", "check_implementation.py"),
    ("Context builder", "packet.py"),
    ("Model reviewer and evidence guardrail", "review_packet.py"),
]

trace = []
for name, script in stages:
    print(f"\n=== {name} ===", flush=True)
    result = subprocess.run(
        [sys.executable, str(root / script)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=180,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")

    trace.append({
        "stage": name,
        "exit_code": result.returncode,
        "output": result.stdout,
        "error": result.stderr,
    })
    if result.returncode != 0:
        break

runs = root / "runs"
runs.mkdir(exist_ok=True)
(runs / "latest.json").write_text(
    json.dumps(trace, indent=2),
    encoding="utf-8",
)

if len(trace) != len(stages) or trace[-1]["exit_code"] != 0:
    raise SystemExit("Case workflow failed; see runs/latest.json")

print("\nCase workflow passed. Trace: runs/latest.json")
