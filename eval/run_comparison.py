"""Primary System A vs. System B comparison on the held-out test split.

Requires data/processed/pairs.jsonl and data/splits/test_ids.json to exist
(Phase 1 — dataset construction) and data/schema/asim_field_reference.json
(Phase 1 — ASIM schema extraction). Not runnable until those are built.
"""
import json
from pathlib import Path

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.baseline.few_shot_examples import FEW_SHOT_EXAMPLE_1, FEW_SHOT_EXAMPLE_2
from src.baseline.run import BaselineRunner
from src.pipeline.system_b import run_system_b

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR = Path(__file__).parent / "results" / "primary"


def load_test_pairs() -> list[dict]:
    test_ids = set(json.loads((DATA_DIR / "splits" / "test_ids.json").read_text()))
    pairs = []
    with (DATA_DIR / "processed" / "pairs.jsonl").open(encoding="utf-8") as f:
        for line in f:
            pair = json.loads(line)
            if pair["rule_id"] in test_ids:
                pairs.append(pair)
    return pairs


def main() -> None:
    asim_schema = json.loads((DATA_DIR / "schema" / "asim_field_reference.json").read_text())
    pairs = load_test_pairs()

    baseline = BaselineRunner()
    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent()

    results = []
    for pair in pairs:
        system_a_kql = baseline.run(
            nl_description=pair["nl_description"],
            asim_field_reference=json.dumps(asim_schema.get(pair["asim_event_type"], {})),
            few_shot_example_1=f"{FEW_SHOT_EXAMPLE_1['nl_description']}\n{FEW_SHOT_EXAMPLE_1['kql']}",
            few_shot_example_2=f"{FEW_SHOT_EXAMPLE_2['nl_description']}\n{FEW_SHOT_EXAMPLE_2['kql']}",
        )
        system_b_result = run_system_b(pair["nl_description"], asim_schema, extraction_agent, ir_builder)

        results.append(
            {
                "pair_id": pair["pair_id"],
                "complexity_tier": pair["complexity_tier"],
                "system_a_kql": system_a_kql,
                "system_b_kql": system_b_result.kql,
                "system_b_success": system_b_result.success,
                "system_b_attempts_used": system_b_result.attempts_used,
                "ground_truth_kql": pair["ground_truth_kql"],
            }
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "comparison_raw.jsonl").write_text(
        "\n".join(json.dumps(r) for r in results), encoding="utf-8"
    )
    print(f"ran {len(results)} test pairs through System A and System B")


if __name__ == "__main__":
    main()
