# Phase 2 — correlate a new PRD line with code and tests

## Goal

Given a line item in a pinned, open-source PRD or requirements document,
the user selects it and receives ranked code and test candidates from a
different source index, with verifiable citations. The workflow then gives a
cautious evidence assessment. It must say **insufficient evidence / needs
review** when the selected passages do not justify a stronger conclusion.

This is planned work. The current `correlate` command accepts text as a search
query, but does not index an arbitrary PRD, select evidence for a new claim, or
prove that claim. The six existing cases use hand-reviewed citations and
claim-specific deterministic proofs. See [GUIDE.md](GUIDE.md) for the current
workflow.

## Build order

1. **Add an independent requirements source.** Choose a genuinely open-source
   PRD or equivalent project requirements document with a clear license and a
   pinned revision. Record its URL, license, revision, and relationship to the
   implementation repository. Keep downloaded source under ignored `data/`.
   Parse individual, stable line items into a requirements index; retain path,
   start/end lines, source hash, and revision for every record. Rebuilding the
   index must produce the same records from the pinned source.
2. **Retrieve across sources.** Add a command that takes a requirement record
   ID, not just free-text keywords, and searches the selected code and test
   indexes. Show candidate ranks and the terms or symbol links responsible for
   them. Support an explicit pairing between the PRD source and a target code
   repository; do not silently mix evidence from unrelated revisions.
3. **Verify and assemble evidence.** Re-read every candidate from its pinned
   source and check its path, line range, hash, and revision before displaying
   or sending it to a model. Build a bounded packet containing the exact PRD
   line, candidate code, and candidate tests. Treat retrieved text as untrusted
   data, including instructions embedded in documents or comments.
4. **Assess conservatively.** Separate three questions: whether code appears
   related, whether it supports or contradicts the complete requirement, and
   whether a cited test directly asserts that behavior. Return citations and
   an explicit uncertainty state. A model may suggest an assessment, but a
   confident model response alone must not become a verified proof. Human
   review remains necessary for claims without a narrow checkable rule.
5. **Evaluate the new workflow.** Create a small, hand-labeled open-source
   set with clear matches, nonmatches, incomplete implementations, misleading
   keyword overlaps, and tests that are only related. Measure retrieval
   separately from evidence labels. Add regression checks for stale citations,
   wrong repository/revision, prompt-injection text, and insufficient evidence.
   Report false support and false direct-test claims, not just overall PASS.
6. **Teach it.** Extend the HTML walkthrough and README with a complete
   PRD-line example: select the line, inspect ranked candidates, read cited
   source, compare the assessment with the answer key, and explain each eval.

## Phase 2 acceptance checks

- A fresh clone plus bootstrap can reproduce the new open-source PRD index
  and its paired code/test indexes from documented pinned revisions.
- A user can choose a PRD record and run one command to see citable code and
  test candidates without creating a case JSON by hand.
- Each displayed citation resolves to the exact pinned source lines; altered
  or stale evidence fails before assessment.
- At least one known match, one nonmatch, one partial match, and one
  related-but-not-direct test are demonstrated end to end in the walkthrough.
- The evaluation reports retrieval ranking and evidence-label accuracy as
  separate results, including failures. Unproven claims remain visibly
  uncertain rather than being presented as verified.
- The documented path works on the target Ubuntu machine in offline mode;
  optional local-model mode stays within the existing resource budget.

This phase does not require a browser application, embeddings, paid APIs, or
operating-system RBAC. Those are separate possible extensions.
