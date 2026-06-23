"""Exact metric definitions — docs/NL-KQL/MASTER_PLAN.md §17.1."""
import re

from src.validation.syntax_validators import strip_comments_and_strings, validate_kql_syntax

_TOKEN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
_LET_BINDING = re.compile(r"\blet\s+(\w+)\s*=")
_ASSIGNMENT_TARGET = re.compile(r"(?:summarize|extend|project|,)\s+(\w+)\s*=(?!=)")
_TABLE_REFERENCE = re.compile(r"^\s*(_?\w+)")
# Parser-call kwargs, e.g. _Im_Dns(responsecodename='NXDOMAIN', starttime=ago(1d))
_PARSER_KWARG = re.compile(r"[(,]\s*([a-z][a-z0-9_]*)\s*=(?!=)")

# Valid ASIM unifying-table name patterns (filtering `im*`/`_Im_*`, parameter-less
# `ASim*`), one per event type this project's IR covers. A table reference
# matching none of these is a hallucinated/non-ASIM table — MASTER_PLAN's FVR
# definition explicitly includes "every referenced field/table", so this must
# be checked, not skipped.
_VALID_ASIM_TABLE_PATTERNS = [
    re.compile(r"^(im|ASim|_Im_)Authentication$", re.IGNORECASE),
    re.compile(r"^(im|ASim|_Im_)NetworkSession$", re.IGNORECASE),
    re.compile(r"^(im|ASim|_Im_)Process(Create|Terminate|Event)?$", re.IGNORECASE),
    re.compile(r"^(im|ASim|_Im_)FileEvent$", re.IGNORECASE),
    re.compile(r"^(im|ASim|_Im_)Dns$", re.IGNORECASE),
    re.compile(r"^(im|ASim|_Im_)WebSession$", re.IGNORECASE),
    re.compile(r"^(im|ASim|_Im_)Registry(Event)?$", re.IGNORECASE),
]


def is_valid_asim_table(token: str) -> bool:
    return any(p.match(token) for p in _VALID_ASIM_TABLE_PATTERNS)

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
    "hassuffix", "hasprefix", "notcontains", "matches", "regex", "away", "expand",
    "mv", "leftanti", "rightouter", "fullouter", "anti", "semi", "between",
    "ipv6_is_match", "geo_info_from_ip_address", "indexof_regex", "tostring_array",
}


def _known_local_names(query: str) -> set[str]:
    """Names defined within the query itself — `let` bindings,
    `summarize`/`extend` assignment aliases, and parser-call kwargs (e.g.
    `responsecodename=` in `_Im_Dns(responsecodename='NXDOMAIN')`) — none of
    which are schema fields."""
    return (
        set(_LET_BINDING.findall(query))
        | set(_ASSIGNMENT_TARGET.findall(query))
        | set(_PARSER_KWARG.findall(query))
    )


def extract_table_reference(query: str) -> str | None:
    """Find the main query's source table.

    `;` is KQL's statement separator — any `let NAME = ...;` statement
    (scalar, or a multi-line tabular subquery as used by a JoinStage)
    precedes the main query and ends with `;`. Splitting on the *last* `;`
    and looking only at what follows finds the main query regardless of how
    many such statements come before it. Found live: the previous
    line-by-line `_LET_BINDING`-skip only filtered lines that themselves
    started with "let NAME =" — a multi-line let-bound subquery's
    continuation lines (e.g. "| summarize ... by ...") were not let-bindings
    themselves, so the first such continuation line was mistaken for the
    main query's table reference, which doesn't match `_TABLE_REFERENCE`
    (starts with "|"), making this return None — and therefore FVR
    unconditionally 0 — for every query using a join/subquery."""
    cleaned = strip_comments_and_strings(query)
    main_segment = cleaned.split(";")[-1]
    body_lines = [l for l in main_segment.strip().splitlines() if l.strip() and not _LET_BINDING.match(l.strip())]
    if not body_lines:
        return None
    table_match = _TABLE_REFERENCE.match(body_lines[0])
    return table_match.group(1) if table_match else None


def referenced_identifiers(query: str) -> set[str]:
    cleaned = strip_comments_and_strings(query)
    tokens = set(_TOKEN.findall(cleaned))
    tokens -= _KQL_KEYWORDS
    tokens -= _known_local_names(cleaned)
    tokens = {t for t in tokens if not t.isdigit()}

    table_ref = extract_table_reference(query)
    if table_ref:
        tokens.discard(table_ref)
    return tokens


def syntax_validity_rate(generated_queries: list[str]) -> float:
    """SVR — fraction of queries that parse against the KQL grammar."""
    if not generated_queries:
        return 0.0
    passed = sum(1 for q in generated_queries if validate_kql_syntax(q).passed)
    return passed / len(generated_queries)


def field_validity_rate(generated_queries: list[str], known_fields: set[str]) -> float:
    """FVR — fraction of queries where every referenced field exists in the
    ASIM schema AND the source table is a real ASIM unifying table (not a
    hallucinated one, e.g. "_Im_ServerError"). Excludes KQL keywords/functions
    and the query's own `let`/assignment-alias locals from the field check."""
    if not generated_queries:
        return 0.0
    valid = 0
    for q in generated_queries:
        table_ref = extract_table_reference(q)
        if table_ref is None or not is_valid_asim_table(table_ref):
            continue
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
