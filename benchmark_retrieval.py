"""Measure lexical retrieval of hand-reviewed evidence from pinned sources."""

import argparse
import json
from pathlib import Path

from lab_core import ROOT, EvidenceStore, authorize, load_policy


def measure(policy, examples, limit=5):
    """Return per-example ranks plus recall and reciprocal-rank metrics."""
    if not examples:
        raise ValueError("Benchmark has no examples")
    if not 1 <= limit <= 20:
        raise ValueError("Limit must be between 1 and 20")
    rows = []
    for example in examples:
        authorize(policy, "learner", "discover", example["kind"])
        store = EvidenceStore(policy, example["repo"])
        target = store.fetch(example["kind"], example["target"])
        candidates = store.search(example["kind"], example["query"], 20)
        rank = next((position for position, row in enumerate(candidates, 1)
                     if (row["path"], row["start_line"], row["end_line"])
                     == (target.path, target.first, target.last)), None)
        rows.append({"id": example["id"], "rank": rank,
                     "in_top_k": rank is not None and rank <= limit,
                     "target": target.citation})
    return {"k": limit, "examples": rows,
            "recall_at_k": sum(row["in_top_k"] for row in rows) / len(rows),
            "mrr_at_20": sum(1 / row["rank"] for row in rows
                             if row["rank"] is not None) / len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--fixture", type=Path,
                        default=ROOT / "benchmarks/retrieval.json")
    args = parser.parse_args()
    examples = json.loads(args.fixture.read_text(encoding="utf-8"))
    print(json.dumps(measure(load_policy(), examples, args.limit), indent=2))


if __name__ == "__main__":
    main()
