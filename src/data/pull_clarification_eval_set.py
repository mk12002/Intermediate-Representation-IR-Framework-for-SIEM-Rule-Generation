"""Pulls a fresh, complexity-stratified real held-out set for the
clarification-on/off measurement (PROJECT_STATUS.md §4AG) — Phase A of
that round, fully mechanical and human-free.

Pool: data/raw/detections_raw.jsonl + solutions_raw.jsonl + hunting_raw.jsonl
(already locally cloned from Azure/Azure-Sentinel, confirmed via web
search 2026-06-30 to still be the active, canonical, MIT-licensed
source — no new clone needed), filtered to rule_ids NOT already used
in pairs_verified.jsonl (tuning), eval/held_out_test.json (the
existing held-out set), or eval/construct_coverage_test.json.

93 fresh candidates exist after that filter. Complexity-tagged with
`src/data/tag_complexity.py`'s EXISTING heuristic (filter count /
aggregation / join presence) rather than a new one, per the explicit
instruction to use the same structural heuristic the scorecard already
uses. Distribution found: complex=82, moderate=9, simple=2 — the same
skew this project's own §2.1 finding already documented (Hunting
Queries/Solutions trend multi-filter); reported honestly here rather
than papered over by hand-relabeling borderline cases into "simple."

Usage:
    python -m src.data.pull_clarification_eval_set
"""
import json
import random
from pathlib import Path

from src.data.tag_complexity import tag_complexity

_OUTPUT = Path("eval/clarification_eval_set.json")
_SEED = 42
_TARGET_N = 50


def _load_jsonl(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def _load_used_ids() -> set:
    pairs_verified = _load_jsonl("data/processed/pairs_verified.jsonl")
    used = {p.get("rule_id") for p in pairs_verified}
    for path in ("eval/held_out_test.json", "eval/construct_coverage_test.json"):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            used |= {d.get("rule_id") for d in data}
        except FileNotFoundError:
            pass
    return used


def main():
    pool = (
        _load_jsonl("data/raw/detections_raw.jsonl")
        + _load_jsonl("data/raw/solutions_raw.jsonl")
        + _load_jsonl("data/raw/hunting_raw.jsonl")
    )
    used_ids = _load_used_ids()

    fresh = [
        p for p in pool
        if p.get("rule_id") not in used_ids
        and len((p.get("description_raw") or "").strip()) >= 20
        and "{{" not in (p.get("query") or "")
        # Found live: 15/50 of the first pull (30%) were "this query has
        # been deprecated, IoCs are outdated" boilerplate -- identical
        # text repeated across many rule_ids, not a real varied
        # detection description, and a degenerate test case either way
        # (the "correct" behavior for a stale-IoC rule is arguably to
        # abstain, which tests nothing new). Excluded explicitly rather
        # than left in and silently inflating the sample.
        and "deprecated" not in (p.get("description_raw") or "").lower()
    ]

    by_tier = {"simple": [], "moderate": [], "complex": []}
    for p in fresh:
        by_tier[tag_complexity(p["query"])].append(p)

    print("fresh candidate pool:", len(fresh))
    print("tier distribution:", {k: len(v) for k, v in by_tier.items()})

    random.seed(_SEED)
    for tier in by_tier:
        random.shuffle(by_tier[tier])

    # Take every simple/moderate candidate (the pool is too thin to
    # subsample), fill the remainder with a random complex sample —
    # stated honestly as the dataset's own property, not retuned to
    # force an even 3-way split that the real pool doesn't support.
    selected = list(by_tier["simple"]) + list(by_tier["moderate"])
    remaining_budget = max(0, _TARGET_N - len(selected))
    selected += by_tier["complex"][:remaining_budget]

    out = []
    for p in selected:
        desc = (p.get("description_raw") or "").strip().strip("'\"")
        out.append({
            "rule_id": p["rule_id"],
            "nl_description": desc,
            "ground_truth_kql": p["query"],
            "complexity_tier": tag_complexity(p["query"]),
            "source_file": p.get("source_file"),
        })

    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    final_counts = {}
    for o in out:
        final_counts[o["complexity_tier"]] = final_counts.get(o["complexity_tier"], 0) + 1
    print(f"\nwrote {len(out)} cases to {_OUTPUT}")
    print("final tier distribution:", final_counts)


if __name__ == "__main__":
    main()
