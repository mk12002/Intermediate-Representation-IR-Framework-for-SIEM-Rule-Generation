"""Stratified train/test split — docs/NL-KQL/MASTER_PLAN.md §16.2 Step 6.

Generated once, written to data/splits/{train,test}_ids.json, and committed
immediately. No development or prompt engineering may touch the test split
afterward.

Usage:
    python -m src.data.make_split --input data/processed/pairs_tagged.jsonl \
        --test-fraction 0.2 --seed 42
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

SPLITS_DIR = Path(__file__).parent.parent.parent / "data" / "splits"


def make_split(pairs: list[dict], test_fraction: float, seed: int) -> tuple[list[str], list[str]]:
    by_tier = defaultdict(list)
    for pair in pairs:
        by_tier[pair["complexity_tier"]].append(pair["rule_id"])

    rng = random.Random(seed)
    train_ids, test_ids = [], []
    for tier, ids in by_tier.items():
        ids = sorted(set(ids))
        rng.shuffle(ids)
        n_test = round(len(ids) * test_fraction)
        test_ids.extend(ids[:n_test])
        train_ids.extend(ids[n_test:])
    return train_ids, test_ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    pairs = [json.loads(line) for line in open(args.input, encoding="utf-8")]
    train_ids, test_ids = make_split(pairs, args.test_fraction, args.seed)

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    (SPLITS_DIR / "train_ids.json").write_text(json.dumps(train_ids, indent=2), encoding="utf-8")
    (SPLITS_DIR / "test_ids.json").write_text(json.dumps(test_ids, indent=2), encoding="utf-8")
    print(f"train: {len(train_ids)}, test: {len(test_ids)}")


if __name__ == "__main__":
    main()
