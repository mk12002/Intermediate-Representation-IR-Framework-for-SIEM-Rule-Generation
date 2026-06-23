"""Primary System A vs. System B comparison on the held-out test split.

Requires data/processed/pairs.jsonl and data/splits/test_ids.json to exist
(Phase 1 — dataset construction) and data/schema/asim_field_reference.json
(Phase 1 — ASIM schema extraction). Not runnable until those are built.
"""
import json
import logging
from pathlib import Path

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.baseline.few_shot_examples import FEW_SHOT_EXAMPLE_1, FEW_SHOT_EXAMPLE_2
from src.baseline.run import BaselineRunner
from src.pipeline.system_b import run_system_b

from eval.metrics import extract_table_reference, field_validity_rate, is_valid_asim_table, referenced_identifiers, syntax_validity_rate
from eval.stats import bootstrap_ci, mcnemar_paired_test
from src.validation.syntax_validators import validate_kql_syntax

logger = logging.getLogger(__name__)

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


def run_one_pair(pair, asim_schema, baseline, extraction_agent, ir_builder) -> dict:
    base = {
        "pair_id": pair["pair_id"],
        "complexity_tier": pair["complexity_tier"],
        "ground_truth_kql": pair["ground_truth_kql"],
    }
    try:
        system_a_kql = baseline.run(
            nl_description=pair["nl_description"],
            asim_field_reference=json.dumps(asim_schema.get(pair["asim_event_type"], {})),
            few_shot_example_1=f"{FEW_SHOT_EXAMPLE_1['nl_description']}\n{FEW_SHOT_EXAMPLE_1['kql']}",
            few_shot_example_2=f"{FEW_SHOT_EXAMPLE_2['nl_description']}\n{FEW_SHOT_EXAMPLE_2['kql']}",
        )
    except Exception as e:
        logger.warning("System A crashed on %s: %s", pair["pair_id"], e)
        system_a_kql = None
        base["system_a_error"] = str(e)

    try:
        system_b_result = run_system_b(pair["nl_description"], asim_schema, extraction_agent, ir_builder)
        base.update(
            system_b_kql=system_b_result.kql,
            system_b_success=system_b_result.success,
            system_b_attempts_used=system_b_result.attempts_used,
            system_b_reason=system_b_result.reason,
        )
    except Exception as e:
        logger.warning("System B crashed on %s: %s", pair["pair_id"], e)
        base.update(system_b_kql=None, system_b_success=False, system_b_error=str(e))

    base["system_a_kql"] = system_a_kql
    return base


def compute_summary(results: list[dict], asim_schema: dict) -> dict:
    """Compute SVR, FVR, RRR, McNemar, and per-tier breakdowns from raw results."""
    all_fields = {f for evt in asim_schema.values() for f in evt["fields"]}

    sys_a_queries = [r.get("system_a_kql") or "" for r in results]
    sys_b_queries = [r.get("system_b_kql") or "" for r in results]

    # Replace None/empty with empty string for SVR (counts as failure)
    sys_a_for_svr = [q if q else "" for q in sys_a_queries]
    sys_b_for_svr = [q if q else "" for q in sys_b_queries]

    svr_a = syntax_validity_rate(sys_a_for_svr)
    svr_b = syntax_validity_rate(sys_b_for_svr)
    fvr_a = field_validity_rate(sys_a_for_svr, all_fields)
    fvr_b = field_validity_rate(sys_b_for_svr, all_fields)

    # Per-query boolean outcomes for McNemar
    svr_a_bools = [bool(q and validate_kql_syntax(q).passed) for q in sys_a_queries]
    svr_b_bools = [bool(q and validate_kql_syntax(q).passed) for q in sys_b_queries]

    fvr_a_bools = []
    fvr_b_bools = []
    for q in sys_a_queries:
        if not q:
            fvr_a_bools.append(False)
            continue
        t = extract_table_reference(q)
        fvr_a_bools.append(bool(t and is_valid_asim_table(t) and referenced_identifiers(q) <= all_fields))
    for q in sys_b_queries:
        if not q:
            fvr_b_bools.append(False)
            continue
        t = extract_table_reference(q)
        fvr_b_bools.append(bool(t and is_valid_asim_table(t) and referenced_identifiers(q) <= all_fields))

    # McNemar tests
    try:
        svr_mcnemar = mcnemar_paired_test(svr_a_bools, svr_b_bools)
    except Exception:
        svr_mcnemar = {"p_value": None, "a_only": 0, "b_only": 0}
    try:
        fvr_mcnemar = mcnemar_paired_test(fvr_a_bools, fvr_b_bools)
    except Exception:
        fvr_mcnemar = {"p_value": None, "a_only": 0, "b_only": 0}

    # RRR — an "attempt 1 failure" is a case where the IR Builder's *first*
    # call didn't produce a valid result, i.e. NOT(success AND attempts_used
    # == 1). The previous version computed `not success`, which is the
    # negation of `final_passes` itself — "failed and final_passes[i]" was
    # therefore `(not success) and success`, always False, making RRR
    # unconditionally 0.0 regardless of the actual data. Confirmed live:
    # 3/5 simulated recoveries still printed RRR=0.0% before this fix.
    final_passes = [r.get("system_b_success", False) for r in results]
    attempts_used = [r.get("system_b_attempts_used") for r in results]
    attempt1_failures = [not (final_passes[i] and attempts_used[i] == 1) for i in range(len(results))]
    total_attempt1_fail = sum(attempt1_failures)
    recovered = sum(1 for i, failed in enumerate(attempt1_failures) if failed and final_passes[i])
    rrr = recovered / total_attempt1_fail if total_attempt1_fail > 0 else 0.0

    # Per-tier breakdown
    tiers = {}
    for r in results:
        t = r.get("complexity_tier", "unknown")
        if t not in tiers:
            tiers[t] = {"total": 0, "sys_b_success": 0}
        tiers[t]["total"] += 1
        if r.get("system_b_success"):
            tiers[t]["sys_b_success"] += 1

    # Bootstrap CIs
    svr_a_ci = bootstrap_ci([float(x) for x in svr_a_bools])
    svr_b_ci = bootstrap_ci([float(x) for x in svr_b_bools])
    fvr_a_ci = bootstrap_ci([float(x) for x in fvr_a_bools])
    fvr_b_ci = bootstrap_ci([float(x) for x in fvr_b_bools])

    return {
        "n": len(results),
        "svr": {"system_a": svr_a, "system_b": svr_b,
                "system_a_ci": svr_a_ci, "system_b_ci": svr_b_ci,
                "mcnemar": svr_mcnemar},
        "fvr": {"system_a": fvr_a, "system_b": fvr_b,
                "system_a_ci": fvr_a_ci, "system_b_ci": fvr_b_ci,
                "mcnemar": fvr_mcnemar},
        "rrr": rrr,
        "per_tier": tiers,
    }


def main() -> None:
    asim_schema = json.loads((DATA_DIR / "schema" / "asim_field_reference.json").read_text())
    pairs = load_test_pairs()

    baseline = BaselineRunner()
    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "comparison_raw.jsonl"

    results = []
    with out_path.open("w", encoding="utf-8") as f:
        for i, pair in enumerate(pairs):
            print(f"[{i + 1}/{len(pairs)}] {pair['pair_id']}", flush=True)
            result = run_one_pair(pair, asim_schema, baseline, extraction_agent, ir_builder)
            results.append(result)
            f.write(json.dumps(result) + "\n")
            f.flush()

    # Compute and save summary metrics
    summary = compute_summary(results, asim_schema)
    summary_path = RESULTS_DIR / "comparison_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Ran {len(results)} test pairs — Summary:")
    print(f"  SVR: System A = {summary['svr']['system_a']:.1%}  |  System B = {summary['svr']['system_b']:.1%}")
    print(f"  FVR: System A = {summary['fvr']['system_a']:.1%}  |  System B = {summary['fvr']['system_b']:.1%}")
    print(f"  RRR: {summary['rrr']:.1%}")
    print(f"  Per-tier: {json.dumps(summary['per_tier'], indent=4)}")
    print(f"  SVR McNemar p = {summary['svr']['mcnemar']['p_value']}")
    print(f"  FVR McNemar p = {summary['fvr']['mcnemar']['p_value']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
