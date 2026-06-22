from src.ir_engine.ir_schema import KQL_AGG_FUNCTIONS, AggregationFunction


def kql_literal(value) -> str:
    """Format a Python value as a KQL literal."""
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        quoted = ", ".join('"{}"'.format(v) for v in value)
        return f"({quoted})"
    return str(value)


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
