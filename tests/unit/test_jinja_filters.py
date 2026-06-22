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
