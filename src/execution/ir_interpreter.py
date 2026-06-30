"""A Python interpreter for KqlPipeline — NOT a KQL parser/executor.

This exists because a real execution oracle (the Azure Data Explorer
emulator, or a seeded Log Analytics workspace) is environment-blocked
here: no Docker, no Azure workspace credentials, no Kusto SDKs
(PROJECT_STATUS.md §4Y). Rather than fake that out, this takes a
different, honest path: since the IR's own author also wrote the
compiler, the IR's *intended* semantics are already fully specified —
this module re-implements them directly in pandas, operating on the
KqlPipeline object itself (not the compiled KQL string), so synthetic
"should fire" / "should not fire" events can be run through it and
checked automatically.

What this validates: does the IR Builder's CONSTRUCTED PIPELINE select
the right rows for a given scenario — the actual Logic Correctness
question, made automatable instead of a single rater's judgment call.

What this does NOT validate: whether the COMPILED KQL STRING, run
against a real Kusto engine, produces the same result — a compiler bug
could exist that this interpreter (sharing the compiler author's
understanding of semantics) wouldn't catch. The two are complementary,
not substitutes; this is the one that's actually buildable here.

Scope: WhereStage, SummarizeStage, ExtendStage (a restricted, safe
expression subset — see _SAFE_FUNCTIONS), JoinStage (inner/leftouter/
leftanti/innerunique), ProjectStage, TopStage, MvExpandStage are
interpreted faithfully. MakeSeriesStage/SeriesAnomalyStage are
approximated (a leave-one-out z-score, not Kusto's real STL-based
series_decompose_anomalies) — adequate for a should-fire/should-not-
fire check, not a numerically exact replication. UnionStage is a
no-op (synthetic test data is single-table; real multi-table union
fan-out isn't meaningful to simulate here).
"""
import ast
import ipaddress
import operator
import re
from datetime import datetime, timedelta, timezone
from typing import Any, List

import pandas as pd

from src.ir_engine.ir_schema import (
    AggregationFunction, FilterOperator, KqlPipeline, JoinKind,
)

_NOW = datetime(2026, 6, 24, tzinfo=timezone.utc)  # fixed reference instant for reproducible tests

_AGO_RE = re.compile(r"^ago\((\d+)([dhms])\)$")


def _eval_time_expr(expr: str) -> datetime:
    """Evaluates the tiny subset of KQL time expressions this IR actually
    emits: now() and ago(Nd/Nh/Nm/Ns). Not a general KQL expression
    evaluator — MakeSeriesStage.from_time/to_time are always one of
    these two shapes by construction (see ir_builder_agent.py)."""
    expr = expr.strip()
    if expr == "now()":
        return _NOW
    m = _AGO_RE.match(expr)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        unit_map = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}
        return _NOW - timedelta(**{unit_map[unit]: n})
    raise ValueError(f"unsupported time expression for the interpreter: {expr!r}")


_ISO_RE = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def _iso8601_to_timedelta(duration: str) -> timedelta:
    m = _ISO_RE.match(duration)
    if not m:
        raise ValueError(f"not a supported ISO 8601 duration: {duration!r}")
    d, h, mi, s = (int(g) if g else 0 for g in m.groups())
    return timedelta(days=d, hours=h, minutes=mi, seconds=s)


def _is_private_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_private
    except ValueError:
        return False


# --- Filter evaluation -------------------------------------------------

def _str(v: Any) -> str:
    return "" if v is None else str(v)


def _has_term(haystack: str, term: str, case_sensitive: bool = False) -> bool:
    """Approximates KQL `has`/`has_cs` — whole-TERM matching (not a raw
    substring search like `contains`/`contains_cs`). A real KQL tokenizer
    splits on a broader punctuation/whitespace set than just alphanumeric
    vs. not; this uses a practical word-boundary approximation, adequate
    for synthetic test strings, not a guarantee of matching Kusto's
    tokenizer in every edge case. Only enforces a boundary on a SIDE of
    the term whose own edge character is itself alphanumeric — found
    live: a term like ".ps1" (a file extension, common in real
    detections) starts with a non-alphanumeric character, so requiring a
    non-alphanumeric lookbehind immediately before it rejected a genuine
    match in "payload.ps1" (preceded by the alphanumeric "d") even though
    real KQL's tokenizer would split on "." and find "ps1" as its own
    token there. `case_sensitive=True` is `has_cs`'s case-sensitive
    matching — `has` itself is case-insensitive by default in KQL."""
    if not term:
        return False
    lookbehind = r"(?<![A-Za-z0-9_])" if term[0].isalnum() or term[0] == "_" else ""
    lookahead = r"(?![A-Za-z0-9_])" if term[-1].isalnum() or term[-1] == "_" else ""
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.search(lookbehind + re.escape(term) + lookahead, haystack, flags) is not None


def _eval_single_filter(row: dict, f) -> bool:
    field_val = row.get(f.field)
    # field_ref: compare against ANOTHER column's value (read from the
    # same row) instead of a literal — added §4AA for cross-field/
    # cross-join correlation checks (e.g. bracketing a process event's
    # time against a joined auth event's time window) that a literal
    # `value` cannot express.
    value = row.get(f.field_ref) if f.field_ref is not None else f.value
    op = f.operator

    if op == FilterOperator.EQ:
        return _str(field_val) == _str(value)
    if op == FilterOperator.NEQ:
        return _str(field_val) != _str(value)
    if op == FilterOperator.EQ_CI:
        return _str(field_val).lower() == _str(value).lower()
    if op == FilterOperator.NEQ_CI:
        return _str(field_val).lower() != _str(value).lower()
    if op == FilterOperator.CONTAINS:
        return _str(value).lower() in _str(field_val).lower()
    if op == FilterOperator.NOT_CONTAINS:
        return _str(value).lower() not in _str(field_val).lower()
    if op == FilterOperator.CONTAINS_CS:
        return _str(value) in _str(field_val)
    if op == FilterOperator.NOT_CONTAINS_CS:
        return _str(value) not in _str(field_val)
    if op == FilterOperator.STARTSWITH:
        return _str(field_val).lower().startswith(_str(value).lower())
    if op == FilterOperator.NOT_STARTSWITH:
        return not _str(field_val).lower().startswith(_str(value).lower())
    if op == FilterOperator.STARTSWITH_CS:
        return _str(field_val).startswith(_str(value))
    if op == FilterOperator.NOT_STARTSWITH_CS:
        return not _str(field_val).startswith(_str(value))
    if op == FilterOperator.ENDSWITH:
        return _str(field_val).lower().endswith(_str(value).lower())
    if op == FilterOperator.NOT_ENDSWITH:
        return not _str(field_val).lower().endswith(_str(value).lower())
    if op == FilterOperator.ENDSWITH_CS:
        return _str(field_val).endswith(_str(value))
    if op == FilterOperator.NOT_ENDSWITH_CS:
        return not _str(field_val).endswith(_str(value))
    if op == FilterOperator.IN:
        return any(_str(field_val) == _str(v) for v in value)
    if op == FilterOperator.NOT_IN:
        return not any(_str(field_val) == _str(v) for v in value)
    if op == FilterOperator.IN_CI:
        return any(_str(field_val).lower() == _str(v).lower() for v in value)
    if op == FilterOperator.NOT_IN_CI:
        return not any(_str(field_val).lower() == _str(v).lower() for v in value)
    if op == FilterOperator.HAS:
        return _has_term(_str(field_val), _str(value))
    if op == FilterOperator.NOT_HAS:
        return not _has_term(_str(field_val), _str(value))
    if op == FilterOperator.HAS_ANY:
        return any(_has_term(_str(field_val), _str(v)) for v in value)
    if op == FilterOperator.HAS_ALL:
        return all(_has_term(_str(field_val), _str(v)) for v in value)
    if op == FilterOperator.HAS_CS:
        return _has_term(_str(field_val), _str(value), case_sensitive=True)
    if op == FilterOperator.NOT_HAS_CS:
        return not _has_term(_str(field_val), _str(value), case_sensitive=True)
    if op == FilterOperator.MATCHES_REGEX:
        return re.search(_str(value), _str(field_val)) is not None
    if op in (FilterOperator.GT, FilterOperator.LT, FilterOperator.GTE, FilterOperator.LTE):
        try:
            lhs, rhs = float(field_val), float(value)
        except (TypeError, ValueError):
            # Not numeric — try datetime comparison instead, the other
            # realistic shape for GT/LT/GTE/LTE (e.g. a field_ref
            # bracketing one timestamp column against another).
            try:
                lhs, rhs = pd.to_datetime(field_val, utc=True), pd.to_datetime(value, utc=True)
            except (TypeError, ValueError):
                return False
        return {
            FilterOperator.GT: operator.gt, FilterOperator.LT: operator.lt,
            FilterOperator.GTE: operator.ge, FilterOperator.LTE: operator.le,
        }[op](lhs, rhs)
    raise ValueError(f"interpreter has no rule for operator {op!r}")


def _eval_and_group(row: dict, g) -> bool:
    return all(_eval_single_filter(row, c) for c in g.conditions)


def _eval_filter_or_group_entry(row: dict, entry) -> bool:
    if entry.type == "and_group":
        return _eval_and_group(row, entry)
    return _eval_single_filter(row, entry)


def _eval_filter_group(row: dict, g) -> bool:
    return any(_eval_filter_or_group_entry(row, c) for c in g.conditions)


def _eval_where_entry(row: dict, entry) -> bool:
    if entry.type == "group":
        return _eval_filter_group(row, entry)
    return _eval_single_filter(row, entry)


def _matches_where(row: dict, stage) -> bool:
    return all(_eval_where_entry(row, f) for f in stage.filters)


# --- Safe expression evaluator for ExtendStage --------------------------

def _kql_iff(cond, a, b):
    return a if cond else b


def _kql_datetime_diff(unit: str, end, start) -> float:
    """KQL's datetime_diff(unit, end, start) -> end - start in `unit`s.
    Added §4Z, found needed by a combination-template case (arg_max
    inside a join, bracketing a process event's time against a joined
    auth event's time window) that the interpreter couldn't evaluate at
    all before this — a real capability gap, not a fixture issue, since
    the function is unrelated to field-vs-field comparison (the
    SEPARATE, larger gap that same case also surfaced, logged in
    PROJECT_STATUS.md §4Z rather than silently patched around here)."""
    delta = pd.to_datetime(end, utc=True) - pd.to_datetime(start, utc=True)
    seconds = delta.total_seconds()
    per_unit = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
    if unit not in per_unit:
        raise ValueError(f"datetime_diff: unsupported unit {unit!r}")
    return seconds / per_unit[unit]


_SAFE_FUNCTIONS = {
    "iff": _kql_iff, "tostring": str, "toint": lambda x: int(float(x)),
    "todouble": float, "tolong": lambda x: int(float(x)),
    "strcat": lambda *a: "".join(str(x) for x in a),
    "ipv4_is_private": _is_private_ip,
    "not": lambda x: not x,
    "abs": abs, "min_of": min, "max_of": max,
    "datetime_diff": _kql_datetime_diff,
}

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_CMP_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
}


def _eval_ast(node, row: dict):
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body, row)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in row:
            return row[node.id]
        if node.id in ("true", "True"):
            return True
        if node.id in ("false", "False"):
            return False
        return None
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_ast(node.left, row), _eval_ast(node.right, row))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_ast(node.operand, row)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_ast(node.operand, row)
    if isinstance(node, ast.BoolOp):
        vals = [_eval_ast(v, row) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP_OPS:
        return _CMP_OPS[type(node.ops[0])](_eval_ast(node.left, row), _eval_ast(node.comparators[0], row))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS:
        args = [_eval_ast(a, row) for a in node.args]
        return _SAFE_FUNCTIONS[node.func.id](*args)
    raise ValueError(f"interpreter cannot safely evaluate expression node: {ast.dump(node)}")


def eval_expression(expr: str, row: dict):
    """Evaluates a restricted, KQL-flavored expression against one row.
    Translates `==`/`!=` (already valid Python) and bare KQL function
    calls — supports the specific function set _SAFE_FUNCTIONS lists,
    not arbitrary KQL. Raises ValueError on anything outside that
    subset, deliberately, rather than silently returning a wrong value."""
    tree = ast.parse(expr, mode="eval")
    return _eval_ast(tree, row)


# --- Stage interpreters ---------------------------------------------------

def _apply_where(df: pd.DataFrame, stage) -> pd.DataFrame:
    if df.empty:
        return df
    mask = df.apply(lambda r: _matches_where(r.to_dict(), stage), axis=1)
    return df[mask]


def _agg_series(series: pd.Series, fn: AggregationFunction, agg) -> Any:
    if fn == AggregationFunction.COUNT:
        return len(series)
    if fn == AggregationFunction.DISTINCT_COUNT:
        return series.nunique()
    if fn == AggregationFunction.SUM:
        return pd.to_numeric(series, errors="coerce").sum()
    if fn == AggregationFunction.AVG:
        return pd.to_numeric(series, errors="coerce").mean()
    if fn == AggregationFunction.MIN:
        return series.min()
    if fn == AggregationFunction.MAX:
        return series.max()
    if fn == AggregationFunction.PERCENTILE:
        return pd.to_numeric(series, errors="coerce").quantile((agg.percentile or 50) / 100.0)
    if fn == AggregationFunction.MAKE_SET:
        vals = list(dict.fromkeys(series.tolist()))
        return vals[: agg.limit] if agg.limit else vals
    if fn == AggregationFunction.MAKE_LIST:
        vals = series.tolist()
        return vals[: agg.limit] if agg.limit else vals
    if fn == AggregationFunction.STDEV:
        return pd.to_numeric(series, errors="coerce").std()
    if fn == AggregationFunction.VARIANCE:
        return pd.to_numeric(series, errors="coerce").var()
    raise ValueError(f"interpreter has no rule for aggregation {fn!r}")


def _apply_summarize(df: pd.DataFrame, stage) -> pd.DataFrame:
    work = df.copy()
    group_cols = list(stage.group_by or [])
    if stage.time_window and not work.empty and "TimeGenerated" in work.columns:
        delta = _iso8601_to_timedelta(stage.time_window)
        ts = pd.to_datetime(work["TimeGenerated"], utc=True)
        epoch_seconds = (ts - pd.Timestamp(_NOW)).dt.total_seconds()
        bin_seconds = delta.total_seconds()
        work["_bin"] = epoch_seconds.floordiv(bin_seconds) * bin_seconds
        group_cols = group_cols + ["_bin"]

    if work.empty:
        cols = group_cols + [a.result_alias for a in stage.aggregations]
        return pd.DataFrame(columns=[c for c in cols if c != "_bin"])

    if not group_cols:
        work["_all"] = 1
        groups = work.groupby("_all")
    else:
        groups = work.groupby(group_cols, dropna=False)

    rows = []
    for key, gdf in groups:
        out = {}
        if group_cols:
            keys = key if isinstance(key, tuple) else (key,)
            for col, val in zip(group_cols, keys):
                if col != "_bin":
                    out[col] = val
        for agg in stage.aggregations:
            series = gdf[agg.field] if agg.field else gdf.iloc[:, 0]
            out[agg.result_alias] = _agg_series(series, agg.function, agg)
        for arg_pick, is_max in ((stage.arg_max, True), (stage.arg_min, False)):
            if arg_pick is None:
                continue
            picked_row = gdf.loc[gdf[arg_pick.order_field].idxmax() if is_max else gdf[arg_pick.order_field].idxmin()]
            out[arg_pick.result_alias or arg_pick.order_field] = picked_row[arg_pick.order_field]
            carry = list(gdf.columns) if arg_pick.carry_fields == ["*"] else arg_pick.carry_fields
            for cf in carry:
                if arg_pick.result_alias and cf == arg_pick.order_field:
                    continue  # already emitted under the alias above
                out[cf] = picked_row[cf]
        rows.append(out)
    return pd.DataFrame(rows)


def _apply_extend(df: pd.DataFrame, stage) -> pd.DataFrame:
    work = df.copy()
    for comp in stage.computed_fields:
        if work.empty:
            work[comp.alias] = None
            continue
        work[comp.alias] = work.apply(lambda r: eval_expression(comp.expression, r.to_dict()), axis=1)
    return work


_PANDAS_JOIN_KIND = {
    JoinKind.INNER: "inner", JoinKind.INNERUNIQUE: "inner",
    JoinKind.LEFTOUTER: "left", JoinKind.RIGHTOUTER: "right",
    JoinKind.FULLOUTER: "outer",
}


def _apply_top(df: pd.DataFrame, stage) -> pd.DataFrame:
    if df.empty or stage.by_field not in df.columns:
        return df
    return df.sort_values(by=stage.by_field, ascending=not stage.desc).head(stage.limit)


def _apply_project(df: pd.DataFrame, stage) -> pd.DataFrame:
    cols = [c for c in stage.fields if c in df.columns]
    return df[cols] if cols else df.iloc[:, :0]


def _apply_mv_expand(df: pd.DataFrame, stage) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    if len(stage.fields) == 1:
        return work.explode(stage.fields[0], ignore_index=True)
    # Lockstep multi-field expansion: zip the named columns row-by-row.
    out_rows = []
    for _, row in work.iterrows():
        arrays = [row[f] if isinstance(row[f], list) else [row[f]] for f in stage.fields]
        for tup in zip(*arrays):
            new_row = row.to_dict()
            for f, v in zip(stage.fields, tup):
                new_row[f] = v
            out_rows.append(new_row)
    return pd.DataFrame(out_rows)


def _apply_make_series(df: pd.DataFrame, stage) -> pd.DataFrame:
    """Produces one row per group_by combination, each aggregation as a
    list of per-bucket values spanning from_time..to_time in step-sized
    buckets — matching KqlPipeline's own semantics (see ir_schema.py's
    MakeSeriesStage docstring), not a literal reproduction of Kusto's
    internal bucket-alignment rules."""
    start, end = _eval_time_expr(stage.from_time), _eval_time_expr(stage.to_time)
    step = _iso8601_to_timedelta(stage.step)
    n_buckets = max(1, int((end - start) / step))
    bucket_starts = [start + i * step for i in range(n_buckets)]

    group_cols = list(stage.group_by or [])
    work = df.copy()
    if work.empty or not group_cols:
        groups = [((), work)]
    else:
        groups = list(work.groupby(group_cols, dropna=False))

    rows = []
    for key, gdf in groups:
        out = {}
        keys = key if isinstance(key, tuple) else (key,)
        for col, val in zip(group_cols, keys):
            out[col] = val
        bucket_series = {b: [] for b in bucket_starts}
        for idx, row in gdf.iterrows():
            if "TimeGenerated" not in row:
                continue
            t = pd.to_datetime(row["TimeGenerated"], utc=True).to_pydatetime()
            for b in bucket_starts:
                if b <= t < b + step:
                    bucket_series[b].append(row)
                    break
        out["TimeGenerated"] = bucket_starts
        for agg in stage.aggregations:
            values = []
            for b in bucket_starts:
                bucket_rows = bucket_series[b]
                series = pd.Series([r[agg.field] for r in bucket_rows]) if (agg.field and bucket_rows) else pd.Series(bucket_rows)
                values.append(_agg_series(series, agg.function, agg) if bucket_rows else 0)
            out[agg.result_alias] = values
        rows.append(out)
    return pd.DataFrame(rows)


def _parse_pattern(stage) -> re.Pattern:
    parts = []
    for tok in stage.tokens:
        if tok.type == "literal":
            parts.append(re.escape(tok.value))
        elif tok.type == "column":
            parts.append(f"(?P<{tok.value}>.*?)")
        else:  # wildcard
            parts.append(".*?")
    return re.compile("^" + "".join(parts) + "$", re.DOTALL)


def _apply_parse(df: pd.DataFrame, stage) -> pd.DataFrame:
    """Simple-mode `parse`: a row that doesn't match the pattern at all
    gets null for every extracted column (KQL's own behavior — parse
    never drops rows, a non-match just leaves the new columns empty),
    not filtered out — any filtering on "did this parse" belongs to a
    later WhereStage, the same as real KQL."""
    work = df.copy()
    pattern = _parse_pattern(stage)
    column_names = [t.value for t in stage.tokens if t.type == "column"]
    if work.empty:
        for name in column_names:
            work[name] = None
        return work
    for name in column_names:
        work[name] = None
    for idx, row in work.iterrows():
        m = pattern.match(_str(row[stage.source_field]))
        if m:
            for name in column_names:
                work.at[idx, name] = m.group(name)
    return work


def _apply_series_anomaly(df: pd.DataFrame, stage) -> pd.DataFrame:
    """Approximates series_decompose_anomalies via a leave-one-out
    z-score per series — NOT Kusto's real STL-decomposition algorithm.
    Adequate for a should-fire/should-not-fire synthetic check (a
    genuine, large spike vs. a flat series), not for matching Kusto's
    exact anomaly score on borderline real data."""
    work = df.copy()
    flags, scores, baselines = [], [], []
    for _, row in work.iterrows():
        series = row[stage.series_field]
        vals = pd.Series(series, dtype="float64")
        row_flags, row_scores, row_baselines = [], [], []
        for i in range(len(vals)):
            rest = vals.drop(vals.index[i])
            mean, std = rest.mean(), rest.std(ddof=0)
            std = std if std and std > 0 else 1e-9
            z = (vals.iloc[i] - mean) / std
            flag = 1 if z > stage.score_threshold else (-1 if z < -stage.score_threshold else 0)
            row_flags.append(flag)
            row_scores.append(z)
            row_baselines.append(mean)
        flags.append(row_flags)
        scores.append(row_scores)
        baselines.append(row_baselines)
    work[stage.flag_alias] = flags
    work[stage.score_alias] = scores
    work[stage.baseline_alias] = baselines
    return work


def run_pipeline(pipeline: KqlPipeline, rows: List[dict]) -> pd.DataFrame:
    """Interprets a KqlPipeline against synthetic rows, returning the
    resulting DataFrame (empty if nothing matches/survives). See module
    docstring for exactly what this does and doesn't validate."""
    df = pd.DataFrame(rows)
    for stage in pipeline.stages:
        if df.empty and stage.type not in ("where", "summarize", "make_series"):
            continue
        if stage.type == "where":
            df = _apply_where(df, stage)
        elif stage.type == "summarize":
            df = _apply_summarize(df, stage)
        elif stage.type == "extend":
            df = _apply_extend(df, stage)
        elif stage.type == "join":
            right_df = run_pipeline(stage.right_pipeline, rows)
            kind = _PANDAS_JOIN_KIND.get(stage.kind)
            if stage.kind in (JoinKind.LEFTANTI, JoinKind.LEFTSEMI):
                if right_df.empty:
                    matched = pd.Series([False] * len(df))
                else:
                    merged_keys = right_df[stage.join_on].drop_duplicates()
                    merged = df.merge(merged_keys, on=stage.join_on, how="left", indicator=True)
                    matched = merged["_merge"] == "both"
                df = df[~matched.values] if stage.kind == JoinKind.LEFTANTI else df[matched.values]
            elif kind:
                df = df.merge(right_df, on=stage.join_on, how=kind, suffixes=("", "_right"))
                if stage.kind == JoinKind.INNERUNIQUE:
                    df = df.drop_duplicates(subset=stage.join_on)
            else:
                raise ValueError(f"interpreter has no rule for join kind {stage.kind!r}")
        elif stage.type == "union":
            continue  # see module docstring — synthetic single-table data, union is a no-op here
        elif stage.type == "project":
            df = _apply_project(df, stage)
        elif stage.type == "top":
            df = _apply_top(df, stage)
        elif stage.type == "mv_expand":
            df = _apply_mv_expand(df, stage)
        elif stage.type == "make_series":
            df = _apply_make_series(df, stage)
        elif stage.type == "series_anomaly":
            df = _apply_series_anomaly(df, stage)
        elif stage.type == "parse":
            df = _apply_parse(df, stage)
        else:
            raise ValueError(f"interpreter has no rule for stage type {stage.type!r}")
    return df


def pipeline_fires(pipeline: KqlPipeline, rows: List[dict]) -> bool:
    """True if the pipeline's final result set is non-empty for the given
    synthetic rows — the should-fire/should-not-fire check this module
    exists for."""
    return not run_pipeline(pipeline, rows).empty
