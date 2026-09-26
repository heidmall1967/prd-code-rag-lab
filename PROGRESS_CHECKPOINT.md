# Progress checkpoint — 2026-09-26

## Working agreement

The user first built the lab step by step, then explicitly authorized the assistant to build autonomously with feedback and decision questions. Use only open-source source data. The lab runs locally on Ubuntu with about 12 GB RAM, 2 GB VRAM, and an older i5; Ollama `qwen2.5:1.5b` is the local reviewer.

## Project goal

Build a from-scratch learning lab that correlates separate requirement, implementation, and test retrieval indexes. Expand it into a study of context engineering, evidence-based guardrails, policy, RBAC, agents, and multi-agent interaction. Current data sources are pinned open-source HTTPX (`b5addb6`, BSD-3-Clause), OpenSSF Scorecard (`f92023a`, Apache-2.0), and Pluggy (`54fb4dd`, MIT). The local Qwen2.5 1.5B model is Apache-2.0.

## Completed

- HTTPX indexes: 9 requirement sections, 470 Python code records, 539 test records, each in a separate SQLite FTS5 database.
- HTTPX default-timeout case: provenance, structural implementation check, bounded evidence packet, local model review, and deterministic guardrail. The implementation is supported. The cited tests are related but do not directly establish that a client constructed without a timeout uses the built-in five-second default. The model falsely marked direct testing established; the guardrail corrected it. The user reported `python3 run_case.py` passing and writing `runs/latest.json`.
- Scorecard indexes: 19 Branch-Protection requirement blocks, 33 Go code records, and 5 Go test records. The Go chunks are extracted with a user-written standard-library AST program.
- Scorecard case file `cases/scorecard_branch_protection.json`: one requirement citation, five implementation citations, and three test citations (nine total). The added test-runner excerpt shows the table case is executed and checked. `verify_scorecard.py` now compares indexed text with source for all nine records.
- Pluggy indexes: 44 RST requirement sections, 93 Python code records, and 165 test records from commit `54fb4dd`. The first-result case cites the RST requirement, the `_multicall` loop, and two direct tests; its offline and local model workflows pass. A regression test executes the pinned Pluggy package without pytest.
- The unified `lab.py` workflow runs four curated claims: HTTPX's five-second default (`supports`), a ten-second default counterclaim (`contradicts`), Scorecard Tier 1 (`supports`), and Pluggy's first non-`None` scalar result (`supports`). It retrieves from separate FTS5 indexes, checks pinned source, builds bounded packets, runs optional sequential reviewer/critic model agents, applies narrow deterministic proofs, enforces application-level RBAC, and writes JSON traces.
- `lab.py correlate` searches requirement, code, and test databases together, suggests lexical links, and follows code-symbol references. Candidates are verified against source but remain suggestions until curated into a case.
- Thirteen cross-layer regression tests pass. Local Qwen2.5 1.5B runs passed all four cases. On the ten-second counterclaim, the reviewer wrongly returned `supports`; the deterministic final verdict returned `contradicts` and recorded the disagreement.

## Current status

The CLI-first version is documented in `GUIDE.md` and stored in the private repository `https://github.com/heidmall1967/prd-code-rag-lab` on `main`. The unified workflow, four case evaluations, and 13 regression tests passed. The source clones, SQLite indexes, binaries, and traces are ignored by Git and can be rebuilt using `GUIDE.md`. Start Ollama for `--mode local`. This remains an educational, claim-specific verifier rather than a general PRD-to-code proof engine.

## Resume from here

1. Open `/home/gsharma/prd-code-rag-lab` and read `GUIDE.md` for the CLI commands and architecture.
2. Run `python3 -m unittest discover -s tests -v` for a quick baseline. Run `python3 lab.py run --case cases/scorecard_branch_protection.json --mode offline` for an end-to-end source check.
3. Choose the next learning milestone: improve ranking so Pluggy's `_multicall` implementation surfaces automatically, add a negative Pluggy case, or build a small local browser UI. Ranking is the recommended next experiment because the new source exposed a concrete retrieval miss.

## Later work

Possible extensions are a local browser UI, more independent open-source requirements and repositories, stronger semantic reranking, negative Scorecard cases, and isolated RBAC identities rather than a CLI-selected principal. The current proofs are intentionally claim-specific; arbitrary new claims fail closed. The reviewer and critic use the same local model and should not be treated as independent evidence.

The user also asked how to switch this session to their ChatGPT Plus plan. That question remains unanswered; verify current official OpenAI guidance before answering it if they raise it again.
