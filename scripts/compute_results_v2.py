"""Ad hoc analysis script for the post-bugfix gpt-4.1-mini Phase 4 re-run.
Not part of the permanent eval harness — reads eval/results/*.jsonl and
prints the numbers needed to rewrite RESULTS_DRAFT.md / PROJECT_STATUS.md.
"""
import json

from eval.metrics import extract_table_reference, field_validity_rate, is_valid_asim_table, referenced_identifiers
from eval.stats import bootstrap_ci, mcnemar_paired_test
from src.validation.syntax_validators import validate_kql_syntax

asim_schema = json.load(open("data/schema/asim_field_reference.json", encoding="utf-8"))
known_fields = {f for event in asim_schema.values() for f in event["fields"]}

rows = [json.loads(l) for l in open("eval/results/primary/comparison_raw.jsonl", encoding="utf-8")]
n = len(rows)
print(f"n = {n}")


def svr_flags(kql_list):
    return [bool(q) and validate_kql_syntax(q).passed for q in kql_list]


def fvr_flags(kql_list):
    flags = []
    for q in kql_list:
        if not q:
            flags.append(False)
            continue
        table_ref = extract_table_reference(q)
        ok = table_ref is not None and is_valid_asim_table(table_ref) and referenced_identifiers(q) <= known_fields
        flags.append(ok)
    return flags


a_kql = [r["system_a_kql"] for r in rows]
b_kql = [r["system_b_kql"] for r in rows]

a_svr = svr_flags(a_kql)
b_svr = svr_flags(b_kql)
a_fvr = fvr_flags(a_kql)
b_fvr = fvr_flags(b_kql)

print("\n--- SVR / FVR (non-completion counted as failure) ---")
print(f"System A SVR: {sum(a_svr)}/{n} = {sum(a_svr) / n:.3f}  95% CI {bootstrap_ci([float(x) for x in a_svr])}")
print(f"System B SVR: {sum(b_svr)}/{n} = {sum(b_svr) / n:.3f}  95% CI {bootstrap_ci([float(x) for x in b_svr])}")
print(f"System A FVR: {sum(a_fvr)}/{n} = {sum(a_fvr) / n:.3f}  95% CI {bootstrap_ci([float(x) for x in a_fvr])}")
print(f"System B FVR: {sum(b_fvr)}/{n} = {sum(b_fvr) / n:.3f}  95% CI {bootstrap_ci([float(x) for x in b_fvr])}")

print("\n--- McNemar paired tests (A vs B) ---")
print("SVR:", mcnemar_paired_test(a_svr, b_svr))
print("FVR:", mcnemar_paired_test(a_fvr, b_fvr))

print("\n--- System B completion / RRR ---")
b_success = [bool(r.get("system_b_success")) for r in rows]
b_attempts = [r.get("system_b_attempts_used") for r in rows]
print(f"System B success (completion): {sum(b_success)}/{n} = {sum(b_success) / n:.3f}")
initial_failures = [not (s and a == 1) for s, a in zip(b_success, b_attempts)]
recovered = sum(1 for f, s in zip(initial_failures, b_success) if f and s)
n_initial_fail = sum(initial_failures)
print(f"initial failures: {n_initial_fail}, recovered by final attempt: {recovered}, RRR = {recovered / n_initial_fail if n_initial_fail else float('nan'):.3f}")

print("\n--- H4: System B success by complexity tier ---")
tiers = {}
for r, s in zip(rows, b_success):
    tiers.setdefault(r["complexity_tier"], []).append(s)
for tier, vals in sorted(tiers.items()):
    print(f"{tier}: {sum(vals)}/{len(vals)} = {sum(vals) / len(vals):.3f}")

print("\n--- Ablations ---")
for name in ["no_repair", "monolithic_extraction", "no_schema_grounding"]:
    abl_rows = [json.loads(l) for l in open(f"eval/results/ablations/{name}.jsonl", encoding="utf-8")]
    if name == "no_repair":
        vals = [bool(r.get("success")) for r in abl_rows]
    else:
        vals = [bool(r.get("ir_valid")) for r in abl_rows]
    print(f"{name}: {sum(vals)}/{len(vals)} = {sum(vals) / len(vals):.3f}")
