# prd-code-rag-lab

A lab for testing whether a **small, local LLM can be trusted to verify PRD-style
claims against real source code**, by forcing every judgment through a strict
evidence pipeline instead of trusting the model's word:

    lexical index (FTS5) → cited excerpt → provenance re-check against disk/git
        → bounded-context packet → LLM verdict → deterministic guardrail

Two case studies exercise the pipeline against real open-source repos:

- **httpx** (Python) — does `httpx.Client()` really default to a 5-second timeout,
  and is that backed by a direct test (not just a test that passes the value
  explicitly)?
- **Scorecard** (Go) — does the Branch-Protection check really award Tier 1 when
  the force-push and deletion probes both report protection?

The interesting result so far: in the httpx case, the model's own verdict was
wrong (it hallucinated that a test checked the built-in default when the test
actually supplied the value explicitly). A deterministic AST guardrail in
[`evidence_guard.py`](evidence_guard.py) catches exactly that mistake and
flips the final verdict — see [`runs/latest.json`](runs/latest.json) for the
full trace. That's the core thesis: don't trust the model's verdict alone,
verify it against code.

## Requirements

- Python 3.12+ (stdlib only — `sqlite3` with FTS5, `ast`, `urllib.request`; no
  third-party packages needed for the Python scripts)
- `git` (used to read/verify commit SHAs of the vendored repos)
- Go 1.21+ (only needed to rebuild `bin/go_chunks`, the Scorecard chunker)
- [Ollama](https://ollama.com) running locally at `127.0.0.1:11434` with the
  `qwen2.5:1.5b` model pulled (`ollama pull qwen2.5:1.5b`) — required for
  `judge_one.py` and `review_packet.py`, which are the only scripts that call
  an LLM. Everything else (indexing, search, provenance verification, packet
  building) runs without it.

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
review_packet.py     send a single evidence excerpt, or a whole packet, to the
                      local model and print its verdict + the guardrail's
                      correction (httpx case only — see "Known gaps" below)
run_case.py           runs the full httpx pipeline end to end (verify →
                      check_implementation → packet → review_packet) and
                      writes a trace to runs/latest.json
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

## Known gaps

- There is no Scorecard equivalent of `run_case.py`/`review_packet.py` yet —
  the Scorecard case only exercises indexing and provenance verification, not
  LLM judging.
- Only two cases exist in total, and neither currently exercises a
  `contradicts` verdict, so the guardrail approach's generality beyond the one
  failure mode it was built to catch is unproven.
- `evidence_guard.py`'s two functions have no direct unit tests; they're only
  exercised indirectly through the two end-to-end cases.
