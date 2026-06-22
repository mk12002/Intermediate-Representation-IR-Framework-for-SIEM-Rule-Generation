import re
from dataclasses import dataclass, field
from typing import Optional

from .ir_schema import SecurityIR

_ISO8601_DURATION = re.compile(r"^P(?!$)(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+S)?)?$")


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


def closest_match(field: str, candidates: list[str]) -> Optional[str]:
    if not candidates:
        return None
    return min(candidates, key=lambda c: _levenshtein(field.lower(), c.lower()))


@dataclass
class ValidationResult:
    passed: bool
    error_type: Optional[str] = None
    message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


def validate_ir(ir: SecurityIR, asim_schema: dict) -> ValidationResult:
    """Schema Validator — pure Python, no LLM call.

    Runs checks in order, short-circuiting on the first failure so a
    repair prompt always addresses exactly one issue.
    """
    schema_fields = asim_schema[ir.event_type.value]["fields"]

    for f in ir.filters:
        if f.field not in schema_fields:
            return ValidationResult(
                passed=False,
                error_type="FIELD_NOT_FOUND",
                message=(
                    f"field '{f.field}' not found in schema "
                    f"'{ir.event_type.value}'; closest match: "
                    f"{closest_match(f.field, schema_fields)}"
                ),
            )

    if ir.group_by:
        for gb in ir.group_by:
            if gb not in schema_fields:
                return ValidationResult(
                    passed=False,
                    error_type="FIELD_NOT_FOUND",
                    message=(
                        f"group_by field '{gb}' not found in schema "
                        f"'{ir.event_type.value}'; closest match: "
                        f"{closest_match(gb, schema_fields)}"
                    ),
                )

    if ir.aggregation and not ir.time_window:
        return ValidationResult(
            passed=False,
            error_type="MISSING_TIME_WINDOW",
            message=(
                "aggregation present but time_window is null — this "
                "would scan the entire table with no time bound"
            ),
        )

    if ir.time_window and not _ISO8601_DURATION.match(ir.time_window):
        return ValidationResult(
            passed=False,
            error_type="INVALID_TIME_WINDOW",
            message=(
                f"time_window '{ir.time_window}' is not a valid ISO 8601 "
                f"duration (e.g. 'PT5M', 'PT1H', 'P1D')"
            ),
        )

    warnings = []
    if ir.threshold and not ir.aggregation:
        warnings.append(
            "threshold is set but aggregation is null — threshold is only "
            "meaningful applied to an aggregation result; this is a likely "
            "extraction error worth reviewing"
        )

    return ValidationResult(passed=True, warnings=warnings)
