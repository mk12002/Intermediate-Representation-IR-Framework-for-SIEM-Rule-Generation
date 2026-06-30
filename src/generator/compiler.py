from typing import List
from src.ir_engine.ir_schema import ASIM_TABLE_NAMES, KqlPipeline, AndGroup, FilterGroup, Filter
from .filters import kql_agg_call, kql_duration, kql_literal

def _compile_filter(f: Filter) -> str:
    rhs = f.field_ref if f.field_ref is not None else kql_literal(f.value)
    return f"{f.field} {f.operator.value} {rhs}"

def _compile_and_group(g: AndGroup) -> str:
    conditions = " and ".join(_compile_filter(c) for c in g.conditions)
    return f"({conditions})"

def _compile_filter_group(g: FilterGroup) -> str:
    parts = [_compile_and_group(c) if c.type == "and_group" else _compile_filter(c) for c in g.conditions]
    conditions = " or ".join(parts)
    return f"({conditions})"

def compile_pipeline(pipeline: KqlPipeline) -> str:
    source_name = getattr(pipeline.source_table, "value", str(pipeline.source_table))
    source_table = ASIM_TABLE_NAMES.get(pipeline.source_table, source_name)
    
    kql_lines = [source_table]
    
    for stage in pipeline.stages:
        if stage.type == "where":
            for f in stage.filters:
                if f.type == "filter":
                    kql_lines.append(f"| where {_compile_filter(f)}")
                elif f.type == "group":
                    kql_lines.append(f"| where {_compile_filter_group(f)}")
                    
        elif stage.type == "summarize":
            aggs = [f"{a.result_alias} = {kql_agg_call(a)}" for a in stage.aggregations]
            if stage.arg_max:
                am = stage.arg_max
                call = f"arg_max({am.order_field}, {', '.join(am.carry_fields)})"
                aggs.append(f"{am.result_alias} = {call}" if am.result_alias else call)
            if stage.arg_min:
                am = stage.arg_min
                call = f"arg_min({am.order_field}, {', '.join(am.carry_fields)})"
                aggs.append(f"{am.result_alias} = {call}" if am.result_alias else call)
            clause = f"| summarize {', '.join(aggs)}"
            
            by_parts = []
            if stage.group_by:
                by_parts.extend(stage.group_by)
            if stage.time_window:
                by_parts.append(f"bin(TimeGenerated, {kql_duration(stage.time_window)})")
                
            if by_parts:
                clause += f" by {', '.join(by_parts)}"
            kql_lines.append(clause)
            
        elif stage.type == "extend":
            comps = [f"{c.alias} = {c.expression}" for c in stage.computed_fields]
            kql_lines.append(f"| extend {', '.join(comps)}")
            
        elif stage.type == "join":
            right_kql = compile_pipeline(stage.right_pipeline)
            # Indent right pipeline for readability
            right_kql_indented = right_kql.replace("\n", "\n    ")
            clause = f"| join kind={stage.kind.value} (\n    {right_kql_indented}\n) on {', '.join(stage.join_on)}"
            kql_lines.append(clause)
            
        elif stage.type == "union":
            tables_str = ", ".join(stage.tables)
            kql_lines.append(f"| union {tables_str}")
            
        elif stage.type == "project":
            kql_lines.append(f"| project {', '.join(stage.fields)}")
            
        elif stage.type == "top":
            desc_str = "desc" if stage.desc else "asc"
            kql_lines.append(f"| top {stage.limit} by {stage.by_field} {desc_str}")

        elif stage.type == "mv_expand":
            if len(stage.fields) == 1 and stage.as_type:
                kql_lines.append(f"| mv-expand {stage.fields[0]} to typeof({stage.as_type})")
            else:
                kql_lines.append(f"| mv-expand {', '.join(stage.fields)}")

        elif stage.type == "make_series":
            aggs = [f"{a.result_alias} = {kql_agg_call(a)}" for a in stage.aggregations]
            clause = f"| make-series {', '.join(aggs)} on TimeGenerated from {stage.from_time} to {stage.to_time} step {kql_duration(stage.step)}"
            if stage.group_by:
                clause += f" by {', '.join(stage.group_by)}"
            kql_lines.append(clause)

        elif stage.type == "series_anomaly":
            clause = (
                f"| extend ({stage.flag_alias}, {stage.score_alias}, {stage.baseline_alias}) = "
                f"series_decompose_anomalies({stage.series_field}, {stage.score_threshold})"
            )
            kql_lines.append(clause)

        elif stage.type == "parse":
            rendered = []
            for tok in stage.tokens:
                if tok.type == "wildcard":
                    rendered.append("*")
                elif tok.type == "literal":
                    rendered.append(kql_literal(tok.value))
                else:
                    rendered.append(tok.value)
            kql_lines.append(f"| parse {stage.source_field} with {' '.join(rendered)}")

    return "\n".join(kql_lines)

def _collect_caveats(pipeline: KqlPipeline) -> List[str]:
    """Caveats belong on the top-level pipeline by instruction (see
    ir_builder_agent.py), but collected recursively through every join's
    right_pipeline too — a caveat placed on a nested pipeline by mistake
    should still surface, not silently vanish, since the entire point of
    this field is that an omission is never invisible."""
    caveats = list(pipeline.caveats)
    for stage in pipeline.stages:
        if stage.type == "join":
            caveats.extend(_collect_caveats(stage.right_pipeline))
    return caveats

def generate_kql(pipeline: KqlPipeline) -> str:
    """Deterministically compile a validated KqlPipeline into a KQL query string.

    Caveats (see KqlPipeline.caveats) render as leading comment lines so
    the abstention is visible directly in the generated query, not just
    in the structured result around it. Rendered once here, not inside
    compile_pipeline, since that function recurses into a join's
    right_pipeline and a caveat rendered there would land at the wrong
    place mid-query instead of all together at the top."""
    body = compile_pipeline(pipeline)
    caveats = _collect_caveats(pipeline)
    if not caveats:
        return body
    caveat_lines = [f"// CAVEAT: {c}" for c in caveats]
    return "\n".join(caveat_lines) + "\n" + body
