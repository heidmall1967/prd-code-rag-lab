"""Narrow, deterministic proofs for the two curated learning cases.

These checks establish only their named claims. New cases must get their own
proofs; a model verdict alone never turns an unrecognized claim into a fact.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from evidence_guard import has_client_call_without_timeout
from lab_core import Evidence


@dataclass(frozen=True)
class Proof:
    implementation: str
    direct_test_status: str
    reasons: list[str]


def _httpx_default_value(repo: Path) -> bool:
    tree = ast.parse((repo / "httpx/_config.py").read_text(encoding="utf-8"))
    assignments = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name)
                and target.id == "DEFAULT_TIMEOUT_CONFIG"
                for target in node.targets)
    ]
    if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Call):
        return False
    call = assignments[0].value
    if not isinstance(call.func, ast.Name) or call.func.id != "Timeout":
        return False
    return any(keyword.arg == "timeout"
               and isinstance(keyword.value, ast.Constant)
               and keyword.value.value == 5.0
               for keyword in call.keywords)


def _httpx_client_defaults(repo: Path) -> bool:
    tree = ast.parse((repo / "httpx/_client.py").read_text(encoding="utf-8"))
    for class_name in ("Client", "AsyncClient"):
        classes = [node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == class_name]
        if len(classes) != 1:
            return False
        constructors = [node for node in classes[0].body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "__init__"]
        if len(constructors) != 1:
            return False
        fn = constructors[0]
        defaults = dict(zip(
            (argument.arg for argument in fn.args.kwonlyargs),
            fn.args.kw_defaults,
        ))
        timeout = defaults.get("timeout")
        if not isinstance(timeout, ast.Name) or timeout.id != "DEFAULT_TIMEOUT_CONFIG":
            return False
    return True


def _httpx_proof(repo: Path, evidence: list[Evidence],
                 claimed_seconds: float) -> Proof:
    labels = {item.label for item in evidence if item.kind == "code"}
    required = {"DEFAULT_TIMEOUT_CONFIG", "Client.__init__", "AsyncClient.__init__"}
    established_five_seconds = (required <= labels
                                and _httpx_default_value(repo)
                                and _httpx_client_defaults(repo))
    if not established_five_seconds:
        implementation = "insufficient"
    elif claimed_seconds == 5.0:
        implementation = "supports"
    else:
        implementation = "contradicts"

    tests = [item.body for item in evidence if item.kind == "test"]
    try:
        possible_direct = any(has_client_call_without_timeout(body)
                              for body in tests)
    except SyntaxError:
        possible_direct = True
    if possible_direct:
        direct = "undetermined"
        test_reason = ("A cited test constructs a client without an explicit timeout; "
                       "a stronger assertion check is needed before calling it direct.")
    else:
        direct = "not_established"
        test_reason = "No cited test constructs a client without an explicit timeout."
    return Proof(implementation, direct, [
        ("AST establishes a 5.0-second default in both clients, which "
         f"{'matches' if implementation == 'supports' else 'contradicts'} "
         f"the claimed {claimed_seconds:g}-second default.")
        if established_five_seconds else
        "The cited code or required AST relationship is missing.",
        test_reason,
    ])


def _scorecard_proof(evidence: list[Evidence]) -> Proof:
    docs = "\n".join(item.excerpt for item in evidence
                     if item.kind == "requirement")
    code = {item.label: item.excerpt for item in evidence
            if item.kind == "code"}
    required_code = {
        "blocksForcePushOnBranches.Run",
        "evaluation.BranchProtection",
        "evaluation.deleteAndForcePushProtection",
        "evaluation.basicLevel",
        "evaluation.computeFinalScore",
    }
    anchors = (
        "Tier 1 Requirements (3/10 points)" in docs
        and "Prevent force push" in docs
        and "Prevent branch deletion" in docs
        and required_code <= code.keys()
    )
    if anchors:
        probe = code["blocksForcePushOnBranches.Run"]
        dispatch = code["evaluation.BranchProtection"]
        helper = code["evaluation.deleteAndForcePushProtection"]
        constant = code["evaluation.basicLevel"]
        final = code["evaluation.computeFinalScore"]
        anchors = all((
            "AllowForcePushes" in probe and "OutcomeTrue" in probe
            and "OutcomeFalse" in probe,
            "blocksDeleteOnBranches.Probe" in dispatch
            and "blocksForcePushOnBranches.Probe" in dispatch
            and "deleteAndForcePushProtection" in dispatch,
            "f.Outcome == finding.OutcomeTrue" in helper
            and "score++" in helper and "maxScore++" in helper,
            bool(re.search(r"\bbasicLevel\s*=\s*3\b", constant)),
            "basicScore := sumUpScoreForTier(Tier1, scores)" in final
            and "normalizeScore(basicScore, maxBasicScore, basicLevel)" in final,
        ))
    implementation = "supports" if anchors else "insufficient"

    case_excerpts = [item.excerpt for item in evidence if item.kind == "test"
                     and item.label == "evaluation.TestBranchProtection"]
    case_block = next((text for text in case_excerpts
                       if 'Admin run only preventing force pushes and deletions' in text), "")
    runner = next((text for text in case_excerpts
                   if "got := BranchProtection" in text), "")
    direct = all((
        'branchFinding(blocksDeleteOnBranches.Probe, "main", finding.OutcomeTrue)' in case_block,
        'branchFinding(blocksForcePushOnBranches.Probe, "main", finding.OutcomeTrue)' in case_block,
        bool(re.search(r"\bScore:\s*3\b", case_block)),
        "got := BranchProtection(tt.name, tt.findings, &dl)" in runner,
        "scut.ValidateTestReturn" in runner,
    ))
    return Proof(implementation,
                 "established" if direct else "not_established", [
        "The cited Go branches, tier constant, and score calculation match the Tier 1 claim."
        if anchors else "Required Scorecard implementation anchors are missing.",
        "The cited table case expects 3 and the cited runner checks its result."
        if direct else "The cited test excerpts do not establish both case and runner.",
    ])


def _pluggy_ast_proves_first_result(repo: Path) -> bool:
    tree = ast.parse((repo / "src/pluggy/_execution.py").read_text(encoding="utf-8"))
    functions = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name == "_multicall"]
    if len(functions) != 1:
        return False
    function = functions[0]

    def name(node, value):
        return isinstance(node, ast.Name) and node.id == value

    stop_after_value = False
    scalar_return = False
    for node in ast.walk(function):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            check = node.test
            if (name(check.left, "res") and len(check.ops) == 1
                    and isinstance(check.ops[0], ast.IsNot)
                    and len(check.comparators) == 1
                    and isinstance(check.comparators[0], ast.Constant)
                    and check.comparators[0].value is None):
                appends = any(
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and name(child.func.value, "results")
                    and child.func.attr == "append"
                    and len(child.args) == 1 and name(child.args[0], "res")
                    for statement in node.body for child in ast.walk(statement)
                )
                stops = any(
                    isinstance(statement, ast.If)
                    and name(statement.test, "firstresult")
                    and any(isinstance(child, ast.Break)
                            for child in statement.body)
                    for statement in node.body
                )
                stop_after_value = appends and stops
        if isinstance(node, ast.If) and name(node.test, "firstresult"):
            for statement in node.body:
                if not (isinstance(statement, ast.Assign)
                        and any(name(target, "result")
                                for target in statement.targets)
                        and isinstance(statement.value, ast.IfExp)):
                    continue
                value = statement.value
                scalar_return = (
                    name(value.test, "results")
                    and isinstance(value.body, ast.Subscript)
                    and name(value.body.value, "results")
                    and isinstance(value.body.slice, ast.Constant)
                    and value.body.slice.value == 0
                    and isinstance(value.orelse, ast.Constant)
                    and value.orelse.value is None
                )
    return stop_after_value and scalar_return


def _pluggy_proof(repo: Path, evidence: list[Evidence]) -> Proof:
    docs = "\n".join(item.excerpt for item in evidence
                     if item.kind == "requirement")
    code = next((item.excerpt for item in evidence
                 if item.kind == "code"
                 and item.label == "_execution._multicall"), "")
    implementation = all((
        "first *hookimpl* which returns a result other" in docs,
        "than ``None``" in docs,
        "@hookspec(firstresult=True)" in docs,
        "if res is not None:" in code,
        "if firstresult:" in code,
        "result = results[0] if results else None" in code,
        _pluggy_ast_proves_first_result(repo),
    ))
    tests = {item.label: item.excerpt for item in evidence if item.kind == "test"}
    invocation = tests.get("test_firstresult_definition", "")
    multicall = tests.get("test_call_none_is_no_result", "")
    direct = all((
        "@hookspec(firstresult=True)" in invocation,
        "return None" in invocation,
        "return arg - 1" in invocation,
        "res = pm.hook.hello(arg=3)" in invocation,
        "assert res == 2" in invocation,
        "firstresult=True" in multicall,
        "assert res == 1" in multicall,
        "firstresult=False" in multicall,
        "assert res == [1]" in multicall,
    ))
    return Proof("supports" if implementation else "insufficient",
                 "established" if direct else "not_established", [
        "Pinned AST and cited lines show None is skipped and the first result is returned as a scalar."
        if implementation else "Pluggy implementation proof is incomplete.",
        "Cited invocation and multicall tests check the scalar result and None handling."
        if direct else "The cited tests do not establish the scalar result and None handling.",
    ])


def prove(case: dict, repo: Path, evidence: list[Evidence]) -> Proof:
    registered = {
        "httpx.default_timeout": (
            "httpx", "New HTTPX clients use a five-second timeout by default."
        ),
        "httpx.default_timeout_ten": (
            "httpx", "New HTTPX clients use a ten-second timeout by default."
        ),
        "scorecard.branch_protection.tier1": (
            "scorecard",
            "When force-push and deletion probes both report protection, "
            "Scorecard awards the Branch-Protection Tier 1 score of 3."
        ),
        "pluggy.firstresult.scalar": (
            "pluggy",
            "A Pluggy hook marked firstresult=True returns the first non-None "
            "implementation result as a single value."
        ),
    }
    identity = registered.get(case["id"])
    if identity is None or case.get("repo", case["id"].split(".", 1)[0]) != identity[0] \
            or case["claim"] != identity[1]:
        return Proof("insufficient", "undetermined", [
            "No deterministic proof is registered for this exact claim and repository."
        ])
    if case["id"] == "httpx.default_timeout":
        return _httpx_proof(repo, evidence, 5.0)
    if case["id"] == "httpx.default_timeout_ten":
        return _httpx_proof(repo, evidence, 10.0)
    if case["id"] == "scorecard.branch_protection.tier1":
        return _scorecard_proof(evidence)
    if case["id"] == "pluggy.firstresult.scalar":
        return _pluggy_proof(repo, evidence)
    raise AssertionError("Registered case has no proof")
