# prd-code-rag-lab

A local learning lab for correlating requirement, code, and test retrieval
databases, then checking whether a small LLM's verdict survives source-based
verification:

**Start with the [interactive HTML walkthrough](LEARNING_WALKTHROUGH.html)** to
turn a PRD line item into a correlation search, then follow step-by-step
commands, expected results, and an explanation of every evaluation.

    lexical index (FTS5) → cited excerpt → provenance re-check against disk/git
        → bounded-context packet → LLM verdict → deterministic guardrail

This is a lexical RAG learning pipeline: retrieval uses FTS5, augmentation
puts verified excerpts into a bounded prompt, and local Ollama generates
reviewer/critic judgments. Candidate discovery and case execution are separate:
the runner uses reviewed citations in a case file, not automatic evidence
selection for an arbitrary PRD line. Its deterministic guardrail decides the
final verdict.

The general new-PRD-line workflow is planned as [Phase 2](PHASE2.md). It will
index a separate open-source requirements source, retrieve citable code and
tests automatically, and evaluate uncertain as well as supported outcomes.

## Fresh clone: run the lab

The repository is currently **private**, so a person needs GitHub access to
clone it. It intentionally excludes the upstream source clones, generated
SQLite indexes, binaries, and traces. A fresh clone needs one bootstrap run.
On Ubuntu, install Python 3.12+, Git, and Go 1.21+ first. Python scripts use
only the standard library with SQLite FTS5; no pip install is needed.

```bash
git clone https://github.com/heidmall1967/prd-code-rag-lab.git
cd prd-code-rag-lab
bash bootstrap.sh
```

The script clones open-source HTTPX, OpenSSF Scorecard, and Pluggy at the
commits in [policy.json](policy.json), builds all nine SQLite indexes and the
Go chunker, then runs the 15 lab tests and retrieval benchmark. It checks
existing source checkouts before rebuilding, so you can rerun it. Cloning the
three upstream repositories requires internet access and may take a while;
after setup, offline case runs do not.

```bash
xdg-open LEARNING_WALKTHROUGH.html
python3 lab.py correlate --repo scorecard --query 'force push' --limit 10
python3 lab.py run --case cases/scorecard_branch_protection.json --mode offline
```

Successful setup ends with `Ran 15 tests`, `OK`, and a benchmark report with
`recall_at_k: 0.8`. The case command should print `supports`,
`established`, and `Evaluation: PASS`. The HTML walkthrough shows the PRD-line
search workflow and explains what these labels mean.

The model is optional. For local reviewer/critic runs, install Ollama, pull
the policy-pinned model, and start its local service:

```bash
ollama pull qwen2.5:1.5b
ollama serve
```

In a second terminal, run
`python3 lab.py run --case cases/pluggy_firstresult_list.json --mode local`.
The final guardrail should return `contradicts / not_established` even if the
model disagrees.

## Downloads, storage, and hardware

`bash bootstrap.sh` does **not** install system packages, Python packages,
Go modules, Ollama, or a model. It uses your existing Python, Git, and Go;
clones only the pinned open-source HTTPX, Scorecard, and Pluggy repositories;
builds a local Go chunker and nine SQLite FTS5 indexes; then runs the lab tests
and benchmark. It does execute this repository's indexing/test code, and one
lab test imports the pinned Pluggy source. Review the script before running it.
No `sudo` is needed.

These are measurements from the Ubuntu development machine on 2026-09-26,
not download guarantees. Upstream Git histories and Ollama packaging can grow.

| Item | Measured disk use | Pulled by |
| --- | ---: | --- |
| HTTPX / Scorecard / Pluggy source clones, including Git history | 6 MB / 104 MB / 1.2 MB | `bootstrap.sh` |
| All nine SQLite indexes and Go chunker | 1.6 MB + 2.9 MB | `bootstrap.sh` |
| Go build cache outside the repo | 35 MB | Go build |
| Qwen2.5 1.5B model (Apache-2.0) | 986 MB (about 0.92 GiB) | Optional `ollama pull qwen2.5:1.5b` |
| Installed Ollama binary and runtime libraries on this machine | 37 MB + 2.1 GB | Separate Ollama installation; varies |

The bootstrap itself adds about 115 MB under the project directory here.
The optional model is another ~1 GB; an Ollama installation can be larger than
the model because it includes runtime libraries. This machine also has a 3B
model, so its total model store is 2.8 GB; **that 3B model is not required**.
Plan for at least **2 GB free** for offline setup if prerequisites are already
installed, or **6–8 GB free** for a first-time Ollama plus model setup.
The [Ollama model page](https://ollama.com/library/qwen2.5) lists the 1.5B
download size; [Ollama's FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)
explains where its model store lives on different installations.

The offline search and case workflow needs no GPU or model. On this 12 GB RAM,
2 GB VRAM machine, one local 4,096-token Qwen2.5 1.5B run reported a 1.4 GB
loaded model, used about 0.8 GB resident runner RAM, and increased GPU use by
about 1.0 GB. Your driver or Ollama build may instead use more system RAM and
less GPU. Keep roughly 3–4 GB RAM available, use one case/model at a time,
and expect local model calls to take tens of seconds on an older i5. The lab
already caps context at 4,096 tokens and calls reviewer and critic
sequentially. Larger contexts and parallel requests increase memory use
([Ollama context guidance](https://github.com/ollama/ollama/blob/main/docs/context-length.mdx),
[FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)).

If Ollama is not already running, a conservative local-only configuration is:

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

Use `ollama ps` to check CPU/GPU placement and loaded size, `free -h` for
available RAM, and `nvidia-smi` if available. GPU use depends on hardware,
driver, and build; do not require it for this lab
([Ollama hardware notes](https://github.com/ollama/ollama/blob/main/docs/gpu.mdx)).
Run `ollama stop qwen2.5:1.5b` after a session if you want to release its
RAM and VRAM immediately.

## Security and privacy boundaries

- Bootstrap connects to GitHub for the three open-source clones. The optional
  model pull connects to Ollama's model registry. Offline cases make no paid
  API calls; local cases send prompts only to the policy-pinned
  `127.0.0.1:11434` endpoint.
- Keep Ollama bound to `127.0.0.1`. Changing `OLLAMA_HOST` to `0.0.0.0` or
  exposing port 11434 can make the local model service reachable from your
  network ([Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)).
- Pinned commits and source-line checks detect stale or changed evidence.
  They do not make upstream code intrinsically safe. Bootstrap runs local
  scripts, builds Go code, and the lab test imports Pluggy; use trusted
  checkouts and avoid `sudo`.
- Retrieved text is untrusted input to the model and can contain misleading
  instructions. Model opinions are recorded, while narrow deterministic
  checks decide registered cases. This is not a general prompt-injection
  defense or proof engine.
- The `--principal` RBAC control is educational; anyone with local access can
  choose another principal or edit `policy.json`. The HTML PRD query builder
  runs locally, but a copied query may remain in shell history. Keep secrets
  out of cases and queries. Generated `runs/` traces are ignored by Git but
  can include model opinions that repeat supplied text.

Six curated cases exercise the pipeline against three open-source repos:

- **httpx** (Python) — does `httpx.Client()` really default to a 5-second timeout,
  and is that backed by a direct test (not just a test that passes the value
  explicitly)?
- **Scorecard** (Go) — does the Branch-Protection check really award Tier 1 when
  the force-push and deletion probes both report protection?
- **httpx contradiction** — does a new client instead default to ten seconds?
- **Pluggy** (Python) — does a `firstresult=True` hook return the first
  non-`None` implementation result as a single value? Two adversarial cases
  claim it returns a list or cite only a related test.

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
data/pluggy/         vendored clone of github.com/pytest-dev/pluggy
cases/*.json         one "claim" per file: the claim text, the doc/code/test
                      citations that back it, and the expected verdict
indexes/*.sqlite     FTS5 indexes built from the three source repos
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
benchmark_retrieval.py
                      measures pinned, hand-reviewed retrieval targets
benchmarks/retrieval.json
                      five target citations and their natural-language queries
```

## Manual source setup

Use `bash bootstrap.sh` for the complete setup. If rebuilding individual
pieces while learning, the source repos in `data/` must match the pinned
commits. For example:

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

The main case is `cases/pluggy_firstresult.json`. The lab's regression suite
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
python3 lab.py run --case cases/pluggy_firstresult_list.json --mode offline
python3 lab.py run --case cases/pluggy_firstresult_related_test.json --mode offline
python3 benchmark_retrieval.py
python3 lab.py run --case cases/pluggy_firstresult.json --mode local
python3 lab.py run --case cases/scorecard_branch_protection.json --mode local
python3 -m unittest discover -s tests -v
```

Each run writes an ignored JSON trace under `runs/`. See [GUIDE.md](GUIDE.md)
for agent roles, RBAC exercises, evidence semantics, and extension steps.

## Limits

The registered deterministic proofs cover these six cases only. New claims
fail closed as `insufficient`/`undetermined` until given a proof. The role
policy is an educational application check, not isolation from someone who
can edit local files. Both model agents use the same local model, so their
opinions are correlated. The HTML walkthrough generates local commands but is
not a browser front end for running retrieval. Open-ended semantic verification
does not exist.

See [Phase 2](PHASE2.md) for the next build scope and acceptance checks.
