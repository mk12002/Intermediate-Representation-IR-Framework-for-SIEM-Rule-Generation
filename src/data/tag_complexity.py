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


def tag_complexity(query: str) -> str:
    filter_count = query.count("| where")
    has_join = "| join" in query
    has_aggregation = "| summarize" in query
    has_multi_groupby = query.count(",") > 2 and has_aggregation

    if has_join or has_multi_groupby or filter_count >= 3:
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
