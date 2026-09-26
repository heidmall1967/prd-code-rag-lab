"""Policy, provenance, retrieval, and context construction for the lab."""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
TABLES = {"requirement": "requirements", "code": "code", "test": "tests"}
KEYS = {"httpx": {"code": "symbol", "test": "name"},
        "scorecard": {"code": "symbol", "test": "symbol"},
        "pluggy": {"code": "symbol", "test": "name"}}


class LabError(Exception):
    """A failed policy or evidence check, reported without a stack trace by the CLI."""


@dataclass(frozen=True)
class Evidence:
    kind: str
    path: str
    label: str
    first: int
    last: int
    focus_start: int
    focus_end: int
    body: str
    excerpt: str
    commit: str

    @property
    def citation(self) -> str:
        return f"{self.path}:{self.focus_start}-{self.focus_end} @ {self.commit[:7]}"


def load_policy(path: Path = ROOT / "policy.json") -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("version") != 1 or policy.get("max_context_chars", 0) < 100:
        raise LabError("Unsupported or invalid policy")
    model_url = urlparse(policy["model"]["url"])
    if model_url.geturl() != "http://127.0.0.1:11434/api/chat":
        raise LabError("Policy permits only the local Ollama chat endpoint")
    return policy


def authorize(policy: dict, principal: str, action: str,
              kind: str | None = None) -> None:
    role_name = policy["principals"].get(principal)
    role = policy["roles"].get(role_name, {})
    if action not in role.get("actions", []):
        raise LabError(f"RBAC denied: {principal} cannot {action}")
    if kind is not None and kind not in role.get("sources", []):
        raise LabError(f"RBAC denied: {principal} cannot read {kind} evidence")


def handoff(policy: dict, events: list[dict], sender: str,
            receiver: str, artifact: str) -> None:
    if receiver not in policy["agent_handoffs"].get(sender, []):
        raise LabError(f"Agent handoff denied: {sender} -> {receiver}")
    events.append({"sender": sender, "receiver": receiver, "artifact": artifact})


def load_case(path: str | Path) -> dict:
    resolved = Path(path).resolve()
    cases_root = (ROOT / "cases").resolve()
    if not resolved.is_relative_to(cases_root):
        raise LabError("Case file must be inside cases/")
    case = json.loads(resolved.read_text(encoding="utf-8"))
    for key in ("id", "commit", "claim", "requirement", "implementation"):
        if key not in case:
            raise LabError(f"Case missing {key}")
    if not re.fullmatch(r"[a-z0-9_.-]+", case["id"]):
        raise LabError("Invalid case id")
    if not re.fullmatch(r"[0-9a-f]{7,40}", case["commit"]):
        raise LabError("Invalid case commit")
    return case


def case_repo(case: dict, policy: dict) -> str:
    name = case.get("repo", case["id"].split(".", 1)[0])
    if name not in policy["repositories"]:
        raise LabError(f"Repository is not allowed: {name}")
    return name


def case_references(case: dict) -> list[tuple[str, dict]]:
    tests = case.get("tests", case.get("related_tests", []))
    return ([('requirement', case['requirement'])]
            + [('code', ref) for ref in case['implementation']]
            + [('test', ref) for ref in tests])


def safe_source(repo: Path, relative: str) -> Path:
    candidate = (repo / relative).resolve()
    if not candidate.is_relative_to(repo) or not candidate.is_file():
        raise LabError(f"Invalid source path: {relative}")
    return candidate


class EvidenceStore:
    def __init__(self, policy: dict, repository: str):
        self.repository = repository
        spec = policy["repositories"][repository]
        self.repo = (ROOT / spec["path"]).resolve()
        if not self.repo.is_dir():
            raise LabError(f"Missing source repository: {self.repo}")
        self.indexes = spec["indexes"]
        try:
            self.commit = subprocess.check_output(
                ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
                text=True, stderr=subprocess.PIPE,
            ).strip()
        except subprocess.CalledProcessError as exc:
            raise LabError(f"Cannot read source commit: {exc.stderr.strip()}") from exc
        if self.commit != spec["commit"]:
            raise LabError(f"Source checkout differs from policy: {repository}")

    def _connect(self, kind: str) -> sqlite3.Connection:
        database = (ROOT / "indexes" / self.indexes[kind]).resolve()
        if not database.is_file():
            raise LabError(f"Missing index: {database}")
        return sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)

    def fetch(self, kind: str, ref: dict) -> Evidence:
        if kind not in TABLES:
            raise LabError(f"Unknown evidence kind: {kind}")
        path = ref["path"]
        source_file = safe_source(self.repo, path)
        table = TABLES[kind]
        if kind == "requirement":
            where = "path = ? AND start_line = ? AND end_line = ?"
            args = (path, ref["start_line"], ref["end_line"])
            label = path
        else:
            key = KEYS[self.repository][kind]
            label = ref[key]
            where = f"path = ? AND {key} = ?"
            args = (path, label)
            if "start_line" in ref and "end_line" in ref:
                where += " AND start_line = ? AND end_line = ?"
                args += (ref["start_line"], ref["end_line"])
        with closing(self._connect(kind)) as db:
            rows = db.execute(
                f"SELECT body, start_line, end_line, commit_sha "
                f"FROM {table} WHERE {where}", args,
            ).fetchall()
        if len(rows) != 1:
            raise LabError(f"Expected one {kind} record for {label}; found {len(rows)}")
        body, first, last, indexed_commit = rows[0]
        if not body or not body.strip():
            raise LabError(f"Empty indexed body for {label}")
        first, last = int(first), int(last)
        lines = source_file.read_text(encoding="utf-8").splitlines()
        if not (1 <= first <= last <= len(lines)):
            raise LabError(f"Invalid indexed line range for {label}")
        source_span = "\n".join(lines[first - 1:last])
        if indexed_commit != self.commit:
            raise LabError(f"Stale index commit for {label}")
        # A Go AST const span ends before an optional inline comment.
        matches = body.strip() == source_span.strip()
        if not matches and self.repository == "scorecard" and kind == "code" \
                and first == last:
            matches = body.strip() == source_span.split("//", 1)[0].strip()
        if not matches:
            raise LabError(f"Indexed text differs from source for {label}")
        start, end = ref.get("focus", [first, last])
        if not (first <= start <= end <= last):
            raise LabError(f"Focus outside indexed lines for {label}")
        excerpt = "\n".join(
            f"{number}: {lines[number - 1]}" for number in range(start, end + 1)
        )
        return Evidence(kind, path, label, first, last, start, end,
                        body, excerpt, self.commit)

    def search(self, kind: str, query: str, limit: int = 5) -> list[dict]:
        if kind not in TABLES:
            raise LabError(f"Unknown evidence kind: {kind}")
        if not 1 <= limit <= 20:
            raise LabError("Search limit must be between 1 and 20")
        terms = re.findall(r"[a-z0-9_]+", query.lower())[:8]
        if not terms:
            raise LabError("Search query has no searchable terms")
        match = " AND ".join(f'"{term}"' for term in terms)
        table = TABLES[kind]
        key = "heading" if kind == "requirement" else KEYS[self.repository][kind]
        with closing(self._connect(kind)) as db:
            rows = db.execute(
                f"SELECT {key}, path, start_line, end_line, commit_sha, "
                f"bm25({table}) FROM {table} WHERE {table} MATCH ? "
                f"ORDER BY bm25({table}) LIMIT ?", (match, limit),
            ).fetchall()
        return [dict(label=r[0], path=r[1], start_line=int(r[2]),
                     end_line=int(r[3]), commit=r[4], score=r[5]) for r in rows]


def build_packet(case: dict, evidence: list[Evidence], budget: int) -> str:
    parts = [f"Claim: {case['claim']}", f"Source commit: {evidence[0].commit}"]
    for item in evidence:
        parts.append(f"{item.kind.title()} | {item.citation}\n{item.excerpt}")
    packet = "\n\n".join(parts)
    if len(packet) > budget:
        raise LabError(f"Context budget exceeded: {len(packet)}/{budget} characters")
    return packet


def _link_terms(value: str) -> set[str]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return set(re.findall(r"[a-z]{3,}", separated.lower()))


def correlate_candidates(store: EvidenceStore, query: str,
                         limit: int = 5) -> dict:
    """Retrieve from all three DBs and suggest lexical links, never proof."""
    terms = list(dict.fromkeys(re.findall(r"[a-z0-9_]+", query.lower())))[:8]
    if not terms:
        raise LabError("Correlation query has no searchable terms")
    if not 1 <= limit <= 20:
        raise LabError("Correlation limit must be between 1 and 20")
    groups: dict[str, list[dict]] = {}
    for kind in TABLES:
        found: dict[tuple, dict] = {}
        for term in terms:
            for row in store.search(kind, term, limit=max(limit, 8)):
                key = (row["path"], row["start_line"], row["end_line"],
                       row["label"])
                if key not in found:
                    ref = {"path": row["path"],
                           "start_line": row["start_line"],
                           "end_line": row["end_line"]}
                    if kind != "requirement":
                        ref[KEYS[store.repository][kind]] = row["label"]
                    item = store.fetch(kind, ref)
                    found[key] = {"evidence": item, "hits": set(),
                                  "best_bm25": row["score"]}
                found[key]["hits"].add(term)
                found[key]["best_bm25"] = min(
                    found[key]["best_bm25"], row["score"]
                )
        ranked = sorted(found.values(), key=lambda item: (
            -len(item["hits"]), item["best_bm25"], item["evidence"].citation
        ))[:limit]
        groups[kind] = ranked

    query_terms = set(terms)
    links = []
    for left_kind, right_kind in (("requirement", "code"), ("code", "test")):
        for left in groups[left_kind]:
            for right in groups[right_kind]:
                left_evidence = left["evidence"]
                right_evidence = right["evidence"]
                shared = sorted(
                    (_link_terms(left_evidence.body + " " + left_evidence.label)
                     & _link_terms(right_evidence.body + " " + right_evidence.label))
                    & query_terms
                )
                if shared:
                    links.append({
                        "from": left_evidence.citation,
                        "to": right_evidence.citation,
                        "shared_query_terms": shared,
                    })
    symbol_references = []
    for seed in groups["code"][:1]:
        label = seed["evidence"].label
        anchor = label.split(".", 1)[0]
        if anchor == Path(seed["evidence"].path).stem:
            # Some indexes prefix symbols with the module name. Following that
            # prefix mostly finds unrelated functions in the same file.
            continue
        if len(anchor) < 8 or not ("_" in anchor or any(c.isupper() for c in anchor)):
            continue
        for row in store.search("code", anchor, limit=20):
            if row["path"] == seed["evidence"].path and row["label"] == label:
                continue
            ref = {"path": row["path"], "symbol": row["label"],
                   "start_line": row["start_line"],
                   "end_line": row["end_line"]}
            target = store.fetch("code", ref)
            symbol_references.append({
                "from": seed["evidence"].citation,
                "to": target.citation,
                "symbol": anchor,
            })
    return {
        "query": query,
        "warning": "Lexical candidates only; inspect and verify a case before judging.",
        "candidates": {
            kind: [
                {"label": item["evidence"].label,
                 "citation": item["evidence"].citation,
                 "matched_terms": sorted(item["hits"])}
                for item in group
            ] for kind, group in groups.items()
        },
        "links": links[:15],
        "symbol_references": symbol_references[:20],
    }
