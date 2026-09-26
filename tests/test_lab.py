"""Cross-layer regression tests for the local evidence workflow."""

import copy
import io
import importlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lab_core
from benchmark_retrieval import measure
from lab import ask_local_model
from lab_core import (ROOT, EvidenceStore, LabError, authorize, build_packet,
                      case_references, correlate_candidates, handoff, load_case,
                      load_policy, safe_source)
from lab_guards import prove


class LabWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy()
        if any(not (ROOT / f"data/{repo}/.git").exists()
               for repo in ("httpx", "scorecard", "pluggy")):
            raise unittest.SkipTest("Pinned source repositories are not checked out")

    def evidence_for(self, filename):
        case = load_case(ROOT / "cases" / filename)
        repo = case.get("repo", case["id"].split(".", 1)[0])
        store = EvidenceStore(self.policy, repo)
        evidence = [store.fetch(kind, ref) for kind, ref in case_references(case)]
        return case, store, evidence

    def test_four_curated_claims_have_distinct_verdicts(self):
        positive, store, evidence = self.evidence_for("default_timeout.json")
        result = prove(positive, store.repo, evidence)
        self.assertEqual((result.implementation, result.direct_test_status),
                         ("supports", "not_established"))

        negative, store, evidence = self.evidence_for("default_timeout_ten.json")
        result = prove(negative, store.repo, evidence)
        self.assertEqual((result.implementation, result.direct_test_status),
                         ("contradicts", "not_established"))

        scorecard, store, evidence = self.evidence_for(
            "scorecard_branch_protection.json"
        )
        result = prove(scorecard, store.repo, evidence)
        self.assertEqual((result.implementation, result.direct_test_status),
                         ("supports", "established"))

        pluggy, store, evidence = self.evidence_for("pluggy_firstresult.json")
        result = prove(pluggy, store.repo, evidence)
        self.assertEqual((result.implementation, result.direct_test_status),
                         ("supports", "established"))

    def test_scorecard_test_runner_is_required_for_direct_test(self):
        case, store, evidence = self.evidence_for(
            "scorecard_branch_protection.json"
        )
        without_runner = [item for item in evidence
                          if not (item.kind == "test" and item.focus_start == 410)]
        result = prove(case, store.repo, without_runner)
        self.assertEqual(result.implementation, "supports")
        self.assertEqual(result.direct_test_status, "not_established")

    def test_reusing_case_id_for_a_different_claim_fails_closed(self):
        case, store, evidence = self.evidence_for("default_timeout.json")
        case["claim"] = "New HTTPX clients use a one-second timeout by default."
        result = prove(case, store.repo, evidence)
        self.assertEqual((result.implementation, result.direct_test_status),
                         ("insufficient", "undetermined"))

    def test_pluggy_needs_both_cited_tests_for_direct_status(self):
        case, store, evidence = self.evidence_for("pluggy_firstresult.json")
        reduced = [item for item in evidence
                   if item.label != "test_call_none_is_no_result"]
        result = prove(case, store.repo, reduced)
        self.assertEqual(result.implementation, "supports")
        self.assertEqual(result.direct_test_status, "not_established")

    def test_adversarial_pluggy_cases_keep_claim_and_test_separate(self):
        false_claim, store, evidence = self.evidence_for(
            "pluggy_firstresult_list.json")
        verdict = prove(false_claim, store.repo, evidence)
        self.assertEqual((verdict.implementation, verdict.direct_test_status),
                         ("contradicts", "not_established"))

        related_test, store, evidence = self.evidence_for(
            "pluggy_firstresult_related_test.json")
        verdict = prove(related_test, store.repo, evidence)
        self.assertEqual((verdict.implementation, verdict.direct_test_status),
                         ("supports", "not_established"))

    def test_retrieval_benchmark_surfaces_pluggy_execution_logic(self):
        examples = json.loads((ROOT / "benchmarks/retrieval.json").read_text())
        report = measure(self.policy, examples)
        ranks = {row["id"]: row["rank"] for row in report["examples"]}
        self.assertEqual(ranks["pluggy-execution"], 1)
        self.assertGreaterEqual(report["recall_at_k"], 0.8)
        self.assertEqual(len(report["examples"]), len(examples))

    def test_pinned_pluggy_runtime_skips_none_and_stops(self):
        source = str((ROOT / "data/pluggy/src").resolve())
        sys.path.insert(0, source)
        try:
            pluggy = importlib.import_module("pluggy")
            self.assertTrue(Path(pluggy.__file__).resolve().is_relative_to(
                (ROOT / "data/pluggy").resolve()
            ))
            hookspec = pluggy.HookspecMarker("lab-firstresult")
            hookimpl = pluggy.HookimplMarker("lab-firstresult")
            calls = []

            class Spec:
                @hookspec(firstresult=True)
                def result(self, value):
                    pass

            class Later:
                @hookimpl
                def result(self, value):
                    calls.append("later")
                    return 99

            class Answer:
                @hookimpl
                def result(self, value):
                    calls.append("answer")
                    return value + 1

            class NoneResult:
                @hookimpl
                def result(self, value):
                    calls.append("none")
                    return None

            manager = pluggy.PluginManager("lab-firstresult")
            manager.add_hookspecs(Spec)
            manager.register(Later())
            manager.register(Answer())
            manager.register(NoneResult())
            self.assertEqual(manager.hook.result(value=1), 2)
            self.assertEqual(calls, ["none", "answer"])
        finally:
            sys.path.pop(0)

    def test_context_budget_fails_closed(self):
        case, _, evidence = self.evidence_for("scorecard_branch_protection.json")
        with self.assertRaisesRegex(LabError, "Context budget exceeded"):
            build_packet(case, evidence, 100)

    def test_role_and_agent_boundaries(self):
        authorize(self.policy, "observer", "discover", "requirement")
        with self.assertRaisesRegex(LabError, "cannot read code"):
            authorize(self.policy, "observer", "discover", "code")
        with self.assertRaisesRegex(LabError, "cannot run"):
            authorize(self.policy, "observer", "run")
        with self.assertRaisesRegex(LabError, "cannot call_model"):
            authorize(self.policy, "auditor", "call_model")
        with self.assertRaisesRegex(LabError, "handoff denied"):
            handoff(self.policy, [], "retriever", "adjudicator", "raw data")

    def test_path_and_commit_boundaries(self):
        repo = (ROOT / "data/httpx").resolve()
        with self.assertRaisesRegex(LabError, "Invalid source path"):
            safe_source(repo, "../../.git/config")
        wrong_policy = copy.deepcopy(self.policy)
        wrong_policy["repositories"]["httpx"]["commit"] = "0" * 40
        with self.assertRaisesRegex(LabError, "differs from policy"):
            EvidenceStore(wrong_policy, "httpx")

    def test_tampered_index_text_is_rejected(self):
        case = load_case(ROOT / "cases/default_timeout.json")
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            (tmp / "data").mkdir()
            (tmp / "indexes").mkdir()
            (tmp / "data/httpx").symlink_to(
                (ROOT / "data/httpx").resolve(), target_is_directory=True
            )
            database = tmp / "indexes/requirements.sqlite"
            shutil.copy2(ROOT / "indexes/requirements.sqlite", database)
            with sqlite3.connect(database) as db:
                db.execute(
                    "UPDATE requirements SET body = ? "
                    "WHERE path = ? AND start_line = ?",
                    ("tampered evidence", "docs/advanced/timeouts.md", 30),
                )
            with patch.object(lab_core, "ROOT", tmp):
                store = EvidenceStore(self.policy, "httpx")
                with self.assertRaisesRegex(LabError, "differs from source"):
                    store.fetch("requirement", case["requirement"])

    def test_line_range_disambiguates_repeated_symbol(self):
        store = EvidenceStore(self.policy, "httpx")
        with sqlite3.connect(ROOT / "indexes/code.sqlite") as db:
            rows = db.execute(
                "SELECT start_line, end_line FROM code "
                "WHERE path = ? AND symbol = ?",
                ("httpx/_client.py", "BaseClient.timeout"),
            ).fetchall()
        self.assertGreaterEqual(len(rows), 2)
        for first, last in rows:
            item = store.fetch("code", {
                "path": "httpx/_client.py", "symbol": "BaseClient.timeout",
                "start_line": int(first), "end_line": int(last),
            })
            self.assertEqual((item.first, item.last), (int(first), int(last)))

    def test_cross_index_query_finds_reference_chain(self):
        store = EvidenceStore(self.policy, "httpx")
        result = correlate_candidates(store, "default timeout", limit=3)
        self.assertTrue(all(result["candidates"][kind]
                            for kind in ("requirement", "code", "test")))
        self.assertTrue(any("DEFAULT_TIMEOUT_CONFIG" in link["symbol"]
                            and "httpx/_client.py:639-716" in link["to"]
                            for link in result["symbol_references"]))
        pluggy = correlate_candidates(
            EvidenceStore(self.policy, "pluggy"), "firstresult", limit=3
        )
        self.assertTrue(all(pluggy["candidates"][kind]
                            for kind in ("requirement", "code", "test")))
        self.assertFalse(any(link["symbol"] == "_manager"
                             for link in pluggy["symbol_references"]))

    def test_nonlocal_model_endpoint_is_rejected(self):
        bad = copy.deepcopy(self.policy)
        bad["model"]["url"] = "https://example.com/api/chat"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(LabError, "only the local Ollama"):
                load_policy(path)

    def test_malformed_model_verdict_cannot_become_a_label(self):
        response = io.BytesIO(json.dumps({
            "message": {"content": json.dumps({
                "implementation": {"unexpected": "object"},
                "direct_test_status": "established",
            })}
        }).encode())
        with patch("lab.urllib.request.build_opener") as build:
            build.return_value.open.return_value = response
            verdict = ask_local_model(
                self.policy, "review", "evidence",
                {"implementation": {"supports"},
                 "direct_test_status": {"established", "not_established"}},
            )
        self.assertIn("invalid_response", verdict)


if __name__ == "__main__":
    unittest.main()
