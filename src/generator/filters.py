from src.ir_engine.ir_schema import KQL_AGG_FUNCTIONS, Aggregation, AggregationFunction


def _escape_kql_string(s: str) -> str:
    """Escape backslash and double-quote for a KQL double-quoted string
    literal. Order matters — backslash first, or escaping the quote would
    itself get re-escaped. Found live: an unescaped filter value containing
    a literal backslash (e.g. a Windows path or "\\$Recycle.Bin\\") produced
    malformed KQL like "\\$Recycle.Bin\\" — read as an escaped, unterminated
    quote, not a closed string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _scalar_literal(value) -> str:
    if isinstance(value, str):
        return f'"{_escape_kql_string(value)}"'
    return str(value)


def kql_literal(value) -> str:
    """Format a Python value as a KQL literal. List items are rendered
    per-item (a numeric list like DstPortNumber in (139, 445) must not be
    quoted as strings — found live: AST migration's Filter.value widened to
    allow List[int]/List[float], and this crashed with AttributeError on
    any non-string item before this fix)."""
    if isinstance(value, list):
        return f"({', '.join(_scalar_literal(v) for v in value)})"
    return _scalar_literal(value)


_DURATION_UNITS = {"D": "d", "H": "h", "M": "m", "S": "s"}


def kql_duration(iso8601: str) -> str:
    """Convert an ISO 8601 duration (e.g. "PT5M", "P1D") to a KQL duration literal."""
    body = iso8601[1:]  # strip leading "P"
    time_part = ""
    if "T" in body:
        date_part, time_part = body.split("T", 1)
    else:
        date_part = body

    result = ""
    num = ""
    for ch in date_part:
        if ch.isdigit():
            num += ch
        else:
            result += num + _DURATION_UNITS[ch]
            num = ""
    for ch in time_part:
        if ch.isdigit():
            num += ch
        else:
            result += num + _DURATION_UNITS[ch]
            num = ""
    return result


def kql_agg_fn(fn: AggregationFunction) -> str:
    """Map an IR aggregation function to its KQL function name."""
    return KQL_AGG_FUNCTIONS[fn]


_LIMIT_FUNCTIONS = {AggregationFunction.MAKE_SET, AggregationFunction.MAKE_LIST}


def kql_agg_call(aggregation: Aggregation) -> str:
    """Render a full KQL aggregation function call, including arguments.
    percentile() takes two required arguments (field, N); make_set()/
    make_list() take an optional second argument (a max collection size,
    KQL defaults to 128 when omitted) — every other supported function
    takes zero or one, so neither can share the plain "fn(field)" template
    most aggregations use."""
    fn_name = KQL_AGG_FUNCTIONS[aggregation.function]
    if aggregation.function == AggregationFunction.PERCENTILE:
        return f"{fn_name}({aggregation.field}, {aggregation.percentile})"
    if aggregation.function in _LIMIT_FUNCTIONS and aggregation.limit is not None:
        return f"{fn_name}({aggregation.field}, {aggregation.limit})"
    return f"{fn_name}({aggregation.field or ''})"
