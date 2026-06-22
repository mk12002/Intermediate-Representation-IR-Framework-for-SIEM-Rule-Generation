from src.data.tag_complexity import tag_complexity


def test_single_filter_no_aggregation_is_simple():
    q = 'imAuthentication\n| where EventResult == "Failure"'
    assert tag_complexity(q) == "simple"


def test_aggregation_with_few_groupby_keys_is_moderate():
    q = (
        "imAuthentication\n"
        "| where EventResult == 'Failure'\n"
        "| summarize FailCount=count() by TargetUsername, bin(TimeGenerated, 10m)"
    )
    assert tag_complexity(q) == "moderate"


def test_join_is_complex():
    q = "imAuthentication\n| where EventResult == 'Failure'\n| join (imAuthentication | where EventResult == 'Success') on TargetUsername"
    assert tag_complexity(q) == "complex"


def test_aggregation_with_many_groupby_keys_is_complex():
    q = (
        "imAuthentication\n"
        "| summarize Count=count() by SrcIpAddr, TargetUsername, SrcGeoCountry, bin(TimeGenerated, 5m)"
    )
    assert tag_complexity(q) == "complex"


def test_many_plain_filters_without_aggregation_is_complex():
    q = "\n".join(["imAuthentication"] + [f'| where Field{i} == "x"' for i in range(5)])
    assert tag_complexity(q) == "complex"


def test_few_plain_filters_without_aggregation_is_simple():
    q = "\n".join(["imAuthentication"] + [f'| where Field{i} == "x"' for i in range(3)])
    assert tag_complexity(q) == "simple"
