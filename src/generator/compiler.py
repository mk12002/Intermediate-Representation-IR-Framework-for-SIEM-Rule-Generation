from pathlib import Path

import jinja2

from src.ir_engine.ir_schema import ASIM_TABLE_NAMES, SecurityIR

from .filters import kql_agg_call, kql_agg_fn, kql_duration, kql_literal

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["kql_literal"] = kql_literal
_env.filters["kql_duration"] = kql_duration
_env.filters["kql_agg_fn"] = kql_agg_fn
_env.filters["kql_agg_call"] = kql_agg_call

_template = _env.get_template("kql_query.kql.j2")


def generate_kql(ir: SecurityIR) -> str:
    """Deterministically compile a validated SecurityIR into a KQL query string.

    Zero LLM calls, zero degrees of freedom — every bug here affects every
    generated query, so this is unit-tested directly (see tests/test_templates.py).
    """
    ctx = dict(
        asim_table_name=ASIM_TABLE_NAMES[ir.event_type],
        filters=ir.filters,
        aggregation=ir.aggregation,
        additional_aggregations=ir.additional_aggregations,
        group_by=ir.group_by or [],
        threshold=ir.threshold,
        time_window=ir.time_window,
        output_fields=ir.output_fields,
        join=ir.join,
    )
    if ir.join:
        ctx["join_table_name"] = ASIM_TABLE_NAMES[ir.join.event_type]
    return _template.render(**ctx).strip()

