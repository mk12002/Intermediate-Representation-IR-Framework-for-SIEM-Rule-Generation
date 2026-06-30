import pandas as pd

from src.execution.ir_interpreter import pipeline_fires, run_pipeline
from src.ir_engine.ir_schema import (
    Aggregation, AggregationFunction, ArgMaxMin, ASIMEventType, ComputedField, Filter,
    FilterGroup, FilterOperator, JoinKind, JoinStage, KqlPipeline,
    MakeSeriesStage, MvExpandStage, ParseStage, ParseToken, SeriesAnomalyStage, SummarizeStage,
    TopStage, WhereStage, ExtendStage, ProjectStage,
)


def test_simple_where_fires_on_matching_row_only():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")])],
    )
    assert pipeline_fires(ir, [{"EventResult": "Failure"}]) is True
    assert pipeline_fires(ir, [{"EventResult": "Success"}]) is False


def test_has_any_and_has_all_case_insensitive_word_boundary():
    ir_any = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[Filter(field="CommandLine", operator=FilterOperator.HAS_ANY, value=["whoami", "ipconfig"])])],
    )
    assert pipeline_fires(ir_any, [{"CommandLine": "cmd.exe /c WHOAMI /all"}]) is True
    assert pipeline_fires(ir_any, [{"CommandLine": "notepad.exe readme.txt"}]) is False

    ir_all = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[Filter(field="CommandLine", operator=FilterOperator.HAS_ALL, value=["accepteula", "-s", "-r", "-q"])])],
    )
    assert pipeline_fires(ir_all, [{"CommandLine": "sdelete64.exe -accepteula -s -r -q C:\\"}]) is True
    assert pipeline_fires(ir_all, [{"CommandLine": "sdelete64.exe -accepteula -s C:\\"}]) is False


def test_in_case_sensitive_vs_in_ci_case_insensitive():
    ir_in = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="ActorUsername", operator=FilterOperator.IN, value=["Admin"])])],
    )
    assert pipeline_fires(ir_in, [{"ActorUsername": "admin"}]) is False  # case-sensitive: no match

    ir_in_ci = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="ActorUsername", operator=FilterOperator.IN_CI, value=["Admin"])])],
    )
    assert pipeline_fires(ir_in_ci, [{"ActorUsername": "admin"}]) is True


def test_eq_case_sensitive_vs_eq_ci_case_insensitive():
    ir_eq = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[Filter(field="ActingProcessName", operator=FilterOperator.EQ, value="powershell.exe")])],
    )
    assert pipeline_fires(ir_eq, [{"ActingProcessName": "PowerShell.EXE"}]) is False  # case-sensitive: no match

    ir_eq_ci = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[Filter(field="ActingProcessName", operator=FilterOperator.EQ_CI, value="powershell.exe")])],
    )
    assert pipeline_fires(ir_eq_ci, [{"ActingProcessName": "PowerShell.EXE"}]) is True


def test_contains_case_insensitive_default_vs_contains_cs_case_sensitive():
    # contains (no suffix) is case-insensitive by default in KQL.
    ir_contains = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[Filter(field="CommandLine", operator=FilterOperator.CONTAINS, value="UwB0AGE=")])],
    )
    assert pipeline_fires(ir_contains, [{"CommandLine": "cmd /c uwb0age= --run"}]) is True

    # contains_cs requires an exact-case match — a different-case base64
    # fragment is a DIFFERENT encoded string, not the same one differently
    # cased, so it must NOT match.
    ir_contains_cs = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[Filter(field="CommandLine", operator=FilterOperator.CONTAINS_CS, value="UwB0AGE=")])],
    )
    assert pipeline_fires(ir_contains_cs, [{"CommandLine": "cmd /c uwb0age= --run"}]) is False
    assert pipeline_fires(ir_contains_cs, [{"CommandLine": "cmd /c UwB0AGE= --run"}]) is True


def test_has_cs_case_sensitive_word_boundary():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[Filter(field="CommandLine", operator=FilterOperator.HAS_CS, value="ENC")])],
    )
    assert pipeline_fires(ir, [{"CommandLine": "powershell -enc abc"}]) is False  # wrong case, has_cs requires exact
    assert pipeline_fires(ir, [{"CommandLine": "powershell -ENC abc"}]) is True


def test_filter_group_or_logic():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[FilterGroup(conditions=[
            Filter(field="DstPortNumber", operator=FilterOperator.EQ, value=22),
            Filter(field="DstPortNumber", operator=FilterOperator.EQ, value=443),
        ])])],
    )
    assert pipeline_fires(ir, [{"DstPortNumber": 22}]) is True
    assert pipeline_fires(ir, [{"DstPortNumber": 443}]) is True
    assert pipeline_fires(ir, [{"DstPortNumber": 80}]) is False


def test_summarize_threshold_fires_only_above_count():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
                group_by=["TargetUsername"],
                time_window="PT10M",
            ),
            WhereStage(filters=[Filter(field="FailCount", operator=FilterOperator.GT, value=3)]),
        ],
    )
    now = "2026-06-24T00:00:00Z"
    few = [{"TargetUsername": "bob", "TimeGenerated": now} for _ in range(2)]
    many = [{"TargetUsername": "bob", "TimeGenerated": now} for _ in range(5)]
    assert pipeline_fires(ir, few) is False
    assert pipeline_fires(ir, many) is True


def test_extend_computed_field_and_comparison():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="IsExternal", expression="ipv4_is_private(SrcIpAddr) == False")]),
            WhereStage(filters=[Filter(field="IsExternal", operator=FilterOperator.EQ, value=True)]),
        ],
    )
    assert pipeline_fires(ir, [{"SrcIpAddr": "8.8.8.8"}]) is True
    assert pipeline_fires(ir, [{"SrcIpAddr": "10.0.0.5"}]) is False


def test_filter_field_ref_brackets_a_value_between_two_other_fields():
    """Added §4AA: the construct-combination case this gap was found
    on — bracketing a process event's time against a joined auth
    event's time window, expressed as two field_ref comparisons rather
    than a literal."""
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            WhereStage(filters=[
                Filter(field="ProcessTime", operator=FilterOperator.GTE, field_ref="FirstAuthTime"),
                Filter(field="ProcessTime", operator=FilterOperator.LTE, field_ref="LastAuthTime"),
            ]),
        ],
    )
    within_window = [{"ProcessTime": "2026-06-24T01:30:00Z", "FirstAuthTime": "2026-06-24T01:00:00Z", "LastAuthTime": "2026-06-24T02:00:00Z"}]
    outside_window = [{"ProcessTime": "2026-06-24T03:00:00Z", "FirstAuthTime": "2026-06-24T01:00:00Z", "LastAuthTime": "2026-06-24T02:00:00Z"}]
    assert pipeline_fires(ir, within_window) is True
    assert pipeline_fires(ir, outside_window) is False


def test_extend_datetime_diff_seconds_minutes_hours_days():
    """Added §4AA — found needed by a real combination case (arg_max
    inside a join, bracketing a process event's time against a joined
    auth event's time window) the interpreter couldn't evaluate at all
    before this, a real capability gap distinct from the field-vs-field
    comparison gap that same case also surfaced (logged separately,
    PROJECT_STATUS.md §4AA, not fixed here)."""
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            ExtendStage(computed_fields=[
                ComputedField(alias="DiffSec", expression="datetime_diff('second', EndTime, StartTime)"),
            ]),
            WhereStage(filters=[Filter(field="DiffSec", operator=FilterOperator.LTE, value=60)]),
        ],
    )
    close = [{"StartTime": "2026-06-24T01:00:00Z", "EndTime": "2026-06-24T01:00:30Z"}]
    far = [{"StartTime": "2026-06-24T01:00:00Z", "EndTime": "2026-06-24T01:05:00Z"}]
    assert pipeline_fires(ir, close) is True
    assert pipeline_fires(ir, far) is False


def test_join_inner_requires_match_on_both_sides():
    right = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[WhereStage(filters=[Filter(field="IsThreatIntel", operator=FilterOperator.EQ, value=True)])],
    )
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=["SrcIpAddr"])],
    )
    left_rows = [{"SrcIpAddr": "1.2.3.4"}]
    assert pipeline_fires(ir, left_rows) is False  # right side has no matching row at all in this call

    # Simulate a real match: left and right share rows with matching key + the right-side filter holding.
    df = run_pipeline(ir, [{"SrcIpAddr": "1.2.3.4", "IsThreatIntel": True}])
    assert not df.empty


def test_top_stage_limits_and_orders():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[TopStage(limit=1, by_field="Count", desc=True)],
    )
    df = run_pipeline(ir, [{"Count": 1}, {"Count": 5}, {"Count": 3}])
    assert len(df) == 1
    assert df.iloc[0]["Count"] == 5


def test_mv_expand_single_field_fans_out_rows():
    ir = KqlPipeline(source_table=ASIMEventType.DNS, stages=[MvExpandStage(fields=["Tags"])])
    df = run_pipeline(ir, [{"Tags": ["a", "b", "c"]}])
    assert len(df) == 3


def test_make_series_then_series_anomaly_flags_a_real_spike():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[
            MakeSeriesStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="NXCount")],
                group_by=["SrcIpAddr"],
                from_time="ago(7d)", to_time="now()", step="P1D",
            ),
            SeriesAnomalyStage(series_field="NXCount", score_threshold=1.5),
            MvExpandStage(fields=["TimeGenerated", "NXCount", "AnomalyFlag", "AnomalyScore", "Baseline"]),
            WhereStage(filters=[Filter(field="AnomalyFlag", operator=FilterOperator.NEQ, value=0)]),
        ],
    )
    # _NOW is fixed at 2026-06-24; ago(7d)..now() with a 1d step buckets
    # all 7 of June 17-23 — every bucket needs SOME events, or an
    # uncovered bucket reads as an implicit zero-count day, which is
    # itself a real (if accidental) anomaly relative to the others.
    all_days = ["2026-06-17", "2026-06-18", "2026-06-19", "2026-06-20", "2026-06-21", "2026-06-22", "2026-06-23"]
    quiet_days = all_days[:-1]
    rows = []
    # 6 quiet days (~2 events each) then 1 day with a massive spike (40 events).
    for day in quiet_days:
        for _ in range(2):
            rows.append({"SrcIpAddr": "10.0.0.1", "TimeGenerated": f"{day}T12:00:00Z"})
    spike_day = all_days[-1] + "T12:00:00Z"
    for _ in range(40):
        rows.append({"SrcIpAddr": "10.0.0.1", "TimeGenerated": spike_day})
    assert pipeline_fires(ir, rows) is True

    flat_rows = [{"SrcIpAddr": "10.0.0.1", "TimeGenerated": f"{day}T12:00:00Z"} for day in all_days for _ in range(2)]
    assert pipeline_fires(ir, flat_rows) is False


def test_arg_max_picks_the_full_row_at_the_latest_timestamp_per_group():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[SummarizeStage(
            arg_max=ArgMaxMin(order_field="TimeGenerated", carry_fields=["*"]),
            group_by=["DvcHostname"],
            time_window="P1D",
        )],
    )
    rows = [
        {"DvcHostname": "host1", "TimeGenerated": "2026-06-24T01:00:00Z", "CommandLine": "early.exe"},
        {"DvcHostname": "host1", "TimeGenerated": "2026-06-24T05:00:00Z", "CommandLine": "latest.exe"},
        {"DvcHostname": "host2", "TimeGenerated": "2026-06-24T02:00:00Z", "CommandLine": "other.exe"},
    ]
    df = run_pipeline(ir, rows)
    host1_row = df[df["DvcHostname"] == "host1"].iloc[0]
    assert host1_row["CommandLine"] == "latest.exe"  # the later of the two host1 rows, not the first


def test_arg_min_picks_the_earliest_row_per_group():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[SummarizeStage(
            arg_min=ArgMaxMin(order_field="TimeGenerated", carry_fields=["CommandLine"]),
            group_by=["DvcHostname"],
            time_window="P1D",
        )],
    )
    rows = [
        {"DvcHostname": "host1", "TimeGenerated": "2026-06-24T05:00:00Z", "CommandLine": "later.exe"},
        {"DvcHostname": "host1", "TimeGenerated": "2026-06-24T01:00:00Z", "CommandLine": "earliest.exe"},
    ]
    df = run_pipeline(ir, rows)
    assert df.iloc[0]["CommandLine"] == "earliest.exe"


def test_arg_max_with_result_alias_does_not_duplicate_the_order_field():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[SummarizeStage(
            arg_max=ArgMaxMin(order_field="TimeGenerated", carry_fields=["*"], result_alias="LatestIndicatorTime"),
            group_by=["IndicatorId"],
            time_window="P1D",
        )],
    )
    rows = [
        {"IndicatorId": "ioc1", "TimeGenerated": "2026-06-24T01:00:00Z", "IsActive": False},
        {"IndicatorId": "ioc1", "TimeGenerated": "2026-06-24T05:00:00Z", "IsActive": True},
    ]
    df = run_pipeline(ir, rows)
    assert "TimeGenerated" not in df.columns  # only available under the alias now
    assert df.iloc[0]["LatestIndicatorTime"] == "2026-06-24T05:00:00Z"
    assert df.iloc[0]["IsActive"] == True  # carried from the same (latest) row


def test_parse_extracts_column_from_matching_rows_and_leaves_nonmatching_null():
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
    df = run_pipeline(ir, [
        {"Message": "Connection blocked for host (evil.example.com) at port 443"},
        {"Message": "no parens here at all"},
    ])
    assert df.iloc[0]["DNSName"] == "evil.example.com"
    assert pd.isna(df.iloc[1]["DNSName"])


def test_parse_then_where_filters_on_extracted_column():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[
            ParseStage(source_field="Message", tokens=[
                ParseToken(type="wildcard"),
                ParseToken(type="literal", value="("),
                ParseToken(type="column", value="DNSName"),
                ParseToken(type="literal", value=")"),
                ParseToken(type="wildcard"),
            ]),
            WhereStage(filters=[Filter(field="DNSName", operator=FilterOperator.ENDSWITH, value=".evil.example.com")]),
        ],
    )
    assert pipeline_fires(ir, [{"Message": "resolved (c2.evil.example.com)"}]) is True
    assert pipeline_fires(ir, [{"Message": "resolved (safe.microsoft.com)"}]) is False
