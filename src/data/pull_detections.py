"""Pull ASIM-normalized detection rules from a cloned Azure/Azure-Sentinel repo.

Usage:
    python -m src.data.pull_detections --source /tmp/azure-sentinel/Detections \
        --filter-asim-only --output data/raw/detections_raw.jsonl
"""
import argparse
import json
import re
from glob import glob
from pathlib import Path

import yaml

# Word-boundary table-name patterns, e.g. imAuthentication, _Im_NetworkSession,
# ASimDns — NOT a bare substring match on "im", which false-positives on
# ordinary words like "claim", "victim", "Limit".
_ASIM_TABLE_PATTERN = re.compile(r"\b(im[A-Z]\w*|_Im_\w*|ASim\w*)\b")


def is_asim_normalized(query: str) -> bool:
    return bool(_ASIM_TABLE_PATTERN.search(query))


def extract_pair(yaml_path: str) -> dict | None:
    with open(yaml_path, encoding="utf-8") as f:
        rule = yaml.safe_load(f)
    if not rule:
        return None

    description = (rule.get("description") or "").strip()
    query = (rule.get("query") or "").strip()

    if len(description) < 20:
        return None
    if "{{" in query or "{{" in description:
        return None

    return {
        "source_file": yaml_path,
        "rule_id": rule.get("id"),
        "description_raw": description,
        "query": query,
        "tactics": rule.get("tactics", []),
        "techniques": rule.get("relevantTechniques", []),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="path to Detections/ folder")
    parser.add_argument("--filter-asim-only", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    asim_pairs, non_asim_pairs = [], []
    for path in glob(f"{args.source}/**/*.yaml", recursive=True):
        pair = extract_pair(path)
        if pair is None:
            continue
        if is_asim_normalized(pair["query"]):
            asim_pairs.append(pair)
        else:
            non_asim_pairs.append(pair)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for pair in asim_pairs:
            f.write(json.dumps(pair) + "\n")

    if not args.filter_asim_only:
        return
    non_asim_path = out_path.parent / "detections_raw_non_asim.jsonl"
    with non_asim_path.open("w", encoding="utf-8") as f:
        for pair in non_asim_pairs:
            f.write(json.dumps(pair) + "\n")

    print(f"asim pairs: {len(asim_pairs)}, non-asim (reserved): {len(non_asim_pairs)}")


if __name__ == "__main__":
    main()
