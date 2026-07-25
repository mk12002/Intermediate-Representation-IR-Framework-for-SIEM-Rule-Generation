from src.generator.compiler import generate_kql
from src.ir_engine.ir_schema import (
    Aggregation, AggregationFunction, ArgMaxMin, ASIMEventType, Filter, FilterGroup, FilterOperator,
    JoinKind, JoinStage, KqlPipeline, WhereStage, SummarizeStage, ProjectStage, ExtendStage, ComputedField,
    MvExpandStage, MakeSeriesStage, SeriesAnomalyStage, ParseStage, ParseToken,
)

def test_simple_ir_filters_only():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")])
        ]
    )
    kql = generate_kql(ir)
    assert kql.startswith("imAuthentication")
    assert 'where EventResult == "Failure"' in kql
    assert "summarize" not in kql

def test_moderate_ir_aggregation():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")]),
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
                group_by=["TargetUsername"],
                time_window="PT10M"
            ),
            WhereStage(filters=[Filter(field="FailCount", operator=FilterOperator.GT, value=15)])
        ]
    )
    kql = generate_kql(ir)
    assert "summarize FailCount = count()" in kql
    assert "by TargetUsername, bin(TimeGenerated, 10m)" in kql
    assert "where FailCount > 15" in kql

def test_output_fields_projected():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            ProjectStage(fields=["SrcIpAddr", "DstIpAddr"])
        ]
    )
    kql = generate_kql(ir)
    assert "project SrcIpAddr, DstIpAddr" in kql
    assert kql.startswith("imNetworkSession")

def test_filter_group_renders_as_parenthesized_or():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            WhereStage(
                filters=[
                    Filter(field="ActingProcessFilename", operator=FilterOperator.EQ, value="net.exe"),
                    FilterGroup(
                        conditions=[
                            Filter(field="ActingProcessCommandLine", operator=FilterOperator.CONTAINS, value="user"),
                            Filter(field="ActingProcessCommandLine", operator=FilterOperator.CONTAINS, value="group"),
                        ]
                    )
                ]
            )
        ]
    )
    kql = generate_kql(ir)
    assert 'where ActingProcessFilename == "net.exe"' in kql
    assert 'where (ActingProcessCommandLine contains "user" or ActingProcessCommandLine contains "group")' in kql

def test_join_renders_let_and_join_clause():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[
            SummarizeStage(aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount")], group_by=["SrcIpAddr"], time_window="PT1H"),
            JoinStage(
                kind=JoinKind.INNER,
                join_on=["SrcIpAddr"],
                right_pipeline=KqlPipeline(
                    source_table=ASIMEventType.DNS,
                    stages=[
                        SummarizeStage(aggregations=[Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="DnsQuery", result_alias="BaselineCount")], group_by=["SrcIpAddr"], time_window="P14D")
                    ]
                )
            ),
            WhereStage(filters=[Filter(field="CurrentCount", operator=FilterOperator.GT, value="BaselineCount")])
        ]
    )
    kql = generate_kql(ir)
    assert "join kind=inner" in kql
    assert "on SrcIpAddr" in kql
    assert "dcount(DnsQuery)" in kql

def test_extend_renders():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="Diff", expression="CurrentCount - BaselineCount")])
        ]
    )
    kql = generate_kql(ir)
    assert "extend Diff = CurrentCount - BaselineCount" in kql


def test_numeric_in_filter_renders_unquoted():
    """Found live: kql_literal's list branch called .replace() on every
    item assuming it was a string — crashed with AttributeError on a
    numeric list (e.g. DstPortNumber in (139, 445)) the moment
    Filter.value was widened to accept List[int]/List[float]. Port numbers
    must render unquoted, not as quoted strings."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            WhereStage(filters=[Filter(field="DstPortNumber", operator=FilterOperator.IN, value=[139, 445])])
        ]
    )
    kql = generate_kql(ir)
    assert "DstPortNumber in (139, 445)" in kql
    assert '"139"' not in kql


def test_filter_field_ref_renders_unquoted_column_not_a_quoted_literal():
    """Added §4AA: a Filter with field_ref set must render the right-hand
    side as a bare column reference, not via kql_literal — that's the
    whole point (the gap this fixes is the model comparing a field
    against the quoted STRING NAME of another column, which can never
    match real data)."""
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            WhereStage(filters=[Filter(field="ProcessTime", operator=FilterOperator.GTE, field_ref="FirstAuthTime")]),
        ],
    )
    kql = generate_kql(ir)
    assert "ProcessTime >= FirstAuthTime" in kql
    assert '"FirstAuthTime"' not in kql


def test_mixed_string_and_numeric_list_renders_each_item_correctly():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            WhereStage(filters=[Filter(field="ActingProcessName", operator=FilterOperator.IN, value=["cmd.exe", "powershell.exe"])])
        ]
    )
    kql = generate_kql(ir)
    assert 'ActingProcessName in ("cmd.exe", "powershell.exe")' in kql


def test_percentile_of_aggregates_via_self_join_compiles_correctly():
    """The percentile-across-groups pattern (e.g. "processes at or below
    the 5th percentile of execution frequency") needs a self-join against
    a constant key plus a second summarize with no group_by to reduce to
    one global scalar row — confirms the full pattern compiles to valid,
    correctly-structured KQL end to end."""
    per_process_freq = SummarizeStage(
        aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="Frequency")],
        group_by=["ActingProcessName"], time_window="P3D",
    )
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            per_process_freq,
            ExtendStage(computed_fields=[ComputedField(alias="JoinKey", expression="1")]),
            JoinStage(
                kind=JoinKind.INNER, join_on=["JoinKey"],
                right_pipeline=KqlPipeline(
                    source_table=ASIMEventType.PROCESS,
                    stages=[
                        per_process_freq,
                        SummarizeStage(
                            aggregations=[Aggregation(function=AggregationFunction.PERCENTILE, field="Frequency", percentile=5, result_alias="P5Frequency")],
                            time_window="P3D",
                        ),
                        ExtendStage(computed_fields=[ComputedField(alias="JoinKey", expression="1")]),
                    ],
                ),
            ),
            ExtendStage(computed_fields=[ComputedField(alias="IsRare", expression="Frequency - P5Frequency")]),
            WhereStage(filters=[Filter(field="IsRare", operator=FilterOperator.LTE, value=0)]),
        ],
    )
    kql = generate_kql(ir)
    assert "percentile(Frequency, 5.0)" in kql
    assert "join kind=inner" in kql
    assert "on JoinKey" in kql
    assert "where IsRare <= 0" in kql

def test_no_caveats_renders_no_comment_lines():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")])],
    )
    kql = generate_kql(ir)
    assert "CAVEAT" not in kql
    assert kql.startswith("imAuthentication")

def test_caveats_render_as_leading_comment_lines():
    ir = KqlPipeline(
        source_table=ASIMEventType.WEB_SESSION,
        stages=[],
        caveats=["no concrete IoC values were given for the source IP check, so no filter on SrcIpAddr was added"],
    )
    kql = generate_kql(ir)
    lines = kql.splitlines()
    assert lines[0] == "// CAVEAT: no concrete IoC values were given for the source IP check, so no filter on SrcIpAddr was added"
    assert lines[1] == "imWebSession"

def test_multiple_caveats_each_render_as_own_comment_line():
    ir = KqlPipeline(source_table=ASIMEventType.PROCESS, stages=[], caveats=["first omission", "second omission"])
    kql = generate_kql(ir)
    lines = kql.splitlines()
    assert lines[0] == "// CAVEAT: first omission"
    assert lines[1] == "// CAVEAT: second omission"
    assert lines[2] == "imProcessCreate"

def test_join_right_pipeline_caveats_still_surface_at_the_top():
    right = KqlPipeline(source_table=ASIMEventType.DNS, stages=[], caveats=["right side caveat"])
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=["SrcIpAddr"])],
    )
    kql = generate_kql(ir)
    lines = kql.splitlines()
    assert lines[0] == "// CAVEAT: right side caveat"
    # The nested pipeline's own body must not also gain a duplicate comment.
    assert kql.count("CAVEAT") == 1

# --- §4AE: abstained pipelines refuse to compile a runnable query ---

def test_abstained_pipeline_emits_no_runnable_query():
    ir = KqlPipeline(
        source_table=ASIMEventType.WEB_SESSION,
        stages=[], abstained=True,
        caveats=["no concrete IoC values were given for the source IP check"],
    )
    kql = generate_kql(ir)
    assert kql == "// ABSTAINED — no executable query produced: no concrete IoC values were given for the source IP check"
    assert "imWebSession" not in kql


def test_abstained_pipeline_with_no_caveats_still_refuses_with_a_generic_reason():
    ir = KqlPipeline(source_table=ASIMEventType.PROCESS, stages=[], abstained=True)
    kql = generate_kql(ir)
    assert kql.startswith("// ABSTAINED")
    assert "imProcessCreate" not in kql


def test_abstained_pipeline_ignores_any_stray_stages_and_still_refuses():
    """abstained=True is authoritative regardless of what (if anything)
    ended up in stages — found live as the actual failure shape this
    fix targets (a model setting both at once would otherwise produce
    an inconsistent result depending on which field won)."""
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[Filter(field="ActingProcessName", operator=FilterOperator.EQ, value="cmd.exe")])],
        abstained=True, caveats=["abstained anyway"],
    )
    kql = generate_kql(ir)
    assert kql == "// ABSTAINED — no executable query produced: abstained anyway"


def test_has_all_and_case_insensitive_in_operators():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[
            Filter(field="CommandLine", operator=FilterOperator.HAS_ALL, value=["accepteula", "-s", "-r", "-q"]),
            Filter(field="ActorUsername", operator=FilterOperator.IN_CI, value=["Admin", "Administrator"]),
        ])],
    )
    kql = generate_kql(ir)
    assert 'CommandLine has_all ("accepteula", "-s", "-r", "-q")' in kql
    assert 'ActorUsername in~ ("Admin", "Administrator")' in kql

def test_case_insensitive_equality_and_case_sensitive_contains_operators():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[
            Filter(field="ActingProcessName", operator=FilterOperator.EQ_CI, value="powershell.exe"),
            Filter(field="CommandLine", operator=FilterOperator.CONTAINS_CS, value="UwB0AGE="),
        ])],
    )
    kql = generate_kql(ir)
    assert 'ActingProcessName =~ "powershell.exe"' in kql
    assert 'CommandLine contains_cs "UwB0AGE="' in kql

def test_mv_expand_single_field_with_type():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[MvExpandStage(fields=["Tags"], as_type="string")],
    )
    kql = generate_kql(ir)
    assert "| mv-expand Tags to typeof(string)" in kql

def test_mv_expand_multiple_fields_in_lockstep():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[MvExpandStage(fields=["TimeBucket", "Count", "AnomalyFlag"])],
    )
    kql = generate_kql(ir)
    assert "| mv-expand TimeBucket, Count, AnomalyFlag" in kql

def test_make_series_and_series_anomaly_pipeline():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[
            MakeSeriesStage(
                aggregations=[Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="DnsQuery", result_alias="DistinctQueries")],
                group_by=["SrcIpAddr"],
                from_time="ago(14d)",
                to_time="now()",
                step="P1D",
            ),
            SeriesAnomalyStage(series_field="DistinctQueries", score_threshold=1.5),
            MvExpandStage(fields=["TimeGenerated", "DistinctQueries", "AnomalyFlag", "AnomalyScore", "Baseline"]),
            WhereStage(filters=[Filter(field="AnomalyFlag", operator=FilterOperator.NEQ, value=0)]),
        ],
    )
    kql = generate_kql(ir)
    assert "| make-series DistinctQueries = dcount(DnsQuery) on TimeGenerated from ago(14d) to now() step 1d by SrcIpAddr" in kql
    assert "| extend (AnomalyFlag, AnomalyScore, Baseline) = series_decompose_anomalies(DistinctQueries, 1.5)" in kql
    assert "| mv-expand TimeGenerated, DistinctQueries, AnomalyFlag, AnomalyScore, Baseline" in kql
    assert "| where AnomalyFlag != 0" in kql

def test_arg_max_with_wildcard_carry_and_group_by():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[SummarizeStage(
            arg_max=ArgMaxMin(order_field="TimeGenerated", carry_fields=["*"]),
            group_by=["DvcHostname"],
            time_window="P1D",
        )],
    )
    kql = generate_kql(ir)
    assert "| summarize arg_max(TimeGenerated, *) by DvcHostname, bin(TimeGenerated, 1d)" in kql

def test_arg_max_and_count_combine_in_same_summarize():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[SummarizeStage(
            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="EventCount")],
            arg_max=ArgMaxMin(order_field="TimeGenerated", carry_fields=["CommandLine", "ActorUsername"]),
            group_by=["DvcHostname"],
            time_window="P1D",
        )],
    )
    kql = generate_kql(ir)
    assert "summarize EventCount = count(), arg_max(TimeGenerated, CommandLine, ActorUsername) by DvcHostname" in kql

def test_arg_min_renders_separately_from_arg_max():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[SummarizeStage(
            arg_min=ArgMaxMin(order_field="TimeGenerated", carry_fields=["*"]),
            group_by=["DvcHostname"],
            time_window="P1D",
        )],
    )
    kql = generate_kql(ir)
    assert "arg_min(TimeGenerated, *)" in kql
    assert "arg_max" not in kql

def test_arg_max_with_custom_result_alias_matches_real_ground_truth_style():
    # Real ground truth (e.g. threat-intel indicator deduplication)
    # consistently renames arg_max's order_field output rather than
    # leaving it under the raw field name.
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[SummarizeStage(
            arg_max=ArgMaxMin(order_field="TimeGenerated", carry_fields=["*"], result_alias="LatestIndicatorTime"),
            group_by=["IndicatorId"],
            time_window="P1D",
        )],
    )
    kql = generate_kql(ir)
    assert "LatestIndicatorTime = arg_max(TimeGenerated, *)" in kql

def test_parse_with_leading_and_trailing_wildcard():
    # Real ground-truth shape: parse Message with * '(' DNSName ')' *
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[ParseStage(source_field="Message", tokens=[
            ParseToken(type="wildcard"),
            ParseToken(type="literal", value="("),
            ParseToken(type="column", value="DNSName"),
            ParseToken(type="literal", value=")"),
            ParseToken(type="wildcard"),
        ])],
    )
    kql = generate_kql(ir)
    assert '| parse Message with * "(" DNSName ")" *' in kql

def test_parse_multi_column_extraction():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[ParseStage(source_field="msg_s", tokens=[
            ParseToken(type="column", value="Protocol"),
            ParseToken(type="literal", value=" request from "),
            ParseToken(type="column", value="SourceHost"),
        ])],
    )
    kql = generate_kql(ir)
    assert '| parse msg_s with Protocol " request from " SourceHost' in kql
