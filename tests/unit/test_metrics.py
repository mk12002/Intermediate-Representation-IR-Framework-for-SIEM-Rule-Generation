from eval.metrics import field_validity_rate, repair_recovery_rate, syntax_validity_rate

ASIM_AUTH_FIELDS = {
    "EventResult", "EventType", "EventResultDetails", "TargetUserId", "TargetUsername",
    "SrcIpAddr", "SrcDvcIpAddr", "SrcGeoCountry", "EventVendor", "TimeGenerated",
}


def test_svr_clean_generated_query():
    kql = 'imAuthentication\n| where EventResult == "Failure"'
    assert syntax_validity_rate([kql]) == 1.0


def test_svr_invalid_query():
    assert syntax_validity_rate(["SELECT * FROM imAuthentication"]) == 0.0


def test_fvr_does_not_flag_let_bindings_or_table_name():
    kql = (
        "let FailureThreshold = 15;\n"
        "imAuthentication\n"
        "| where EventType == 'Logon' and EventResult == 'Failure'\n"
        "| where EventResultDetails in ('No such user or password')\n"
        "| summarize UserCount=dcount(TargetUserId) by SrcIpAddr, SrcGeoCountry, bin(TimeGenerated, 5m)\n"
        "| where UserCount > FailureThreshold"
    )
    assert field_validity_rate([kql], ASIM_AUTH_FIELDS) == 1.0


def test_fvr_does_not_flag_multiple_summarize_aliases():
    kql = (
        "imAuthentication\n"
        "| summarize UserCount=dcount(TargetUserId), Vendors=make_set(EventVendor)\n"
        "    by SrcIpAddr"
    )
    assert field_validity_rate([kql], ASIM_AUTH_FIELDS) == 1.0


def test_fvr_flags_hallucinated_field():
    kql = 'imAuthentication\n| where SourceIP == "1.2.3.4"'
    assert field_validity_rate([kql], ASIM_AUTH_FIELDS) == 0.0


def test_fvr_flags_hallucinated_table():
    """MASTER_PLAN's FVR definition is 'every referenced field/table' — a
    fabricated table like _Im_ServerError must fail FVR even if every field
    referenced afterward happens to be a real field name."""
    kql = '_Im_ServerError()\n| where EventResult == "Failure"'
    assert field_validity_rate([kql], ASIM_AUTH_FIELDS) == 0.0


def test_fvr_accepts_real_table_name_variants():
    for table in ["imAuthentication", "ASimAuthentication", "_Im_Authentication"]:
        kql = f'{table}\n| where EventResult == "Failure"'
        assert field_validity_rate([kql], ASIM_AUTH_FIELDS) == 1.0


def test_fvr_empty_list():
    assert field_validity_rate([], ASIM_AUTH_FIELDS) == 0.0


def test_repair_recovery_rate():
    initial_failures = [True, True, False, True]
    final_passes = [True, False, True, True]
    # cases 0,1,3 failed initially; of those, 0 and 3 ended up passing -> 2/3
    assert repair_recovery_rate(initial_failures, final_passes) == 2 / 3
