from eval.run_comparison import compute_summary

ASIM_SCHEMA = {
    "AuthenticationEvent": {"fields": ["EventResult", "TargetUsername", "SrcIpAddr", "TimeGenerated"]},
}

VALID_KQL = 'imAuthentication\n| where EventResult == "Failure"'


def _result(success: bool, attempts_used, tier: str = "simple") -> dict:
    return {
        "system_b_kql": VALID_KQL if success else None,
        "system_b_success": success,
        "system_b_attempts_used": attempts_used,
        "system_a_kql": None,
        "complexity_tier": tier,
    }


def test_rrr_is_not_unconditionally_zero():
    """Found live: the previous RRR computation derived "attempt 1 failure"
    as `not success`, and "recovered" as `failed and success` for the same
    index — i.e. `(not success) and success`, which is always False
    regardless of the data. A run with 2 genuinely-recovered cases (success
    via repair, attempts_used > 1) printed RRR=0.0%."""
    results = [
        _result(True, attempts_used=2),   # recovered via repair
        _result(True, attempts_used=3),   # recovered via repair
        _result(True, attempts_used=1),   # converged on attempt 1 -- not a failure at all
        _result(False, attempts_used=None),  # never recovered
        _result(False, attempts_used=None),  # never recovered
    ]
    summary = compute_summary(results, ASIM_SCHEMA)
    # attempt-1 failures: the 2 recovered + 2 outright fails = 4 (the
    # attempts_used=1 case did not fail attempt 1). Recovered: the 2 that
    # ultimately succeeded. RRR = 2/4 = 0.5.
    assert summary["rrr"] == 0.5


def test_rrr_with_no_failures_at_all_is_zero_not_a_division_error():
    results = [_result(True, attempts_used=1)]
    summary = compute_summary(results, ASIM_SCHEMA)
    assert summary["rrr"] == 0.0


def test_rrr_with_zero_recoveries():
    results = [_result(False, attempts_used=None), _result(False, attempts_used=None)]
    summary = compute_summary(results, ASIM_SCHEMA)
    assert summary["rrr"] == 0.0
