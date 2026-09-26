# Progress checkpoint — 2026-09-26

## Working agreement

The user writes and runs the project code. The assistant guides one small step at a time, reviews outputs, and does not implement project features on the user's behalf. Use only open-source source data. The lab runs locally on Ubuntu with about 12 GB RAM, 2 GB VRAM, and an older i5; Ollama `qwen2.5:1.5b` is the local reviewer.

## Project goal

Build a from-scratch learning lab that correlates separate requirement, implementation, and test retrieval indexes. Expand it into a study of context engineering, evidence-based guardrails, policy, RBAC, agents, and multi-agent interaction. Current data sources are pinned open-source HTTPX (`b5addb6`, BSD-3-Clause) and OpenSSF Scorecard (`f92023a`, Apache-2.0). The local Qwen2.5 1.5B model is Apache-2.0.

## Completed

- HTTPX indexes: 9 requirement sections, 470 Python code records, 539 test records, each in a separate SQLite FTS5 database.
- HTTPX default-timeout case: provenance, structural implementation check, bounded evidence packet, local model review, and deterministic guardrail. The implementation is supported. The cited tests are related but do not directly establish that a client constructed without a timeout uses the built-in five-second default. The model falsely marked direct testing established; the guardrail corrected it. The user reported `python3 run_case.py` passing and writing `runs/latest.json`.
- Scorecard indexes: 19 Branch-Protection requirement blocks, 33 Go code records, and 5 Go test records. The Go chunks are extracted with a user-written standard-library AST program.
- Scorecard case file `cases/scorecard_branch_protection.json`: one requirement citation, five implementation citations, and two test citations (eight total). The case claims that true force-push and deletion protection findings earn the Tier 1 score of 3.
- The user reported `python3 verify_scorecard.py` passing for the eight current citations. The current script checks record existence, focus-line containment, and pinned commit for all eight; it compares indexed source text for the requirement and code records. The **test loop does not yet compare indexed test text with source**.
- `packet_scorecard.py` renders focused, line-numbered source excerpts. The user reported a size of 3,809 characters for the current eight-citation packet.

## Exact next step

The Scorecard evaluation test has a table case at `checks/evaluation/branch_protection_test.go:118-140` with both relevant probe outcomes true and expected `Score: 3`. Its runner at lines 410-417 calls `BranchProtection(tt.name, tt.findings, &dl)` and `scut.ValidateTestReturn(...)`. The runner excerpt is **not yet in the case JSON** despite the previous instruction.

Guide the user to append a third test citation with the same path and symbol `evaluation.TestBranchProtection`, focus `[410, 417]`. Then have them validate JSON, run `verify_scorecard.py`, and report the new packet length. The case should then have nine citations. After that, guide them to add `body` to the test query in `verify_scorecard.py` and call its existing `verify_source_body(...)` helper inside the test loop.

## Later work

Add a Scorecard reviewer and deterministic checks that distinguish implementation support from direct-test support; run the case end to end and record a trace. Then generalize across cases and add policy, RBAC, and agent roles in small, inspectable steps. Do not confuse a model's explanation with verified evidence.

The user also asked how to switch this session to their ChatGPT Plus plan. That question remains unanswered; verify current official OpenAI guidance before answering it. There is no Git repository at the project root, so this checkpoint is a file, not a Git commit.
