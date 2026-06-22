"""Exact metric definitions — docs/NL-KQL/MASTER_PLAN.md §17.1."""
import re

from src.validation.syntax_validators import strip_comments_and_strings, validate_kql_syntax

_TOKEN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
_LET_BINDING = re.compile(r"\blet\s+(\w+)\s*=")
_ASSIGNMENT_TARGET = re.compile(r"(?:summarize|extend|project|,)\s+(\w+)\s*=(?!=)")
_TABLE_REFERENCE = re.compile(r"^\s*(_?\w+)")

# KQL operators, functions, and literals that are never field names. Not
# exhaustive of the language — scoped to what System A/B's outputs and the
# dataset's ground-truth queries actually use. See docs/NL-KQL/MASTER_PLAN.md §23
# on why a full KQL grammar/symbol table isn't in scope here.
_KQL_KEYWORDS = {
    "let", "where", "summarize", "project", "extend", "join", "bin", "by", "and", "or", "not",
    "contains", "startswith", "endswith", "in", "has", "has_any", "has_all",
    "count", "count_", "dcount", "dcountif", "countif", "sum", "avg", "min", "max",
    "make_set", "make_list", "arg_max", "arg_min", "ago", "now", "strcat", "split",
    "tostring", "toint", "tolong", "todatetime", "todynamic", "dynamic", "isnotempty",
    "isempty", "isnull", "isnotnull", "format_datetime", "case", "iff", "extract",
    "parse", "true", "false", "kind", "inner", "outer", "leftouter", "on", "render",
    "top", "sort", "order", "desc", "asc", "distinct", "union", "datatable", "print",
    "toscalar", "trim", "substring", "strlen", "indexof", "replace", "tolower",
    "toupper", "bag_pack", "pack", "array_length", "set_difference", "set_union",
    "iif", "strcat_array", "todouble", "toreal", "tobool", "tohex", "tolower",
    "datetime_diff", "startofday", "startofweek", "startofmonth", "endofday",
    "format_timespan", "totimespan", "geo_distance_2points", "ipv4_is_match",
    "ipv4_is_in_range", "parse_json", "bag_unpack", "mv-expand", "mv_expand",
    "materialize", "hint", "shuffle", "with", "step", "range", "series_decompose",
}


def _known_local_names(query: str) -> set[str]:
    """Names defined within the query itself — `let` bindings and
    `summarize`/`extend` assignment aliases — which are correct, query-local
    identifiers and not hallucinated schema fields."""
    return set(_LET_BINDING.findall(query)) | set(_ASSIGNMENT_TARGET.findall(query))


def referenced_identifiers(query: str) -> set[str]:
    cleaned = strip_comments_and_strings(query)
    tokens = set(_TOKEN.findall(cleaned))
    tokens -= _KQL_KEYWORDS
    tokens -= _known_local_names(cleaned)
    tokens = {t for t in tokens if not t.isdigit()}

    body_lines = [l for l in cleaned.strip().splitlines() if l.strip() and not _LET_BINDING.match(l.strip())]
    if body_lines:
        table_match = _TABLE_REFERENCE.match(body_lines[0])
        if table_match:
            tokens.discard(table_match.group(1))
    return tokens


def syntax_validity_rate(generated_queries: list[str]) -> float:
    """SVR — fraction of queries that parse against the KQL grammar."""
    if not generated_queries:
        return 0.0
    passed = sum(1 for q in generated_queries if validate_kql_syntax(q).passed)
    return passed / len(generated_queries)


def field_validity_rate(generated_queries: list[str], known_fields: set[str]) -> float:
    """FVR — fraction of queries where every referenced field/table identifier
    exists in the ASIM schema. Excludes KQL keywords/functions, the query's own
    `let`/assignment-alias locals, and the leading table reference, none of
    which are schema fields."""
    if not generated_queries:
        return 0.0
    valid = 0
    for q in generated_queries:
        if referenced_identifiers(q) <= known_fields:
            valid += 1
    return valid / len(generated_queries)


def repair_recovery_rate(initial_failures: list[bool], final_passes: list[bool]) -> float:
    """RRR — fraction of attempt-1 failures that pass by attempt <= 3."""
    failed_first = [i for i, failed in enumerate(initial_failures) if failed]
    if not failed_first:
        return 0.0
    recovered = sum(1 for i in failed_first if final_passes[i])
    return recovered / len(failed_first)
