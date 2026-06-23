from src.generator.compiler import generate_kql
from src.ir_engine.ir_schema import (
    Aggregation,
    AggregationFunction,
    ASIMEventType,
    Filter,
    FilterGroup,
    FilterOperator,
    JoinKind,
    JoinStage,
    SecurityIR,
    Threshold,
    ThresholdOperator,
)


def test_simple_ir_filters_only():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
    )
    kql = generate_kql(ir)
    assert kql.startswith("imAuthentication")
    assert 'where EventResult == "Failure"' in kql
    assert "summarize" not in kql


def test_moderate_ir_aggregation_threshold_time_window():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
        group_by=["TargetUsername"],
        threshold=Threshold(operator=ThresholdOperator.GT, value=15),
        time_window="PT10M",
    )
    kql = generate_kql(ir)
    assert "summarize FailCount = count()" in kql
    assert "by TargetUsername, bin(TimeGenerated, 10m)" in kql
    assert "where FailCount > 15" in kql


def test_output_fields_projected():
    ir = SecurityIR(
        event_type=ASIMEventType.NETWORK_SESSION,
        output_fields=["SrcIpAddr", "DstIpAddr"],
    )
    kql = generate_kql(ir)
    assert "project SrcIpAddr, DstIpAddr" in kql
    assert kql.startswith("imNetworkSession")


def test_distinct_count_renders_dcount():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(
            function=AggregationFunction.DISTINCT_COUNT, field="TargetUsername", result_alias="DistinctUsers"
        ),
        group_by=["SrcIpAddr"],
        time_window="PT5M",
    )
    kql = generate_kql(ir)
    assert "dcount(TargetUsername)" in kql


def test_percentile_renders_with_both_field_and_value_args():
    """percentile() takes two arguments (field, N) — every other supported
    aggregation function takes zero or one, so this needs its own render
    path rather than the plain "fn(field)" shape."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(
            function=AggregationFunction.PERCENTILE, field="EventResult", percentile=95, result_alias="P95",
        ),
        group_by=["SrcIpAddr"],
        time_window="PT5M",
    )
    kql = generate_kql(ir)
    assert "percentile(EventResult, 95.0)" in kql
    assert "P95 = percentile" in kql


def test_make_set_renders_with_limit():
    ir = SecurityIR(
        event_type=ASIMEventType.WEB_SESSION,
        aggregation=Aggregation(function=AggregationFunction.MAKE_SET, field="Url", result_alias="Urls", limit=100),
        time_window="PT1H",
    )
    kql = generate_kql(ir)
    assert "Urls = make_set(Url, 100)" in kql


def test_make_list_renders_without_limit_when_omitted():
    ir = SecurityIR(
        event_type=ASIMEventType.WEB_SESSION,
        aggregation=Aggregation(function=AggregationFunction.MAKE_LIST, field="Url", result_alias="Urls"),
        time_window="PT1H",
    )
    kql = generate_kql(ir)
    assert "Urls = make_list(Url)" in kql


def test_additional_aggregations_render_as_extra_summarize_columns():
    """Most real ASIM analytic rules compute several summarize columns
    together (count + evidence + timestamps) — confirmed against actual
    ground-truth shape (e.g. "ErrorCount=count(), Urls=make_set(Url,100),
    EventStartTime=min(TimeGenerated), EventEndTime=max(TimeGenerated)")."""
    ir = SecurityIR(
        event_type=ASIMEventType.WEB_SESSION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="ErrorCount"),
        additional_aggregations=[
            Aggregation(function=AggregationFunction.MAKE_SET, field="Url", result_alias="Urls", limit=100),
            Aggregation(function=AggregationFunction.MIN, field="TimeGenerated", result_alias="EventStartTime"),
            Aggregation(function=AggregationFunction.MAX, field="TimeGenerated", result_alias="EventEndTime"),
        ],
        group_by=["SrcIpAddr"],
        time_window="P1D",
    )
    kql = generate_kql(ir)
    assert "summarize ErrorCount = count(), Urls = make_set(Url, 100), EventStartTime = min(TimeGenerated), EventEndTime = max(TimeGenerated)" in kql
    assert "by SrcIpAddr" in kql


def test_join_stage_additional_aggregations_render():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount"),
        group_by=["SrcIpAddr"],
        time_window="PT1H",
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="Count"),
            additional_aggregations=[
                Aggregation(function=AggregationFunction.MAKE_LIST, field="DnsQuery", result_alias="Queries"),
            ],
            time_window="P14D",
            join_on=["SrcIpAddr"],
        ),
    )
    kql = generate_kql(ir)
    assert "Count = count(), Queries = make_list(DnsQuery)" in kql


def test_aggregation_with_time_window_but_no_group_by_has_no_leading_comma():
    """Found live: group_by=[] + time_window set used to render
    "by , bin(TimeGenerated, 5m)" — a leading comma with no preceding
    group-by key, which is dead syntax but still passed the syntax
    validator (no left operand isn't a grammar violation it checks for)."""
    ir = SecurityIR(
        event_type=ASIMEventType.WEB_SESSION,
        aggregation=Aggregation(
            function=AggregationFunction.DISTINCT_COUNT, field="HttpUserAgent", result_alias="DistinctUserAgents"
        ),
        group_by=[],
        time_window="PT5M",
    )
    kql = generate_kql(ir)
    assert "by ," not in kql
    assert "by bin(TimeGenerated, 5m)" in kql


def test_aggregation_with_neither_group_by_nor_time_window_omits_by_clause():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="TotalCount"),
    )
    kql = generate_kql(ir)
    assert "summarize TotalCount = count()" in kql
    assert " by " not in kql


def test_filter_group_renders_as_parenthesized_or():
    """Covers the "(A or B) and (C or D)" pattern a flat AND-only filters
    list can't express — e.g. GT: (CommandLine has 'user' or 'group') and
    (CommandLine hassuffix '/do' or '/domain')."""
    ir = SecurityIR(
        event_type=ASIMEventType.PROCESS,
        filters=[
            Filter(field="ActingProcessFilename", operator=FilterOperator.EQ, value="net.exe"),
            FilterGroup(
                conditions=[
                    Filter(field="ActingProcessCommandLine", operator=FilterOperator.CONTAINS, value="user"),
                    Filter(field="ActingProcessCommandLine", operator=FilterOperator.CONTAINS, value="group"),
                ]
            ),
            FilterGroup(
                conditions=[
                    Filter(field="ActingProcessCommandLine", operator=FilterOperator.ENDSWITH, value="/do"),
                    Filter(field="ActingProcessCommandLine", operator=FilterOperator.ENDSWITH, value="/domain"),
                ]
            ),
        ],
    )
    kql = generate_kql(ir)
    assert 'where ActingProcessFilename == "net.exe"' in kql
    assert 'where (ActingProcessCommandLine contains "user" or ActingProcessCommandLine contains "group")' in kql
    assert 'where (ActingProcessCommandLine endswith "/do" or ActingProcessCommandLine endswith "/domain")' in kql


# --- Negated operator rendering ---

def test_not_contains_renders():
    ir = SecurityIR(
        event_type=ASIMEventType.PROCESS,
        filters=[Filter(field="ActingProcessCommandLine", operator=FilterOperator.NOT_CONTAINS, value="sdelete")],
    )
    kql = generate_kql(ir)
    assert '!contains "sdelete"' in kql


def test_not_in_renders():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="TargetUsername", operator=FilterOperator.NOT_IN, value=["admin", "root"])],
    )
    kql = generate_kql(ir)
    assert '!in ("admin", "root")' in kql


def test_has_renders():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        filters=[Filter(field="DnsQuery", operator=FilterOperator.HAS, value="mining")],
    )
    kql = generate_kql(ir)
    assert 'has "mining"' in kql


def test_has_any_renders_with_parens():
    """has_any needs special syntax: field has_any (val1, val2, ...)"""
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        filters=[Filter(field="DnsQuery", operator=FilterOperator.HAS_ANY, value=["mining.com", "pool.org"])],
    )
    kql = generate_kql(ir)
    assert 'has_any ("mining.com", "pool.org")' in kql


def test_matches_regex_renders():
    ir = SecurityIR(
        event_type=ASIMEventType.PROCESS,
        filters=[Filter(field="ActingProcessCommandLine", operator=FilterOperator.MATCHES_REGEX, value=r"cmd\.exe.*\/c")],
    )
    kql = generate_kql(ir)
    assert 'matches regex' in kql


def test_not_startswith_renders():
    ir = SecurityIR(
        event_type=ASIMEventType.FILE,
        filters=[Filter(field="TargetFilePath", operator=FilterOperator.NOT_STARTSWITH, value="C:\\Windows")],
    )
    kql = generate_kql(ir)
    assert '!startswith' in kql


def test_not_has_renders():
    """The real ground-truth pattern this operator exists for: detecting a
    renamed-binary evasion case requires CommandLine !has "sdelete" — !has
    was initially missing from the negated-operator set even though
    !contains/!startswith/!endswith/!in were added alongside it."""
    ir = SecurityIR(
        event_type=ASIMEventType.PROCESS,
        filters=[Filter(field="ActingProcessCommandLine", operator=FilterOperator.NOT_HAS, value="sdelete")],
    )
    kql = generate_kql(ir)
    assert '!has "sdelete"' in kql


# --- Join rendering ---

def test_join_renders_let_and_join_clause():
    """A JoinStage should render as a let-binding + | join kind=... clause."""
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        filters=[Filter(field="DnsQuery", operator=FilterOperator.HAS, value="mining")],
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount"),
        group_by=["SrcIpAddr"],
        time_window="PT1H",
        join=JoinStage(
            alias="Baseline",
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(
                function=AggregationFunction.DISTINCT_COUNT,
                field="DnsQuery",
                result_alias="BaselineCount",
            ),
            group_by=["SrcIpAddr"],
            time_window="P14D",
            join_on=["SrcIpAddr"],
            join_kind=JoinKind.INNER,
        ),
    )
    kql = generate_kql(ir)
    # Should have the let binding for the subquery
    assert "let Baseline = imDns" in kql
    # Should have the join clause on the main query
    assert "join kind=inner (Baseline) on SrcIpAddr" in kql
    # Main query should still have its own summarize
    assert "summarize CurrentCount = count()" in kql
    # The subquery should have its own summarize
    assert "dcount(DnsQuery)" in kql
    # Found live: the main query's "by ..." clause and the "| join ..."
    # clause rendered on the SAME line with zero separation
    # ("...bin(TimeGenerated, 1h)| join kind=inner...") because every
    # tag-only line between them (the by_parts {% endif %}, the absent
    # threshold block, the join {% if %}) trimmed its own trailing newline
    # with nothing left to contribute one. The join clause must start on
    # its own line.
    assert "| join kind=inner" in kql
    for line in kql.splitlines():
        assert not line.rstrip().endswith(")| join"), f"join clause concatenated onto the previous line: {line!r}"


def test_join_leftanti_renders():
    """leftanti join — exclusion pattern (e.g., exclude known-good IPs)."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
        join=JoinStage(
            alias="KnownGood",
            event_type=ASIMEventType.AUTHENTICATION,
            filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Success")],
            join_on=["SrcIpAddr"],
            join_kind=JoinKind.LEFTANTI,
        ),
    )
    kql = generate_kql(ir)
    assert "let KnownGood = imAuthentication" in kql
    assert "join kind=leftanti (KnownGood) on SrcIpAddr" in kql


def test_join_with_multiple_join_on_keys():
    ir = SecurityIR(
        event_type=ASIMEventType.NETWORK_SESSION,
        join=JoinStage(
            alias="Sub",
            event_type=ASIMEventType.NETWORK_SESSION,
            join_on=["SrcIpAddr", "DstIpAddr"],
            join_kind=JoinKind.INNER,
        ),
    )
    kql = generate_kql(ir)
    assert "on SrcIpAddr, DstIpAddr" in kql


def test_ir_without_join_has_no_let_or_join_clause():
    """Backward compat: IRs without a join field must not emit let/join."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
    )
    kql = generate_kql(ir)
    assert "let " not in kql
    assert "join " not in kql


def test_threshold_compares_to_joined_baseline_column():
    """Found live: a baseline-vs-current detection's threshold compared the
    current count to a bare literal, never the joined BaselineAvg column —
    the join just decorated already-filtered rows. The join clause must
    render BEFORE the threshold so the joined column is in scope, and the
    threshold must reference it directly rather than a literal alone."""
    ir = SecurityIR(
        event_type=ASIMEventType.NETWORK_SESSION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount"),
        group_by=["SrcIpAddr"],
        time_window="P1D",
        threshold=Threshold(operator=ThresholdOperator.GT, value=50, compare_to_join_field="BaselineAvg"),
        join=JoinStage(
            alias="Baseline",
            event_type=ASIMEventType.NETWORK_SESSION,
            aggregation=Aggregation(function=AggregationFunction.AVG, field="SrcIpAddr", result_alias="BaselineAvg"),
            group_by=["SrcIpAddr"],
            time_window="P14D",
            join_on=["SrcIpAddr"],
            join_kind=JoinKind.INNER,
        ),
    )
    kql = generate_kql(ir)
    assert "CurrentCount > BaselineAvg + 50" in kql
    # The join clause must appear before the threshold clause that depends on it.
    join_pos = kql.index("| join kind=inner")
    threshold_pos = kql.index("| where CurrentCount > BaselineAvg")
    assert join_pos < threshold_pos

