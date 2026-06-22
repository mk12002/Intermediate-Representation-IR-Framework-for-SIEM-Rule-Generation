from src.validation.syntax_validators import validate_kql_syntax


def test_simple_valid_query():
    result = validate_kql_syntax('imAuthentication\n| where EventResult == "Failure"')
    assert result.passed


def test_let_statement_before_table_is_valid():
    kql = (
        "let FailureThreshold = 15;\n"
        "imAuthentication\n"
        "| where EventType == 'Logon'\n"
        "| summarize UserCount=dcount(TargetUserId) by SrcDvcIpAddr, bin(TimeGenerated, 5m)\n"
        "| where UserCount > FailureThreshold"
    )
    assert validate_kql_syntax(kql).passed


def test_comment_containing_sql_keyword_does_not_false_positive():
    kql = (
        "imAuthentication\n"
        "// derived from a system that reports differently\n"
        "| where EventResult == \"Failure\""
    )
    assert validate_kql_syntax(kql).passed


def test_string_literal_containing_sql_keyword_does_not_false_positive():
    kql = (
        "imFileEvent\n"
        "| where TargetFileName in (\"select_export.csv\", \"from_backup.zip\")"
    )
    assert validate_kql_syntax(kql).passed


def test_actual_sql_leakage_detected():
    result = validate_kql_syntax("SELECT * FROM imAuthentication WHERE EventResult = 'Failure'")
    assert not result.passed
    assert result.error_type == "SYNTAX_ERROR"


def test_single_equals_in_where_detected():
    result = validate_kql_syntax('imAuthentication\n| where EventResult = "Failure"')
    assert not result.passed


def test_unrecognized_clause_keyword_detected():
    result = validate_kql_syntax("imAuthentication\n| stats count by TargetUsername")
    assert not result.passed


def test_join_clause_is_valid():
    kql = (
        "let threshold = 200;\n"
        "_Im_Dns(responsecodename='NXDOMAIN')\n"
        "| where isnotempty(DnsResponseCodeName)\n"
        "| summarize count() by SrcIpAddr, bin(TimeGenerated,15m)\n"
        "| where count_ > threshold\n"
        "| join kind=inner (_Im_Dns(responsecodename='NXDOMAIN')\n"
        "    ) on SrcIpAddr"
    )
    assert validate_kql_syntax(kql).passed


def test_empty_query_fails():
    assert not validate_kql_syntax("").passed
