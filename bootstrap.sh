#!/usr/bin/env bash
# Rebuild ignored open-source data and indexes after cloning this lab.
set -euo pipefail

cd "$(dirname "$0")"

echo "Setup will clone pinned HTTPX, Scorecard, and Pluggy if absent; build local"
echo "indexes and a Go chunker; then run tests and a benchmark."
echo "It does not install system packages or pull an Ollama model."

for program in git go python3; do
  if ! command -v "$program" >/dev/null 2>&1; then
    echo "Missing required program: $program" >&2
    exit 1
  fi
done

python3 - <<'PY'
import sqlite3
import sys

if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12 or newer is required")
with sqlite3.connect(":memory:") as db:
    db.execute("CREATE VIRTUAL TABLE fts_check USING fts5(body)")
PY

mkdir -p data indexes bin

clone_pinned() {
  local name="$1"
  local url="$2"
  local expected="$3"
  local path="data/$name"
  if [[ ! -d "$path/.git" ]]; then
    if [[ -e "$path" ]]; then
      echo "$path exists but is not a Git checkout; inspect it before retrying" >&2
      exit 1
    fi
    git clone "$url" "$path"
    git -C "$path" checkout --detach "$expected"
  fi
  local actual
  actual="$(git -C "$path" rev-parse HEAD)"
  if [[ "$actual" != "$expected" ]]; then
    echo "$path is at $actual, but policy requires $expected" >&2
    exit 1
  fi
  if [[ -n "$(git -C "$path" status --porcelain)" ]]; then
    echo "$path has local changes; use a clean pinned checkout" >&2
    exit 1
  fi
  echo "Pinned $name at $actual"
}

clone_pinned httpx https://github.com/encode/httpx.git \
  b5addb64f0161ff6bfe94c124ef76f6a1fba5254
clone_pinned scorecard https://github.com/ossf/scorecard.git \
  f92023a3f77879f96e0c9c1305f289d755be4bb6
clone_pinned pluggy https://github.com/pytest-dev/pluggy.git \
  54fb4ddda7d0e0dc9dde12fa5cebb9ae13d8cff9

python3 index_docs.py
python3 index_code.py
python3 index_tests.py

go build -o bin/go_chunks go_chunks.go
bin/go_chunks \
  data/scorecard/checks/evaluation/branch_protection.go \
  data/scorecard/checks/evaluation/branch_protection_test.go \
  data/scorecard/probes/blocksForcePushOnBranches/impl.go \
  data/scorecard/probes/blocksForcePushOnBranches/impl_test.go \
  > indexes/scorecard_samples.jsonl
python3 index_scorecard_docs.py
python3 index_scorecard_go.py
python3 index_pluggy.py

python3 -m unittest discover -s tests -q
python3 benchmark_retrieval.py
echo "Setup complete. Open LEARNING_WALKTHROUGH.html or run python3 lab.py --help."
