"""Statistical treatment — docs/NL-KQL/MASTER_PLAN.md §19."""
import numpy as np
from statsmodels.stats.contingency_tables import mcnemar


def mcnemar_paired_test(a_results: list[bool], b_results: list[bool]) -> dict:
    """Paired McNemar's test for binary outcome metrics (SVR, FVR) — both
    systems run on the same underlying NL inputs."""
    both_pass = sum(a and b for a, b in zip(a_results, b_results))
    a_only = sum(a and not b for a, b in zip(a_results, b_results))
    b_only = sum(b and not a for a, b in zip(a_results, b_results))
    both_fail = sum(not a and not b for a, b in zip(a_results, b_results))

    table = [[both_pass, a_only], [b_only, both_fail]]
    result = mcnemar(table, exact=(a_only + b_only < 25))
    return {"p_value": result.pvalue, "a_only": a_only, "b_only": b_only}


def bootstrap_ci(values: list[float], n: int = 10000, ci: float = 0.95) -> tuple[float, float]:
    means = [
        np.mean(np.random.choice(values, len(values), replace=True))
        for _ in range(n)
    ]
    lo = (1 - ci) / 2 * 100
    return float(np.percentile(means, lo)), float(np.percentile(means, 100 - lo))
