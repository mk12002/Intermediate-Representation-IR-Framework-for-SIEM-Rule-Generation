from src.ir_engine.ir_schema import ASIMEventType, ExtractionOutput, SecurityIR, Threshold, ThresholdOperator
from src.pipeline.repair_loop import _check_constraint_traceability, _extract_unambiguous_number


def _extraction(threshold_language):
    return ExtractionOutput(
        likely_event_type="WebSessionEvent",
        actors=["source"],
        action_description="generates many requests",
        threshold_language=threshold_language,
    )


def _ir(value):
    return SecurityIR(
        event_type=ASIMEventType.WEB_SESSION,
        threshold=Threshold(operator=ThresholdOperator.GT, value=value),
    )


def test_extract_unambiguous_number_single():
    assert _extract_unambiguous_number("more than 50 connections") == 50.0


def test_extract_unambiguous_number_none_when_absent():
    assert _extract_unambiguous_number("many connections") is None
    assert _extract_unambiguous_number(None) is None


def test_extract_unambiguous_number_none_when_multiple():
    """Found this exact pattern live: NL phrases routinely carry both a
    margin number and a lookback-window number in the same sentence
    ("exceeds the 14-day baseline by more than 50") — guessing which one
    a threshold should match would be more likely to misfire than help."""
    assert _extract_unambiguous_number("more than 50 connections over 14 days") is None


def test_constraint_check_flags_a_real_mismatch():
    """The exact failure mode this check exists for: threshold.value
    silently drifting from what the description specifies (e.g. using 1
    instead of the description's explicit 50) while remaining perfectly
    schema-valid — caught nowhere else."""
    result = _check_constraint_traceability(_extraction("more than 50 connections"), _ir(1))
    assert not result.passed
    assert result.error_type == "THRESHOLD_VALUE_MISMATCH"
    assert "50" in result.message


def test_constraint_check_passes_when_values_agree():
    result = _check_constraint_traceability(_extraction("more than 50 connections"), _ir(50))
    assert result is None


def test_constraint_check_skipped_when_threshold_language_is_ambiguous():
    result = _check_constraint_traceability(_extraction("more than 50 connections over 14 days"), _ir(1))
    assert result is None


def test_constraint_check_skipped_when_no_threshold_language():
    result = _check_constraint_traceability(_extraction(None), _ir(50))
    assert result is None


def test_constraint_check_skipped_when_ir_has_no_threshold():
    ir = SecurityIR(event_type=ASIMEventType.WEB_SESSION)
    result = _check_constraint_traceability(_extraction("more than 50 connections"), ir)
    assert result is None
