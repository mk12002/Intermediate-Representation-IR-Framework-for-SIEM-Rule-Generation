import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

from .ir_schema import AggregationFunction, FilterOperator, KqlPipeline

_ISO8601_DURATION = re.compile(r"^P(?!$)(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+S)?)?$")

# Operators where a field-to-field comparison is a real, common pattern
# (bracketing one event's value against another's — see Filter.field_ref
# in ir_schema.py) — restricting LITERAL_MATCHES_SCHEMA_FIELD to these
# keeps the check targeted at the actual failure mode it exists to catch
# (§4AA's bug, generalized) rather than firing on contains/has/startswith,
# where a literal coincidentally spelled like a column name is far more
# likely to be exactly that: an unusual but real literal, not a mistaken
# field reference.
_FIELD_REF_LIKELY_OPERATORS = {
    FilterOperator.EQ, FilterOperator.NEQ, FilterOperator.EQ_CI, FilterOperator.NEQ_CI,
    FilterOperator.GT, FilterOperator.LT, FilterOperator.GTE, FilterOperator.LTE,
}

# A FilterGroup (OR) whose conditions are ALL a negated operator on the SAME
# field with DIFFERENT literal values is a tautology: "X != 'a' or X != 'b'"
# is true for every value except one that is somehow simultaneously 'a' and
# 'b', which is impossible — so it's always true and filters nothing. Found
# live, repeatedly: a renamed-binary-evasion exclusion ("not literally named
# sdelete.exe, and also not sdelete64.exe") wrapped in an OR instead of
# AND — the model reaches for FilterGroup whenever there's more than one
# exclusion condition, even though FilterGroup is an OR and exclusions need
# to ALL hold (AND) to mean "excluded from every one of these names".
_NEGATED_OPERATORS = {
    FilterOperator.NEQ, FilterOperator.NOT_CONTAINS, FilterOperator.NOT_STARTSWITH,
    FilterOperator.NOT_ENDSWITH, FilterOperator.NOT_IN, FilterOperator.NOT_HAS,
    # Case-insensitive/-sensitive variants (added alongside the operators
    # themselves) — a tautological OR-of-negations is just as tautological
    # whether the comparison is case-sensitive or not, so these need the
    # same coverage as their plain counterparts above or this check would
    # silently stop catching the exact bug class it exists for on any IR
    # using one of these operators instead of the originals.
    FilterOperator.NEQ_CI, FilterOperator.NOT_CONTAINS_CS,
    FilterOperator.NOT_STARTSWITH_CS, FilterOperator.NOT_ENDSWITH_CS,
    FilterOperator.NOT_HAS_CS,
}


def _is_tautological_negation_group(conditions) -> bool:
    if not all(c.type == "filter" and c.operator in _NEGATED_OPERATORS for c in conditions):
        return False
    fields = {c.field for c in conditions}
    if len(fields) != 1:
        return False
    values = {c.value if not isinstance(c.value, list) else tuple(c.value) for c in conditions}
    return len(values) == len(conditions)


# A direct complementary pair — "X in (...) or X !in (...)" with the SAME
# field and value — is the most basic tautology (X or not-X), distinct from
# _is_tautological_negation_group above (which needs >=2 all-negated
# conditions on different values). Found live: the model wrapped a positive
# membership check and its own negation in one OR'd group instead of
# choosing one.
_COMPLEMENTARY_OPERATORS = {
    FilterOperator.EQ: FilterOperator.NEQ,
    FilterOperator.NEQ: FilterOperator.EQ,
    FilterOperator.CONTAINS: FilterOperator.NOT_CONTAINS,
    FilterOperator.NOT_CONTAINS: FilterOperator.CONTAINS,
    FilterOperator.STARTSWITH: FilterOperator.NOT_STARTSWITH,
    FilterOperator.NOT_STARTSWITH: FilterOperator.STARTSWITH,
    FilterOperator.ENDSWITH: FilterOperator.NOT_ENDSWITH,
    FilterOperator.NOT_ENDSWITH: FilterOperator.ENDSWITH,
    FilterOperator.IN: FilterOperator.NOT_IN,
    FilterOperator.NOT_IN: FilterOperator.IN,
    FilterOperator.HAS: FilterOperator.NOT_HAS,
    FilterOperator.NOT_HAS: FilterOperator.HAS,
    # Same complementary-pair logic for the case-insensitive-equality and
    # case-sensitive substring/prefix/suffix/term operators added alongside
    # EQ_CI/CONTAINS_CS/etc. — without these, "X =~ 'a' or X !~ 'a'" would
    # pass this check uncaught purely because it uses the newer operator
    # spelling instead of plain ==/!=.
    FilterOperator.EQ_CI: FilterOperator.NEQ_CI,
    FilterOperator.NEQ_CI: FilterOperator.EQ_CI,
    FilterOperator.CONTAINS_CS: FilterOperator.NOT_CONTAINS_CS,
    FilterOperator.NOT_CONTAINS_CS: FilterOperator.CONTAINS_CS,
    FilterOperator.STARTSWITH_CS: FilterOperator.NOT_STARTSWITH_CS,
    FilterOperator.NOT_STARTSWITH_CS: FilterOperator.STARTSWITH_CS,
    FilterOperator.ENDSWITH_CS: FilterOperator.NOT_ENDSWITH_CS,
    FilterOperator.NOT_ENDSWITH_CS: FilterOperator.ENDSWITH_CS,
    FilterOperator.HAS_CS: FilterOperator.NOT_HAS_CS,
    FilterOperator.NOT_HAS_CS: FilterOperator.HAS_CS,
}


def _has_complementary_pair(conditions) -> bool:
    plain = [c for c in conditions if c.type == "filter"]
    for i, a in enumerate(plain):
        for b in plain[i + 1:]:
            if a.field != b.field:
                continue
            a_val = a.value if not isinstance(a.value, list) else tuple(a.value)
            b_val = b.value if not isinstance(b.value, list) else tuple(b.value)
            if a_val != b_val:
                continue
            if _COMPLEMENTARY_OPERATORS.get(a.operator) == b.operator:
                return True
    return False


# A two-sided numeric range ("X > 0 and X <= 60") expressed as OR instead
# of AND is a tautology whenever the lower bound doesn't exceed the upper
# bound — every real number satisfies at least one side (e.g. -5 <= 60;
# 1000 > 0). Found live: a sequential-events pattern's own ">0 and <=60"
# ordering+window check, normally two separate AND-ed WhereStage filters,
# got flattened into one FilterGroup with "or" instead — the same
# AND-vs-OR confusion this validator already catches for other shapes,
# just for a numeric range pair instead of a negated-value or
# complementary-operator pair.
_LOWER_BOUND_OPS = {FilterOperator.GT, FilterOperator.GTE}
_UPPER_BOUND_OPS = {FilterOperator.LT, FilterOperator.LTE}


def _has_tautological_range_pair(conditions) -> bool:
    plain = [c for c in conditions if c.type == "filter"]
    for i, a in enumerate(plain):
        for b in plain[i + 1:]:
            if a.field != b.field:
                continue
            if a.operator in _LOWER_BOUND_OPS and b.operator in _UPPER_BOUND_OPS:
                lo, hi = a, b
            elif b.operator in _LOWER_BOUND_OPS and a.operator in _UPPER_BOUND_OPS:
                lo, hi = b, a
            else:
                continue
            if isinstance(lo.value, bool) or isinstance(hi.value, bool):
                continue
            if not isinstance(lo.value, (int, float)) or not isinstance(hi.value, (int, float)):
                continue
            lo_val, hi_val = float(lo.value), float(hi.value)
            if lo_val < hi_val:
                return True
            if lo_val == hi_val and not (lo.operator == FilterOperator.GT and hi.operator == FilterOperator.LT):
                return True
    return False

# Only count()/dcount() can be trivially true for every group that exists in
# a summarize result (a group can't exist with zero rows) — a threshold below
# 1, or a GTE threshold at or below 1, filters nothing. Carried forward from
# the original SecurityIR validator (found live, gpt-4.1-mini: "ErrorCount
# >= 1" passed validation while filtering zero rows) — the AST migration
# dropped this check entirely until restored here.
_DEGENERATE_COUNT_FUNCTIONS = {AggregationFunction.COUNT, AggregationFunction.DISTINCT_COUNT}

# stdev()/variance() of a group that's already been reduced to one row by
# an identical prior grouping is always 0/null — found live, repeatedly,
# even after explicit prompt guidance: the model keeps using the SAME
# time_window on both chained SummarizeStages instead of a finer bucket
# on the first one.
_SPREAD_FUNCTIONS = {AggregationFunction.STDEV, AggregationFunction.VARIANCE}

# Only count() takes zero arguments in KQL — every other function needs a
# field to operate on. Also carried forward; the AST migration dropped it.
_FUNCTIONS_REQUIRING_FIELD = {
    AggregationFunction.DISTINCT_COUNT, AggregationFunction.SUM,
    AggregationFunction.AVG, AggregationFunction.MIN, AggregationFunction.MAX,
    AggregationFunction.PERCENTILE, AggregationFunction.MAKE_SET,
    AggregationFunction.MAKE_LIST, AggregationFunction.STDEV,
    AggregationFunction.VARIANCE,
}

# Best-effort identifier extraction for ExtendStage.computed_fields[].expression
# — a raw KQL expression string the schema cannot structurally validate the
# way it validates every other stage's field references. Without this, a
# hallucinated field name inside an expression (e.g. "extend X = SomeFakeField
# + 1") compiles and ships silently — the exact failure mode (FVR) the rest of
# this validator exists to prevent. Not a real KQL parser: strips string
# literals, treats any identifier immediately followed by "(" as a function
# call (not a field), and excludes a small set of bare operator/literal words.
# This will have some false positives (an unusual constant-like token gets
# flagged) but that is a far better failure mode than zero checking — a false
# positive costs one repair attempt; a true negative ships a hallucinated field.
_STRING_LITERAL_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
_FUNCTION_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_KQL_OPERATOR_WORDS = frozenset({
    "and", "or", "not", "in", "has", "has_any", "contains", "startswith",
    "endswith", "between", "true", "false", "null", "dynamic",
})

# Real KQL scalar functions — not exhaustive, but covers the common cases
# this project's outputs and ground truth actually use. Found live: the
# model invented array_diff()/array_avg()/array_stddev() inside an extend
# expression — none of those are real KQL functions — and the original
# "anything followed by '(' is a function, skip it" logic let all three
# sail through completely unchecked, the same field-hallucination failure
# mode this validator otherwise exists to prevent, just for function names
# instead of field names.
_KNOWN_KQL_FUNCTIONS = frozenset({
    "strcat", "strcat_array", "split", "substring", "strlen", "indexof",
    "indexof_regex", "replace_string", "replace_regex", "replace", "trim",
    "trim_start", "trim_end", "tolower", "toupper", "parse_json",
    "parse_url", "parse_urlquery", "parse_csv", "parse_path", "extract",
    "extract_all", "reverse", "url_decode", "url_encode", "translate",
    "countof", "isempty", "isnotempty", "isnull", "isnotnull", "isnan",
    "isfinite", "isinf", "parse_version", "parse_ipv4", "parse_ipv4_mask",
    "base64_encodestring", "base64_decodestring", "base64_decodetostring",
    "abs", "sign", "exp", "exp2", "exp10", "log", "log2", "log10", "sqrt",
    "pow", "round", "floor", "ceiling", "bin", "bin_at", "gamma", "sin",
    "cos", "tan", "asin", "acos", "atan", "atan2", "pi", "rand", "range",
    "bitset_count_ones", "binary_and", "binary_or", "binary_xor",
    "binary_not", "binary_shift_left", "binary_shift_right",
    "ago", "now", "datetime_diff", "datetime_add", "datetime_part",
    "dayofweek", "dayofmonth", "dayofyear", "monthofyear", "weekofyear",
    "startofday", "startofweek", "startofmonth", "startofyear", "endofday",
    "endofweek", "endofmonth", "endofyear", "format_datetime",
    "format_timespan", "getmonth", "getyear", "todatetime", "totimespan",
    "unixtime_seconds_todatetime", "unixtime_microseconds_todatetime",
    "unixtime_milliseconds_todatetime", "unixtime_nanoseconds_todatetime",
    "tostring", "toint", "tolong", "todouble", "toreal", "tobool",
    "todynamic", "tohex", "toguid", "tounixtime",
    "iff", "iif", "case", "coalesce", "max_of", "min_of",
    "array_length", "array_sum", "array_index_of", "array_slice",
    "array_split", "array_concat", "array_reverse", "array_rotate_left",
    "array_rotate_right", "array_shift_left", "array_shift_right",
    "array_sort_asc", "array_sort_desc", "bag_keys", "bag_merge",
    "bag_pack", "bag_remove_keys", "pack", "pack_array", "zip",
    "set_union", "set_intersect", "set_difference", "set_has_element",
    "geo_distance_2points", "geo_point_in_circle", "geo_point_in_polygon",
    "ipv4_is_match", "ipv4_is_in_range", "ipv4_is_private", "ipv6_is_match",
    "hash", "hash_sha256", "hash_md5", "hash_sha1", "gettype",
    "percentile", "countif", "dcountif", "dcount", "count", "sum", "avg",
    "min", "max", "make_set", "make_list", "arg_max", "arg_min",
    "stdev", "stdevp", "variance", "variancep", "series_stats",
    "series_decompose_anomalies", "series_fit_line", "series_outliers",
})


def _extract_referenced_fields(expression: str) -> Set[str]:
    without_strings = _STRING_LITERAL_RE.sub(" ", expression)
    function_names = {m.group(1) for m in _FUNCTION_CALL_RE.finditer(without_strings)}
    tokens = _IDENTIFIER_RE.findall(without_strings)
    return {t for t in tokens if t not in function_names and t.lower() not in _KQL_OPERATOR_WORDS}


def _extract_unknown_function_calls(expression: str) -> Set[str]:
    """The companion check to _extract_referenced_fields: a function name
    is skipped there (not checked as a field), but it still needs to be
    a real KQL function — otherwise a hallucinated function name compiles
    and ships exactly like a hallucinated field would."""
    without_strings = _STRING_LITERAL_RE.sub(" ", expression)
    function_names = {m.group(1) for m in _FUNCTION_CALL_RE.finditer(without_strings)}
    return {f for f in function_names if f.lower() not in _KNOWN_KQL_FUNCTIONS}


# Aggregation functions (count, sum, stdev, percentile, ...) only exist as
# part of a summarize clause in real KQL — there is no scalar/row-wise form
# of any of them, so a call to one inside an ExtendStage expression is
# invalid KQL even though the function name itself is real and would pass
# _extract_unknown_function_calls. Found live: the model computed a
# regularity/deviation statistic with "extend X = stdev(Count)" instead of
# moving the stdev() into the SummarizeStage it belongs in — a single-row
# scalar context has no group of rows for stdev to operate over. min/max
# are aggregate-only too; their scalar two-argument counterparts are the
# differently-named min_of()/max_of(), already in _KNOWN_KQL_FUNCTIONS.
_AGGREGATE_ONLY_FUNCTIONS = frozenset({
    "count", "dcount", "countif", "dcountif", "sum", "avg", "min", "max",
    "percentile", "make_set", "make_list", "arg_max", "arg_min",
    "stdev", "stdevp", "variance", "variancep",
})


def _extract_aggregate_only_function_calls(expression: str) -> Set[str]:
    without_strings = _STRING_LITERAL_RE.sub(" ", expression)
    function_names = {m.group(1) for m in _FUNCTION_CALL_RE.finditer(without_strings)}
    return {f for f in function_names if f.lower() in _AGGREGATE_ONLY_FUNCTIONS}


# Filter.value is always compared as a literal — a string that merely
# LOOKS like a KQL function call (e.g. "ago(1h)", "startofday(now())") is
# matched against that exact text, never evaluated. Found live, twice:
# the model tried to express relative-time filtering this way instead of
# using SummarizeStage.time_window (which compiles to a real bin() call)
# or an ExtendStage (a real, unquoted expression) — a silently-useless
# filter that looks plausible but can never match real data.
_FUNCTION_CALL_VALUE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\([^()]*\)$")


def _is_function_call_like_value(value) -> bool:
    return isinstance(value, str) and bool(_FUNCTION_CALL_VALUE_RE.match(value.strip()))


def _is_degenerate_count_filter(operator, value) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if operator == FilterOperator.GT:
        return value < 1
    if operator == FilterOperator.GTE:
        return value <= 1
    return False


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


# Recurring failure class found scoring live results (not from a single
# isolated case): the model inventing a specific string literal that
# appears nowhere in the input — a malware name used as a user ID, a
# fabricated absolute date, an invented file path. A hard error here
# would be too risky: plenty of CORRECT literals are legitimate domain
# knowledge that never appears in casual text either (e.g. "53"/"445" for
# well-known ports — already numeric, so excluded below — or a value the
# Extraction Agent recalled from its own knowledge of a named tool, e.g.
# "accepteula"). So this is advisory only: a warning on the final,
# otherwise-valid result, not a blocking failure that could reject an
# already-correct IR over a true-but-uncommon literal.
_COMMON_LITERAL_VALUES = frozenset({
    "true", "false", "success", "failure", "denied", "allowed", "blocked",
    "permit", "deny", "error", "warning", "info", "unknown", "none", "null",
    # Real DNS RCODE enum values — standard, not invented, and routinely
    # absent from casual text even when correct. Empirically the single
    # biggest false-positive source on a live trial run before this list
    # was added (PROJECT_STATUS.md §4P).
    "noerror", "nxdomain", "servfail", "refused", "formerr", "notimp",
})

# A value that's the input's own wording plus a common executable/script
# extension (rundll32 -> rundll32.exe) isn't invented, just normalized —
# also a measured false-positive source on the same trial run.
_COMMON_VALUE_SUFFIXES = (".exe", ".dll", ".com", ".bat", ".ps1", ".sh")


def _is_ungrounded_literal(value, nl_description: Optional[str]) -> bool:
    if not nl_description or not isinstance(value, str):
        return False
    stripped = value.strip()
    if len(stripped) < 4 or stripped.lower() in _COMMON_LITERAL_VALUES:
        return False
    lowered = stripped.lower()
    haystack = nl_description.lower()
    if lowered in haystack:
        return False
    for suffix in _COMMON_VALUE_SUFFIXES:
        if lowered.endswith(suffix) and lowered[: -len(suffix)] in haystack:
            return False
    return True


def _collect_ungrounded_literal_warnings(pipeline: KqlPipeline, nl_description: Optional[str]) -> List[str]:
    if not nl_description:
        return []
    warnings: List[str] = []

    def check(f) -> None:
        if _is_ungrounded_literal(f.value, nl_description):
            warnings.append(
                f"filter value {f.value!r} on field '{f.field}' does not appear "
                f"in the input description and isn't a common status/boolean "
                f"value — verify it wasn't invented rather than read from the input."
            )

    for stage in pipeline.stages:
        if stage.type == "where":
            for f in stage.filters:
                if f.type == "filter":
                    check(f)
                elif f.type == "group":
                    for c in f.conditions:
                        if c.type == "and_group":
                            for sub in c.conditions:
                                check(sub)
                        else:
                            check(c)
        elif stage.type == "join":
            warnings.extend(_collect_ungrounded_literal_warnings(stage.right_pipeline, nl_description))

    return warnings


# §4AD — generalizes the NXDomainCount bug (PROJECT_STATUS.md §4AC):
# an aggregation's result_alias naming a SPECIFIC CONDITION/STATUS
# ("NXDomainCount", "FailedLoginCount", "DeletedKeyCount") is a promise
# that a WhereStage filtered to exactly that condition before the
# aggregation ran. Found live: an alias claimed "NXDomainCount" while
# the actual aggregation was a plain count() with no NXDOMAIN filter
# anywhere upstream — the alias actively lied about what the number
# measured, invisible to every other check (schema-valid, syntax-valid,
# correctly named). This is the same meta-shape as other bugs already
# fixed in this project's history (a literal that should have been a
# field_ref; a property filtered on the wrong entity's field) — an
# artifact claiming something its own structure doesn't deliver.
#
# Two earlier versions of this check were tried and rejected, live
# calibrated against fresh train-split queries before shipping (this
# project's standing discipline, §4P) — both real negative results,
# kept here rather than silently discarded:
#
# v1 (STOPLIST: flag any camelCase token not in a generic-words list):
# 4/12 fired, 4/4 false positives. "DistinctProcesses", "QueriedDomains",
# "SubdomainCount", "AdFindHashes"/"CommandLines"/"ExecutionCount" all
# name the KIND of thing aggregated (a content/entity descriptor), not
# a condition rows were filtered to — a generic-words stoplist cannot
# tell that apart from a real example like "NXDomain."
#
# v2 (ALLOWLIST: only check a curated list of real ASIM status/outcome
# vocabulary — "failed", "error", "nxdomain", etc.): narrowed scope,
# re-calibrated on a FRESH 15-query sample — still 2/2 false positives.
# Both had a perfectly correct upstream filter ("HttpStatusCode >= 400"
# for "ErrorCount"; "EventResult != Success" for "FailedConnectionCount")
# that the literal-substring check couldn't recognize, because a
# correct filter almost always uses SCHEMA vocabulary (field names,
# enum values, numeric thresholds), not the NATURAL-LANGUAGE word the
# alias happens to use — two different vocabularies that don't share
# substrings even when the logic is exactly right. NXDomainCount's
# original bug happened to be checkable by substring only because DNS
# response codes are one of the rare cases where the schema's own enum
# value ("NXDOMAIN") IS the natural-language word — not the general case.
#
# v3 (shipped): rather than checking WHICH filter matches WHICH word
# (the part that doesn't generalize), check WHETHER ANY WhereStage
# filter exists upstream AT ALL before the aggregation. The original
# bug's actual shape was a make-series/summarize with ZERO preceding
# filters of any kind, not almost-right vocabulary — a much narrower,
# structural claim with no semantic matching to get wrong. Lower
# recall (a real wrong-vocabulary mismatch like a hypothetical
# "AdminAccessCount" with an upstream filter on the wrong field would
# not be caught) but the false-positive rate measured at v1/v2 made
# shipping either of those irresponsible — still advisory, never a
# hard error, per the same §4P calibration principle.
_ALIAS_CONDITION_TERMS = {
    "nxdomain", "noerror", "servfail", "refused", "failed", "failure",
    "success", "successful", "denied", "blocked", "allowed", "permitted",
    "admin", "administrator", "external", "internal", "private", "public",
    "suspicious", "malicious", "benign", "encrypted", "unencrypted",
    "deleted", "created", "modified", "renamed", "elevated", "privileged",
    "anonymous", "unauthorized", "authorized", "expired", "revoked",
    "compromised", "outbound", "inbound", "critical", "highrisk", "lowrisk",
    "error", "errors",
}

_ALIAS_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _alias_implied_terms(alias: str) -> List[str]:
    """Splits a result_alias on camelCase boundaries, keeping only
    words on the curated condition/status allowlist above — see the
    long comment on that list for why a broader stoplist-based
    approach was tried first and rejected on measured false-positive
    rate before this one shipped."""
    words = _ALIAS_CAMEL_BOUNDARY.sub(" ", alias).split()
    return [w for w in words if w.lower() in _ALIAS_CONDITION_TERMS]


def _collect_alias_implies_filter_warnings(pipeline: KqlPipeline) -> List[str]:
    """v3 (see the long comment above _ALIAS_CONDITION_TERMS for why):
    checks WHETHER any WhereStage filter exists upstream at all before
    an aggregation whose alias implies a condition — not WHICH filter,
    since matching alias vocabulary against filter vocabulary measured
    too many false positives to ship (correct filters routinely use
    schema vocabulary — field names, enum values, numeric thresholds —
    that shares no substring with the alias's natural-language word)."""
    warnings: List[str] = []
    any_where_seen = False

    def check_aggregations(aggregations) -> None:
        for agg in aggregations:
            terms = _alias_implied_terms(agg.result_alias)
            if terms and not any_where_seen:
                warnings.append(
                    f"aggregation alias '{agg.result_alias}' implies a filter on "
                    f"'{terms[0]}', but no WhereStage filters anything upstream in "
                    f"this pipeline at all — verify this aggregation is actually "
                    f"computed over a filtered subset, not a plain count/aggregation "
                    f"over everything with a misleading name."
                )

    for stage in pipeline.stages:
        if stage.type == "where" and stage.filters:
            any_where_seen = True
        elif stage.type == "summarize":
            check_aggregations(stage.aggregations)
        elif stage.type == "make_series":
            check_aggregations(stage.aggregations)
        elif stage.type == "join":
            warnings.extend(_collect_alias_implies_filter_warnings(stage.right_pipeline))

    return warnings


def closest_match(field_name: str, candidates) -> Optional[str]:
    if not candidates:
        return None
    return min(candidates, key=lambda c: _levenshtein(field_name.lower(), c.lower()))


# ASIM field names follow consistent naming conventions (documented in
# MASTER_PLAN_v2_ast.md §15.3) — a suffix reliably predicts the kind of
# value the field holds even with no sample-value dataset to draw a real
# example from. Repair errors that name a field are more actionable with
# a concrete example of what to put there, not just the field name itself
# — "the model fixes what it's told precisely."
_FIELD_VALUE_HINTS = [
    (re.compile(r"PortNumber$"), 'a port number, e.g. 443'),
    (re.compile(r"IpAddr$"), 'an IP address string, e.g. "10.0.0.5"'),
    (re.compile(r"(Username|UserId)$"), 'an account name string, e.g. "jsmith"'),
    (re.compile(r"(^TimeGenerated$|Time)$"), "a datetime value"),
    (re.compile(r"(Count|Length|Size|Bytes|Duration)$"), "a number"),
    (re.compile(r"(Url|Domain|Hostname|FQDN)$"), "a URL/hostname string"),
    (re.compile(r"(StatusCode|ResultDetails|ResponseCode)$"), "a numeric or short status/result code"),
    (re.compile(r"(CommandLine|Path)$"), "a file path or command-line string"),
]


def _field_value_hint(field_name: str) -> str:
    for pattern, hint in _FIELD_VALUE_HINTS:
        if pattern.search(field_name):
            return hint
    return ""


def closest_match_with_hint(field_name: str, candidates) -> str:
    """closest_match(), plus a one-line example of the kind of value the
    suggested field actually expects, when its name follows a recognized
    ASIM naming convention. Falls back to bare closest_match() output
    when nothing is recognized or there's no candidate at all."""
    match = closest_match(field_name, candidates)
    if match is None:
        return "none"
    hint = _field_value_hint(match)
    return f"{match} (expects {hint})" if hint else match


@dataclass
class ValidationResult:
    passed: bool
    error_type: Optional[str] = None
    message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    final_schema: Set[str] = field(default_factory=set)


def validate_ir(
    pipeline: KqlPipeline, base_schema: dict, nl_description: Optional[str] = None
) -> ValidationResult:
    """Schema Validator — pure Python, no LLM call.

    Stateful schema tracker: walks the AST pipeline stage by stage,
    maintaining the set of fields actually available at that point (which
    mutates after summarize/extend/project/join), plus a parallel set of
    which of those fields are count-like aggregation results (for the
    degenerate-threshold check). Runs checks in order, short-circuiting on
    the first failure so a repair prompt always addresses exactly one issue.
    """
    source = pipeline.source_table.value if hasattr(pipeline.source_table, "value") else str(pipeline.source_table)
    if source not in base_schema:
        # The schema's source_table type (Union[ASIMEventType, str]) allows
        # a raw/custom table, but the IR Builder is only ever instructed to
        # use ASIM-normalized event types — nothing in its prompt tells it
        # a free-text table name is acceptable. Found live: the model
        # invented "error event" for a description with no real technical
        # signal, and every subsequent field check then failed with an
        # unhelpful "closest match: None" (available_schema was empty)
        # instead of clearly diagnosing the actual problem — the source
        # table itself, not the field names referenced against it.
        return ValidationResult(
            passed=False,
            error_type="INVALID_SOURCE_TABLE",
            message=(
                f"source_table '{source}' is not a recognized ASIM event "
                f"type. Closest: {closest_match(source, base_schema.keys())}. "
                f"Pick one of: {', '.join(sorted(base_schema.keys()))}."
            ),
        )
    available_schema: Set[str] = set(base_schema.get(source, {}).get("fields", []))
    count_like_aliases: Set[str] = set()
    prior_summarize_signature: Optional[tuple] = None

    for idx, stage in enumerate(pipeline.stages):
        if stage.type == "where":
            for f in stage.filters:
                if f.type == "filter":
                    if f.field not in available_schema:
                        return ValidationResult(
                            passed=False,
                            error_type="FIELD_NOT_FOUND",
                            message=(
                                f"Stage {idx} (where): field '{f.field}' not "
                                f"found. Closest: {closest_match_with_hint(f.field, available_schema)}"
                            ),
                        )
                    if f.field_ref is not None and f.field_ref not in available_schema:
                        return ValidationResult(
                            passed=False,
                            error_type="FIELD_NOT_FOUND",
                            message=(
                                f"Stage {idx} (where): field_ref '{f.field_ref}' not "
                                f"found. Closest: {closest_match_with_hint(f.field_ref, available_schema)}"
                            ),
                        )
                    if _is_function_call_like_value(f.value):
                        return ValidationResult(
                            passed=False,
                            error_type="FUNCTION_CALL_AS_LITERAL_VALUE",
                            message=(
                                f"Stage {idx} (where): '{f.field} {f.operator.value} "
                                f"{f.value!r}' — the value looks like a KQL function "
                                f"call written as a string, which is compared as that "
                                f"exact literal text, never evaluated. Use "
                                f"SummarizeStage.time_window for relative time "
                                f"windowing, or an ExtendStage expression (unquoted, "
                                f"real KQL) if you need a computed comparison."
                            ),
                        )
                    if (
                        f.field_ref is None and f.operator in _FIELD_REF_LIKELY_OPERATORS
                        and isinstance(f.value, str) and f.value != f.field
                        and f.value in available_schema
                    ):
                        # The generalization of the §4AA field_ref fix: that
                        # round added the CAPABILITY (a filter CAN compare
                        # against another column), but nothing stops the
                        # model from reverting to the old broken pattern —
                        # writing a real column's name as a quoted string
                        # `value` instead of `field_ref`. That compiles to a
                        # literal string comparison that can never actually
                        # match a real column's value, exactly as silently
                        # wrong as the bug field_ref was built to fix, and
                        # invisible to every other check here (the value IS
                        # a valid string, so FIELD_NOT_FOUND never fires).
                        # The generalization of the literal-provenance
                        # principle (§4P): a literal that should have been
                        # something else, caught by what it actually is, not
                        # by guessing intent.
                        return ValidationResult(
                            passed=False,
                            error_type="LITERAL_MATCHES_SCHEMA_FIELD",
                            message=(
                                f"Stage {idx} (where): '{f.field} {f.operator.value} "
                                f"\"{f.value}\"' — \"{f.value}\" is itself the name of "
                                f"a real column in scope here, not a literal value. "
                                f"This is almost certainly meant to be a field-to-field "
                                f"comparison (e.g. bracketing one event's timestamp "
                                f"against another's, from a join or an earlier stage) "
                                f"written the wrong way — use field_ref=\"{f.value}\" "
                                f"instead of value=\"{f.value}\" so the compiler emits "
                                f"an unquoted column reference instead of a quoted "
                                f"string literal that can never match anything real."
                            ),
                        )
                    if f.field in count_like_aliases and _is_degenerate_count_filter(f.operator, f.value):
                        return ValidationResult(
                            passed=False,
                            error_type="DEGENERATE_THRESHOLD",
                            message=(
                                f"Stage {idx} (where): '{f.field} {f.operator.value} {f.value}' "
                                f"is trivially true for every group that exists in the "
                                f"summarize result (count/distinct_count is always >= 1 for "
                                f"an existing group) — it filters nothing. Use a threshold "
                                f"value that reflects the actual quantity described in the "
                                f"detection, or remove the where stage entirely if the "
                                f"description gives no real number."
                            ),
                        )
                elif f.type == "group":
                    for c in f.conditions:
                        if c.type == "and_group":
                            for sub in c.conditions:
                                if sub.field not in available_schema:
                                    return ValidationResult(
                                        passed=False,
                                        error_type="FIELD_NOT_FOUND",
                                        message=(
                                            f"Stage {idx} (where group, and_group): field "
                                            f"'{sub.field}' not found. Closest: "
                                            f"{closest_match_with_hint(sub.field, available_schema)}"
                                        ),
                                    )
                            continue
                        if c.field not in available_schema:
                            return ValidationResult(
                                passed=False,
                                error_type="FIELD_NOT_FOUND",
                                message=(
                                    f"Stage {idx} (where group): field '{c.field}' not "
                                    f"found. Closest: {closest_match_with_hint(c.field, available_schema)}"
                                ),
                            )
                    if _is_tautological_negation_group(f.conditions):
                        return ValidationResult(
                            passed=False,
                            error_type="TAUTOLOGICAL_FILTER_GROUP",
                            message=(
                                f"Stage {idx} (where group): every condition is a "
                                f"negated check on the same field with a different "
                                f"value (e.g. \"!= 'a' or != 'b'\") — this is always "
                                f"true (nothing can simultaneously equal 'a' and 'b'), "
                                f"so it filters nothing. Excluding several literal "
                                f"values means ALL of those exclusions must hold "
                                f"together — use separate, plain AND-ed Filter "
                                f"entries (NOT a FilterGroup, which is an OR) for "
                                f"each one."
                            ),
                        )
                    if _has_complementary_pair(f.conditions):
                        return ValidationResult(
                            passed=False,
                            error_type="TAUTOLOGICAL_FILTER_GROUP",
                            message=(
                                f"Stage {idx} (where group): two conditions check "
                                f"the same field against the same value with "
                                f"opposite operators (e.g. \"in (X) or !in (X)\") — "
                                f"this is a direct tautology (X or not-X), always "
                                f"true. Pick the one condition you actually mean, "
                                f"or remove the FilterGroup if you only need one "
                                f"of them."
                            ),
                        )
                    if _has_tautological_range_pair(f.conditions):
                        return ValidationResult(
                            passed=False,
                            error_type="TAUTOLOGICAL_FILTER_GROUP",
                            message=(
                                f"Stage {idx} (where group): two conditions form a "
                                f"numeric lower bound and upper bound on the SAME "
                                f"field (e.g. \"X > 0\" and \"X <= 60\") joined by "
                                f"OR — every number satisfies at least one side "
                                f"(e.g. -5 <= 60; 1000 > 0), so this is always "
                                f"true and filters nothing. A range like 'between "
                                f"A and B' or 'after A but within B' needs BOTH "
                                f"bounds to hold AT ONCE — use two separate, "
                                f"plain AND-ed Filter entries (not a FilterGroup) "
                                f"instead."
                            ),
                        )

        elif stage.type == "summarize":
            new_schema: Set[str] = set(stage.group_by or [])
            new_count_like: Set[str] = set()
            if stage.group_by:
                for gb in stage.group_by:
                    if gb not in available_schema:
                        return ValidationResult(
                            passed=False,
                            error_type="FIELD_NOT_FOUND",
                            message=(
                                f"Stage {idx} (summarize group_by): field '{gb}' not "
                                f"found. Closest: {closest_match_with_hint(gb, available_schema)}"
                            ),
                        )
                if "TimeGenerated" in stage.group_by and stage.time_window:
                    return ValidationResult(
                        passed=False,
                        error_type="REDUNDANT_RAW_TIME_FIELD_IN_GROUP_BY",
                        message=(
                            f"Stage {idx} (summarize): group_by lists the raw "
                            f"'TimeGenerated' field AND time_window is set — "
                            f"time_window already compiles to "
                            f"bin(TimeGenerated, ...) in the by-clause, so "
                            f"listing the raw field too groups by the exact "
                            f"per-row timestamp as well, which collapses every "
                            f"aggregation in this stage to ~1 row each "
                            f"(every row has a near-unique timestamp). Remove "
                            f"'TimeGenerated' from group_by — time_window is "
                            f"the only thing needed to bucket by time."
                        ),
                    )

            seen_aliases: Set[str] = set()
            for agg in stage.aggregations:
                if agg.result_alias in seen_aliases:
                    return ValidationResult(
                        passed=False,
                        error_type="DUPLICATE_AGGREGATION_ALIAS",
                        message=(
                            f"Stage {idx} (summarize): result_alias "
                            f"'{agg.result_alias}' is used more than once — "
                            f"every column in the same summarize clause needs "
                            f"a distinct alias."
                        ),
                    )
                seen_aliases.add(agg.result_alias)

                if agg.field and agg.field not in available_schema:
                    return ValidationResult(
                        passed=False,
                        error_type="FIELD_NOT_FOUND",
                        message=(
                            f"Stage {idx} (summarize agg): field '{agg.field}' not "
                            f"found. Closest: {closest_match_with_hint(agg.field, available_schema)}"
                        ),
                    )
                if agg.function in _FUNCTIONS_REQUIRING_FIELD and not agg.field:
                    return ValidationResult(
                        passed=False,
                        error_type="AGGREGATION_MISSING_FIELD",
                        message=(
                            f"Stage {idx} (summarize): aggregation function "
                            f"'{agg.function.value}' requires a field — only "
                            f"count() takes zero arguments in KQL. Set the "
                            f"field to the column to {agg.function.value} over."
                        ),
                    )
                if agg.function == AggregationFunction.PERCENTILE:
                    if agg.percentile is None or not (0 <= agg.percentile <= 100):
                        return ValidationResult(
                            passed=False,
                            error_type="INVALID_PERCENTILE_VALUE",
                            message=(
                                f"Stage {idx} (summarize): aggregation function is "
                                f"'percentile' but percentile is missing or out of "
                                f"range — set it to the percentile to compute, "
                                f"0-100 (e.g. 95 for the 95th percentile)."
                            ),
                        )
                new_schema.add(agg.result_alias)
                if agg.function in _DEGENERATE_COUNT_FUNCTIONS:
                    new_count_like.add(agg.result_alias)

            for arg_pick, label in ((stage.arg_max, "arg_max"), (stage.arg_min, "arg_min")):
                if arg_pick is None:
                    continue
                if arg_pick.order_field not in available_schema:
                    return ValidationResult(
                        passed=False,
                        error_type="FIELD_NOT_FOUND",
                        message=(
                            f"Stage {idx} (summarize {label}): order_field "
                            f"'{arg_pick.order_field}' not found. Closest: "
                            f"{closest_match_with_hint(arg_pick.order_field, available_schema)}"
                        ),
                    )
                if arg_pick.carry_fields == ["*"]:
                    carried = available_schema - {arg_pick.order_field} if arg_pick.result_alias else available_schema
                    new_schema.update(carried)
                else:
                    for cf in arg_pick.carry_fields:
                        if cf not in available_schema:
                            return ValidationResult(
                                passed=False,
                                error_type="FIELD_NOT_FOUND",
                                message=(
                                    f"Stage {idx} (summarize {label}): carry_fields "
                                    f"entry '{cf}' not found. Closest: "
                                    f"{closest_match_with_hint(cf, available_schema)}"
                                ),
                            )
                        new_schema.add(cf)
                # When result_alias is given, the order_field's value is
                # only available under the alias (matching real KQL —
                # "LatestIndicatorTime = arg_max(TimeGenerated, *)" does
                # not also leave a separate "TimeGenerated" column).
                new_schema.add(arg_pick.result_alias or arg_pick.order_field)

            current_summarize_signature = (tuple(sorted(stage.group_by or [])), stage.time_window)
            has_spread_agg = any(agg.function in _SPREAD_FUNCTIONS for agg in stage.aggregations)
            if has_spread_agg and current_summarize_signature == prior_summarize_signature:
                return ValidationResult(
                    passed=False,
                    error_type="DEGENERATE_SPREAD_OVER_SINGLE_ROW",
                    message=(
                        f"Stage {idx} (summarize): this stage computes "
                        f"stdev()/variance() over the immediately preceding "
                        f"SummarizeStage's results, but uses the EXACT SAME "
                        f"group_by and time_window as that stage — which "
                        f"means every group from the prior stage already "
                        f"collapsed to exactly one row, and stdev()/"
                        f"variance() of a single value is always 0 or null. "
                        f"The prior stage must use a FINER time_window (e.g. "
                        f"a daily bucket feeding into a 14-day reduction) so "
                        f"this stage has multiple rows per group to compute "
                        f"spread over."
                    ),
                )
            prior_summarize_signature = current_summarize_signature

            available_schema = new_schema
            count_like_aliases = new_count_like

            if (stage.aggregations or stage.arg_max or stage.arg_min) and not stage.time_window:
                return ValidationResult(
                    passed=False,
                    error_type="MISSING_TIME_WINDOW",
                    message=(
                        f"Stage {idx} (summarize): aggregations present but "
                        f"time_window is null — this would scan the entire "
                        f"table with no time bound."
                    ),
                )
            if stage.time_window and not _ISO8601_DURATION.match(stage.time_window):
                return ValidationResult(
                    passed=False,
                    error_type="INVALID_TIME_WINDOW",
                    message=(
                        f"Stage {idx} (summarize): time_window "
                        f"'{stage.time_window}' is not a valid ISO 8601 "
                        f"duration (e.g. 'PT5M', 'PT1H', 'P1D')."
                    ),
                )

        elif stage.type == "extend":
            for comp in stage.computed_fields:
                agg_only_fns = _extract_aggregate_only_function_calls(comp.expression)
                if agg_only_fns:
                    bad_fn = sorted(agg_only_fns)[0]
                    return ValidationResult(
                        passed=False,
                        error_type="AGGREGATE_FUNCTION_IN_EXTEND",
                        message=(
                            f"Stage {idx} (extend): computed field "
                            f"'{comp.alias}' calls '{bad_fn}(...)', which is "
                            f"a KQL aggregation function — it only exists "
                            f"inside a summarize clause, operating over a "
                            f"group of rows, and has no scalar/row-wise form. "
                            f"Move this computation into a SummarizeStage's "
                            f"aggregations list (give it a result_alias), "
                            f"then reference that alias here if you still "
                            f"need to combine it with something else."
                        ),
                    )
                unknown_fns = _extract_unknown_function_calls(comp.expression)
                if unknown_fns:
                    bad_fn = sorted(unknown_fns)[0]
                    return ValidationResult(
                        passed=False,
                        error_type="UNKNOWN_FUNCTION_IN_EXPRESSION",
                        message=(
                            f"Stage {idx} (extend): computed field "
                            f"'{comp.alias}' calls '{bad_fn}(...)', which is "
                            f"not a real KQL function — this will fail at "
                            f"query time. Use a real KQL function, or "
                            f"restructure the expression without it."
                        ),
                    )
                referenced = _extract_referenced_fields(comp.expression)
                unknown = referenced - available_schema
                if unknown:
                    bad_field = sorted(unknown)[0]
                    return ValidationResult(
                        passed=False,
                        error_type="FIELD_NOT_FOUND",
                        message=(
                            f"Stage {idx} (extend): computed field "
                            f"'{comp.alias}' references '{bad_field}', which "
                            f"is not in the available schema at this point in "
                            f"the pipeline. Closest: "
                            f"{closest_match_with_hint(bad_field, available_schema)}"
                        ),
                    )
                available_schema.add(comp.alias)
                # A computed field is not itself a count — clear any stale
                # count-like marker an alias of the same name might have
                # carried from an earlier stage, to avoid a false
                # DEGENERATE_THRESHOLD match against a non-count value.
                count_like_aliases.discard(comp.alias)

        elif stage.type == "join":
            right_validation = validate_ir(stage.right_pipeline, base_schema)
            if not right_validation.passed:
                return right_validation
            for join_key in stage.join_on:
                if join_key not in available_schema:
                    return ValidationResult(
                        passed=False,
                        error_type="JOIN_KEY_NOT_FOUND_LEFT",
                        message=(
                            f"Stage {idx} (join): key '{join_key}' not in "
                            f"left schema. Closest: "
                            f"{closest_match_with_hint(join_key, available_schema)}"
                        ),
                    )
                if join_key not in right_validation.final_schema:
                    return ValidationResult(
                        passed=False,
                        error_type="JOIN_KEY_NOT_FOUND_RIGHT",
                        message=(
                            f"Stage {idx} (join): key '{join_key}' not in "
                            f"right schema. Closest: "
                            f"{closest_match_with_hint(join_key, right_validation.final_schema)}"
                        ),
                    )
            available_schema.update(right_validation.final_schema)
            # A join can re-expand row cardinality (a 1-to-many match),
            # so a prior summarize's "already collapsed to 1 row per
            # group" assumption is no longer safe to carry across one —
            # avoids a false DEGENERATE_SPREAD_OVER_SINGLE_ROW on patterns
            # like percentile-of-aggregates that deliberately join back
            # into a wider row set before reducing again.
            prior_summarize_signature = None

        elif stage.type == "union":
            if not stage.tables:
                return ValidationResult(
                    passed=False,
                    error_type="EMPTY_UNION",
                    message=f"Stage {idx} (union): tables list is empty.",
                )
            # Schemas for arbitrary raw table names aren't known to this
            # validator, so available_schema is left unchanged — a
            # conservative choice that can't validate newly-available
            # columns from the unioned tables, but also can't be fooled
            # into accepting a field that doesn't exist anywhere.
            prior_summarize_signature = None

        elif stage.type == "project":
            for proj_field in stage.fields:
                if proj_field not in available_schema:
                    return ValidationResult(
                        passed=False,
                        error_type="FIELD_NOT_FOUND",
                        message=(
                            f"Stage {idx} (project): field '{proj_field}' not "
                            f"found. Closest: {closest_match_with_hint(proj_field, available_schema)}"
                        ),
                    )
            available_schema = set(stage.fields)
            count_like_aliases &= available_schema

        elif stage.type == "top":
            if stage.by_field not in available_schema:
                return ValidationResult(
                    passed=False,
                    error_type="FIELD_NOT_FOUND",
                    message=(
                        f"Stage {idx} (top): field '{stage.by_field}' not "
                        f"found. Closest: {closest_match_with_hint(stage.by_field, available_schema)}"
                    ),
                )

        elif stage.type == "mv_expand":
            for mv_field in stage.fields:
                if mv_field not in available_schema:
                    return ValidationResult(
                        passed=False,
                        error_type="FIELD_NOT_FOUND",
                        message=(
                            f"Stage {idx} (mv_expand): field '{mv_field}' not "
                            f"found. Closest: {closest_match_with_hint(mv_field, available_schema)}"
                        ),
                    )
            if stage.as_type and len(stage.fields) != 1:
                return ValidationResult(
                    passed=False,
                    error_type="MV_EXPAND_AS_TYPE_WITH_MULTIPLE_FIELDS",
                    message=(
                        f"Stage {idx} (mv_expand): as_type is set but fields "
                        f"lists {len(stage.fields)} fields — `to typeof(...)` "
                        f"only applies to a single-field mv-expand. Either drop "
                        f"as_type, or expand exactly one field."
                    ),
                )
            # mv-expand fans one row into many per expanded value but
            # doesn't change which COLUMNS are available — every field
            # already in scope stays in scope, the listed fields just
            # change from array-typed to scalar-typed per output row.

        elif stage.type == "make_series":
            new_schema = set(stage.group_by or [])
            new_schema.add("TimeGenerated")  # make-series always emits the bucketed time axis as its own series
            if stage.group_by:
                for gb in stage.group_by:
                    if gb not in available_schema:
                        return ValidationResult(
                            passed=False,
                            error_type="FIELD_NOT_FOUND",
                            message=(
                                f"Stage {idx} (make_series group_by): field "
                                f"'{gb}' not found. Closest: "
                                f"{closest_match_with_hint(gb, available_schema)}"
                            ),
                        )
            for agg in stage.aggregations:
                if agg.field and agg.field not in available_schema:
                    return ValidationResult(
                        passed=False,
                        error_type="FIELD_NOT_FOUND",
                        message=(
                            f"Stage {idx} (make_series agg): field "
                            f"'{agg.field}' not found. Closest: "
                            f"{closest_match_with_hint(agg.field, available_schema)}"
                        ),
                    )
                if agg.function in _FUNCTIONS_REQUIRING_FIELD and not agg.field:
                    return ValidationResult(
                        passed=False,
                        error_type="AGGREGATION_MISSING_FIELD",
                        message=(
                            f"Stage {idx} (make_series): aggregation function "
                            f"'{agg.function.value}' requires a field — only "
                            f"count() takes zero arguments in KQL."
                        ),
                    )
                new_schema.add(agg.result_alias)
            if not _ISO8601_DURATION.match(stage.step):
                return ValidationResult(
                    passed=False,
                    error_type="INVALID_TIME_WINDOW",
                    message=(
                        f"Stage {idx} (make_series): step '{stage.step}' is "
                        f"not a valid ISO 8601 duration (e.g. 'PT1H', 'P1D')."
                    ),
                )
            available_schema = new_schema
            count_like_aliases = set()
            prior_summarize_signature = None

        elif stage.type == "series_anomaly":
            if stage.series_field not in available_schema:
                return ValidationResult(
                    passed=False,
                    error_type="FIELD_NOT_FOUND",
                    message=(
                        f"Stage {idx} (series_anomaly): series_field "
                        f"'{stage.series_field}' not found — this must be a "
                        f"series-valued aggregation alias produced by a prior "
                        f"MakeSeriesStage. Closest: "
                        f"{closest_match_with_hint(stage.series_field, available_schema)}"
                    ),
                )
            available_schema = set(available_schema)
            available_schema.update({stage.flag_alias, stage.score_alias, stage.baseline_alias})

        elif stage.type == "parse":
            if stage.source_field not in available_schema:
                return ValidationResult(
                    passed=False,
                    error_type="FIELD_NOT_FOUND",
                    message=(
                        f"Stage {idx} (parse): source_field "
                        f"'{stage.source_field}' not found. Closest: "
                        f"{closest_match_with_hint(stage.source_field, available_schema)}"
                    ),
                )
            column_names = [t.value for t in stage.tokens if t.type == "column"]
            if not column_names:
                return ValidationResult(
                    passed=False,
                    error_type="PARSE_EXTRACTS_NOTHING",
                    message=(
                        f"Stage {idx} (parse): every token is 'literal' or "
                        f"'wildcard' — at least one 'column' token is required, "
                        f"or this stage extracts nothing and shouldn't exist."
                    ),
                )
            if len(column_names) != len(set(column_names)):
                return ValidationResult(
                    passed=False,
                    error_type="DUPLICATE_PARSE_COLUMN",
                    message=(
                        f"Stage {idx} (parse): two or more 'column' tokens "
                        f"share the same name — each extracted column needs "
                        f"its own distinct name."
                    ),
                )
            available_schema = set(available_schema)
            available_schema.update(column_names)

    return ValidationResult(
        passed=True,
        final_schema=available_schema,
        warnings=(
            _collect_ungrounded_literal_warnings(pipeline, nl_description)
            + _collect_alias_implies_filter_warnings(pipeline)
        ),
    )
