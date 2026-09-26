# prd-code-rag-lab

A local learning lab for correlating requirement, code, and test retrieval
databases, then checking whether a small LLM's verdict survives source-based
verification:

    lexical index (FTS5) → cited excerpt → provenance re-check against disk/git
        → bounded-context packet → LLM verdict → deterministic guardrail

Four curated claims exercise the pipeline against three open-source repos:

- **httpx** (Python) — does `httpx.Client()` really default to a 5-second timeout,
  and is that backed by a direct test (not just a test that passes the value
  explicitly)?
- **Scorecard** (Go) — does the Branch-Protection check really award Tier 1 when
  the force-push and deletion probes both report protection?
- **httpx contradiction** — does a new client instead default to ten seconds?
- **Pluggy** (Python) — does a `firstresult=True` hook return the first
  non-`None` implementation result as a single value?

The original HTTPX experiment caught a model falsely crediting a related test
as direct. In the unified workflow, two sequential local model agents review
the same verified evidence, but deterministic, case-specific checks decide the
final verdict. On the Scorecard case, the agents disagreed about direct testing;
the trace retains both opinions for inspection. See [GUIDE.md](GUIDE.md) for
the full workflow and its limits.

## Requirements

- Python 3.12+ (stdlib only — `sqlite3` with FTS5, `ast`, `urllib.request`; no
  third-party packages needed for the Python scripts)
- `git` (used to read/verify commit SHAs of the vendored repos)
- Go 1.21+ (only needed to rebuild `bin/go_chunks`, the Scorecard chunker)
- [Ollama](https://ollama.com) running locally at `127.0.0.1:11434` with
  `qwen2.5:1.5b` pulled for `lab.py run --mode local` and the older model
  experiments. `--mode offline`, indexing, search, and tests need no model.

## Layout

```
data/httpx/          vendored clone of github.com/encode/httpx, pinned to a
                      commit referenced by cases/default_timeout.json
data/scorecard/      vendored clone of github.com/ossf/scorecard, pinned to a
                      commit referenced by cases/scorecard_branch_protection.json
cases/*.json         one "claim" per file: the claim text, the doc/code/test
                      citations that back it, and the expected verdict
indexes/*.sqlite     FTS5 indexes built from data/httpx and data/scorecard
                      (regenerate with the index_*.py scripts below — nothing
                      here is hand-maintained)
index_*.py           build the FTS5 indexes for docs / code / tests
search.py,
search_docs.py,
references.py,
traces.py            ad hoc lexical lookups against the indexes, for exploring
                      by hand (see "Usage:" text in each script for the exact
                      argv shape)
packet.py,
packet_scorecard.py  assemble a bounded-context, line-numbered evidence packet
                      for one case
verify.py,
verify_scorecard.py  re-derive each cited excerpt from the source files on
                      disk and the current commit SHA, and fail loudly on any
                      mismatch (stale index, edited source, wrong commit)
check_implementation.py
                      httpx-specific structural check (AST) that the default
                      timeout constant is actually wired into both clients
evidence_guard.py     deterministic checks that can downgrade or correct an
                      LLM verdict (e.g. catches a test being credited with
                      "supports" when it never constructs a client)
judge_one.py,
review_packet.py     older HTTPX-only experiment with local model judgment
                      and a specific direct-test guardrail
run_case.py           runs the full httpx pipeline end to end (verify →
                      check_implementation → packet → review_packet) and
                      writes a trace to runs/latest.json
lab.py                unified CLI for discovery and role-based case runs
lab_core.py           policy, RBAC, pinned-source retrieval, provenance,
                      bounded packets, and agent handoffs
lab_guards.py         narrow deterministic proofs for the curated claims
policy.json           source allowlist, role permissions, context cap, and
                      local-only model endpoint
tests/test_lab.py     cross-layer regression tests
index_pluggy.py       builds Pluggy RST requirements, Python code, and test
                      indexes using only the Python standard library
```

## Setup

The vendored repos in `data/` must exist and be checked out at the exact
commits the case files reference. If they're missing:

```bash
git clone https://github.com/encode/httpx.git data/httpx
git -C data/httpx checkout b5addb64f0161ff6bfe94c124ef76f6a1fba5254

git clone https://github.com/ossf/scorecard.git data/scorecard
git -C data/scorecard checkout f92023a3f77879f96e0c9c1305f289d755be4bb6
```

## Running the httpx case

```bash
# Build the indexes (repeat any time data/httpx or the indexing scripts change)
python3 index_docs.py
python3 index_code.py
python3 index_tests.py

# Run the full pipeline (requires Ollama running with qwen2.5:1.5b)
python3 run_case.py
```

`run_case.py` chains `verify.py` → `check_implementation.py` → `packet.py` →
`review_packet.py`, stops at the first failing stage, and writes every
stage's stdout/stderr to `runs/latest.json`. Run any stage on its own for
faster iteration, e.g. `python3 packet.py 1800` to just print the evidence
packet with a given character budget.

`judge_one.py` runs a narrower experiment: it judges a single cited test
excerpt against the claim, in isolation, to see whether the model (and the
guardrail) get that one piece of evidence right.

## Running the Scorecard case

```bash
# Rebuild bin/go_chunks if go_chunks.go changed
go build -o bin/go_chunks go_chunks.go

# Chunk the Go source/test files this case cites (must be run with paths
# relative to the project root — go_chunks derives each record's stored path
# from that). Use `go build` + the binary, not `go run`: `go run` refuses to
# accept _test.go files as arguments.
bin/go_chunks \
  data/scorecard/checks/evaluation/branch_protection.go \
  data/scorecard/checks/evaluation/branch_protection_test.go \
  data/scorecard/probes/blocksForcePushOnBranches/impl.go \
  data/scorecard/probes/blocksForcePushOnBranches/impl_test.go \
  > indexes/scorecard_samples.jsonl

python3 index_scorecard_docs.py
python3 index_scorecard_go.py

# Verify provenance and inspect the evidence packet
python3 verify_scorecard.py
python3 packet_scorecard.py
```

## Running the Pluggy case

Pluggy provides an independent MIT-licensed plugin-system example with RST
documentation and Python code. Rebuild its three indexes with:

```bash
git clone https://github.com/pytest-dev/pluggy.git data/pluggy
git -C data/pluggy checkout 54fb4ddda7d0e0dc9dde12fa5cebb9ae13d8cff9
python3 index_pluggy.py
```

The new case is `cases/pluggy_firstresult.json`. The lab's regression suite
executes a small behavior check against the pinned Pluggy source without
installing pytest.

## Unified learning workflow

```bash
python3 lab.py roles
python3 lab.py discover --repo scorecard --kind requirement --query force
python3 lab.py correlate --repo scorecard --query 'force push'
python3 lab.py correlate --repo pluggy --query firstresult
python3 lab.py run --case cases/default_timeout.json --mode offline
python3 lab.py run --case cases/default_timeout_ten.json --mode offline
python3 lab.py run --case cases/scorecard_branch_protection.json --mode offline
python3 lab.py run --case cases/pluggy_firstresult.json --mode offline
python3 lab.py run --case cases/pluggy_firstresult.json --mode local
python3 lab.py run --case cases/scorecard_branch_protection.json --mode local
python3 -m unittest discover -s tests -v
```

Each run writes an ignored JSON trace under `runs/`. See [GUIDE.md](GUIDE.md)
for agent roles, RBAC exercises, evidence semantics, and extension steps.

## Limits

The registered deterministic proofs cover these four claims only. New claims
fail closed as `insufficient`/`undetermined` until given a proof. The role
policy is an educational application check, not isolation from someone who
can edit local files. Both model agents use the same local model, so their
opinions are correlated. No web UI or open-ended semantic verification exists.
