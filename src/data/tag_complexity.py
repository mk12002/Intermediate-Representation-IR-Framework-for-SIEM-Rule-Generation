"""Complexity tagging — docs/NL-KQL/MASTER_PLAN.md §16.2 Step 5.

Automated tagging only. Per the docs, this must be spot-checked manually on
a 20% sample per tier before being trusted — a query can have one filter but
still be conceptually complex (e.g. a single filter against a computed field).

Usage:
    python -m src.data.tag_complexity --input data/raw/detections_raw.jsonl \
        --output data/processed/pairs_tagged.jsonl
"""
import argparse
import json
from pathlib import Path


def _top_level_comma_count(text: str) -> int:
    """Count commas at paren-depth 0 only, so a function call's internal
    comma (e.g. `bin(TimeGenerated, 10m)`) isn't mistaken for an additional
    group-by key."""
    depth = 0
    commas = 0
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            commas += 1
    return commas


def tag_complexity(query: str) -> str:
    """v2 — revised 2026-06-22 after manually reviewing all 195 raw pairs.

    v1 (filter_count>=3 OR has_join OR comma-count>2) tagged 86% of the
    verified set "complex", because real multi-condition AND-chained filters
    (3+ plain `where` clauses with no join/correlation) are common in this
    dataset (mostly Hunting Queries/Solutions, not curated Detections/) and
    aren't actually harder to translate than a join or wide group-by — they
    were over-weighted relative to genuine structural complexity. v2 raises
    the bar for "many filters alone = complex" to 5, and replaces the naive
    comma-count group-by check with an actual count of `by` clause keys.
    Re-tagging brought complex 86%->68%; the residual skew above the 35/35/30
    target is a real property of this dataset (Hunting Queries trend
    multi-filter) — see docs/NL-KQL/PROJECT_STATUS.md §2.1 — not something to
    keep retuning toward a target distribution.
    """
    filter_count = query.count("| where")
    has_join = "| join" in query
    has_aggregation = "| summarize" in query

    group_by_keys = 0
    if has_aggregation and " by " in query:
        by_clause = query.split(" by ", 1)[1].split("|")[0]
        group_by_keys = _top_level_comma_count(by_clause) + 1

    if has_join or (has_aggregation and group_by_keys >= 3) or (not has_aggregation and filter_count >= 5):
        return "complex"
    if has_aggregation:
        return "moderate"
    return "simple"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, nargs="+", help="one or more raw pairs .jsonl files")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    pairs = []
    for input_path in args.input:
        with open(input_path, encoding="utf-8") as f:
            for line in f:
                pair = json.loads(line)
                pair["complexity_tier"] = tag_complexity(pair["query"])
                pairs.append(pair)

    counts = {"simple": 0, "moderate": 0, "complex": 0}
    for p in pairs:
        counts[p["complexity_tier"]] += 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair) + "\n")

    total = len(pairs)
    print(f"tagged {total} pairs: " + ", ".join(f"{k}={v} ({v/total:.0%})" for k, v in counts.items()))


if __name__ == "__main__":
    main()
