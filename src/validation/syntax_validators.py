import re
from dataclasses import dataclass
from typing import Optional

# No mature open-source KQL parser is used here — this is a scoped grammar
# check covering the operator subset this project's templates and System A's
# baseline actually produce (where/summarize/project/bin), not full KQL
# grammar coverage. See docs/NL-KQL/MASTER_PLAN.md §23.
_VALID_CLAUSE_KEYWORDS = {
    "where", "summarize", "project", "project-away", "extend", "join", "bin",
    "order", "sort", "top", "render", "union", "mv-expand", "mvexpand",
    "parse", "evaluate", "lookup", "make-series", "invoke", "getschema",
    "distinct", "serialize", "find", "as", "project-rename", "project-reorder",
    "take", "limit", "sample", "count", "scan", "fork", "partition",
}
_LEADING_CLAUSE = re.compile(r"^\s*([\w-]+)\b")
_LET_STATEMENT = re.compile(r"^\s*let\s+\w+\s*=")
_SQL_SPL_LEAKAGE = re.compile(r"\b(SELECT|GROUP\s+BY|stats\s+count)\b", re.IGNORECASE)
_SINGLE_EQUALS_COMPARISON = re.compile(r"(?<![=!<>])=(?!=)(?!~)(?!\s*=)")
_LINE_COMMENT = re.compile(r"//.*$")
# KQL verbatim strings (@'...'/@"...") don't escape backslashes — a lone
# trailing `\` before the closing quote is literal, not an escape introducer.
# Must be matched before the regular escaped-string alternatives, otherwise
# the regular pattern's `\\.` over-consumes past the real closing quote.
_STRING_LITERAL = re.compile(
    r"@'[^']*'|@\"[^\"]*\"|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\""
)


def strip_comments_and_strings(kql: str) -> str:
    """Remove line comments and string-literal contents so substring/regex
    checks below don't false-positive on plain English text or IOC lists
    inside quotes (e.g. a comment or dynamic() array containing the word
    "from")."""
    without_comments = "\n".join(_LINE_COMMENT.sub("", line) for line in kql.splitlines())
    return _STRING_LITERAL.sub("''", without_comments)


@dataclass
class ValidationResult:
    passed: bool
    error_type: Optional[str] = None
    message: Optional[str] = None
    offending_token: Optional[str] = None


def validate_kql_syntax(kql: str) -> ValidationResult:
    if not kql or not kql.strip():
        return ValidationResult(False, "SYNTAX_ERROR", "empty query")

    cleaned = strip_comments_and_strings(kql)
    lines = [l for l in cleaned.strip().splitlines() if l.strip()]

    leak = _SQL_SPL_LEAKAGE.search(cleaned)
    if leak:
        return ValidationResult(
            False, "SYNTAX_ERROR",
            f"SQL/SPL syntax leaked into KQL: '{leak.group(0)}'",
            offending_token=leak.group(0),
        )

    # Skip leading `let NAME = ...;` statements — real-world KQL (and our
    # own few-shot examples) commonly defines variables before the source
    # table reference. The first non-`let` line is the table/source line.
    body_lines = [l for l in lines if not _LET_STATEMENT.match(l)]
    if not body_lines:
        return ValidationResult(False, "SYNTAX_ERROR", "no table reference found")

    for line in body_lines[1:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        match = _LEADING_CLAUSE.match(stripped[1:].strip())
        if not match or match.group(1) not in _VALID_CLAUSE_KEYWORDS:
            token = match.group(1) if match else stripped
            return ValidationResult(
                False, "SYNTAX_ERROR",
                f"unrecognized clause keyword '{token}'",
                offending_token=token,
            )
        if match.group(1) == "where":
            eq = _SINGLE_EQUALS_COMPARISON.search(stripped)
            if eq:
                return ValidationResult(
                    False, "SYNTAX_ERROR",
                    "single '=' used for comparison — KQL requires '=='",
                    offending_token="=",
                )

    return ValidationResult(passed=True)
