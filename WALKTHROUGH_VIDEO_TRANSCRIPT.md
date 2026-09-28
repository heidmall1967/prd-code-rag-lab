# PRD Code RAG Lab walkthrough video

Captioned, silent video. Captured lab results: 2026-09-28.

## 1. The local learning lab

Open LEARNING_WALKTHROUGH.html. It is an interactive guide to the PRD search workflow.

## 2. Build a PRD search

Enter a line item, choose distinctive terms and a repository, then copy the generated CLI command. The page does not execute it.

## 3. Get ready

Bootstrap clones three pinned repositories, builds nine SQLite indexes, and runs tests and retrieval checks. Ollama is optional.

```text
$ bash bootstrap.sh
# On this checkout:
$ python3 -m unittest discover -s tests -q
Ran 15 tests in 0.298s
OK
```

## 4. Inspect roles

The learner can search requirements, code and tests. The observer can search requirements only; the auditor can run offline cases.

```text
$ python3 lab.py roles
learner  → analyst: discover, run, call_model, write_trace
observer → viewer: discover requirements
auditor  → auditor: discover, run, write_trace
```

## 5. Discover a requirement

A lexical result points to the pinned Pluggy documentation at exact source lines. It is a candidate to inspect.

```text
$ python3 lab.py discover --repo pluggy --kind requirement \
    --query firstresult --limit 2
First result only
docs/index.rst:671-688 @ 54fb4dd
```

## 6. Correlate three indexes

The same query searches requirements, code and tests. Shared terms and symbol references suggest links; they do not prove the claim.

```text
$ python3 lab.py correlate --repo scorecard \
    --query 'force push' --limit 3
requirement  docs/checks.md:88-90
code         blocksForcePushOnBranches.Run:40-82
test         blocksForcePushOnBranches.Test_Run:29-175
warning      Lexical candidates only
```

## 7. Measure retrieval

Five hand reviewed targets give recall at five of 0.8. The direct Pluggy test ranks eighth, outside the first five results.

```text
$ python3 benchmark_retrieval.py
pluggy execution       rank 1
pluggy docs            rank 1
pluggy direct test     rank 8
httpx default constant rank 1
scorecard force probe  rank 1
recall_at_k: 0.8    mrr_at_20: 0.825
```

## 8. Verify and decide offline

A curated case names exact citations. The runner checks the pinned commit and lines, builds a bounded packet, then applies the registered proof.

```text
$ python3 lab.py run --case cases/pluggy_firstresult.json \
    --mode offline
4 verified citations; context 3493/5000
implementation: supports
direct_test_status: established
Evaluation: PASS
```

## 9. Six case outcomes

PASS means the final labels match each case answer key. A false claim can correctly pass with a contradicts label.

```text
HTTPX 5s default       supports     not_established
HTTPX 10s claim        contradicts  not_established
Scorecard Tier 1       supports     established
Pluggy scalar          supports     established
Pluggy list claim      contradicts  not_established
Pluggy related test    supports     not_established
```

## 10. Local model and guardrail

The local Qwen2.5 reviewer supported the false list claim. The critic questioned its test, and the source based guardrail returned contradicts.

```text
$ python3 lab.py run --case cases/pluggy_firstresult_list.json \
    --mode local
Reviewer: supports / established
Critic: test not_established
Model disagreements: 2
Final: contradicts / not_established
Evaluation: PASS
```

## 11. Role boundary

The observer cannot read code evidence through this CLI. This is an educational application permission check.

```text
$ python3 lab.py discover --repo pluggy --kind code \
    --query firstresult --principal observer
Lab error: RBAC denied: observer cannot read code evidence
exit code: 2
```

## 12. Context budget boundary

The Scorecard packet needs 4,278 characters. A 2,000 character budget rejects it instead of silently dropping evidence.

```text
$ python3 lab.py run \
    --case cases/scorecard_branch_protection.json \
    --budget 2000
Lab error: Context budget exceeded: 4278/2000 characters
exit code: 2
```

## 13. Audit the trace

Every case writes a JSON trace under runs. Inspect citations, packet hash, model opinions, disagreements, final labels and evaluation_pass.

```text
$ python3 lab.py run --case cases/pluggy_firstresult.json \
    --mode offline
Trace: runs/pluggy.firstresult.scalar-....json

repo  commit  citations  context_chars  packet_sha256
model_opinions  disagreements  final  evaluation_pass
```

## 14. What the lab proves

The six registered cases have narrow source based checks. New claims can be searched, but they need reviewed citations and a registered proof for a supported verdict.

```text
Open LEARNING_WALKTHROUGH.html
Read README.md and GUIDE.md
Run python3 lab.py --help
```
