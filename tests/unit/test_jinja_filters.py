import pytest

from src.generator.filters import kql_agg_fn, kql_duration, kql_literal
from src.ir_engine.ir_schema import AggregationFunction


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Failure", '"Failure"'),
        (20, "20"),
        (["a", "b"], '("a", "b")'),
    ],
)
def test_kql_literal(value, expected):
    assert kql_literal(value) == expected


@pytest.mark.parametrize(
    "iso8601,expected",
    [
        ("PT5M", "5m"),
        ("PT1H", "1h"),
        ("P1D", "1d"),
        ("PT30S", "30s"),
    ],
)
def test_kql_duration(iso8601, expected):
    assert kql_duration(iso8601) == expected


def test_kql_agg_fn_dcount_distinction():
    assert kql_agg_fn(AggregationFunction.DISTINCT_COUNT) == "dcount"
    assert kql_agg_fn(AggregationFunction.COUNT) == "count"


@pytest.mark.parametrize(
    "value,expected",
    [
        (r"\$Recycle.Bin\\", r'"\\$Recycle.Bin\\\\"'),
        (r"C:\Users\foo", r'"C:\\Users\\foo"'),
        ('say "hi"', r'"say \"hi\""'),
    ],
)
def test_kql_literal_escapes_backslash_and_quote(value, expected):
    """Found live: a filter value containing a literal backslash (Windows
    path, or the literal special folder name "$Recycle.Bin") produced
    malformed KQL — the trailing backslash was read as escaping the closing
    quote rather than terminating the string."""
    assert kql_literal(value) == expected


def test_kql_literal_escapes_within_list_values_too():
    assert kql_literal([r"C:\temp", "plain"]) == r'("C:\\temp", "plain")'
