# Progress checkpoint — 2026-09-26

## Working agreement

The user first built the lab step by step, then explicitly authorized the assistant to build autonomously with feedback and decision questions. Use only open-source source data. The lab runs locally on Ubuntu with about 12 GB RAM, 2 GB VRAM, and an older i5; Ollama `qwen2.5:1.5b` is the local reviewer.

## Project goal

Build a from-scratch learning lab that correlates separate requirement, implementation, and test retrieval indexes. Expand it into a study of context engineering, evidence-based guardrails, policy, RBAC, agents, and multi-agent interaction. Current data sources are pinned open-source HTTPX (`b5addb6`, BSD-3-Clause) and OpenSSF Scorecard (`f92023a`, Apache-2.0). The local Qwen2.5 1.5B model is Apache-2.0.

## Completed

- HTTPX indexes: 9 requirement sections, 470 Python code records, 539 test records, each in a separate SQLite FTS5 database.
- HTTPX default-timeout case: provenance, structural implementation check, bounded evidence packet, local model review, and deterministic guardrail. The implementation is supported. The cited tests are related but do not directly establish that a client constructed without a timeout uses the built-in five-second default. The model falsely marked direct testing established; the guardrail corrected it. The user reported `python3 run_case.py` passing and writing `runs/latest.json`.
- Scorecard indexes: 19 Branch-Protection requirement blocks, 33 Go code records, and 5 Go test records. The Go chunks are extracted with a user-written standard-library AST program.
- Scorecard case file `cases/scorecard_branch_protection.json`: one requirement citation, five implementation citations, and three test citations (nine total). The added test-runner excerpt shows the table case is executed and checked. `verify_scorecard.py` now compares indexed text with source for all nine records.
- The unified `lab.py` workflow runs three curated claims: HTTPX's five-second default (`supports`), a ten-second default counterclaim (`contradicts`), and Scorecard Tier 1 (`supports`). It retrieves from separate FTS5 indexes, checks pinned source, builds bounded packets, runs optional sequential reviewer/critic model agents, applies narrow deterministic proofs, enforces application-level RBAC, and writes JSON traces.
- `lab.py correlate` searches requirement, code, and test databases together, suggests lexical links, and follows code-symbol references. Candidates are verified against source but remain suggestions until curated into a case.
- Eleven cross-layer regression tests pass. Local Qwen2.5 1.5B runs passed all three cases. On the ten-second counterclaim, the reviewer wrongly returned `supports`; the deterministic final verdict returned `contradicts` and recorded the disagreement.

## Current status

The assistant asked whether the first complete version should remain CLI-only or add a local browser UI; no reply has arrived. CLI-first is implemented and documented in `GUIDE.md`. The unified workflow, three case evaluations, and regression suite have passed. This remains an educational, claim-specific verifier rather than a general PRD-to-code proof engine.

## Later work

Possible next learning extensions are a local browser UI, more independent open-source requirements and repositories, stronger semantic reranking, negative Scorecard cases, and isolated RBAC identities rather than a CLI-selected principal. The current proofs are intentionally claim-specific; arbitrary new claims fail closed.

The user also asked how to switch this session to their ChatGPT Plus plan. That question remains unanswered; verify current official OpenAI guidance before answering it. There is no Git repository at the project root, so this checkpoint is a file, not a Git commit.
