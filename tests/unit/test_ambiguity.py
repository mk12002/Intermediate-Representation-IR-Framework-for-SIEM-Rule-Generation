from src.clarification.gap_checker import find_ambiguities, scan_ambiguities
from src.ir_engine.ir_schema import (
    Ambiguity, ASIMEventType, Filter, FilterOperator, JoinKind, JoinStage, KqlPipeline, WhereStage,
)


class _StubScanner:
    """Stands in for AmbiguityScanAgent in unit tests — scan_ambiguities
    only requires a .scan(nl, ir) -> List[Ambiguity] method."""

    def __init__(self, to_return):
        self.to_return = to_return
        self.calls = []

    def scan(self, nl_description, ir):
        self.calls.append(nl_description)
        return self.to_return


def test_no_ambiguities_means_empty_list():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")])],
    )
    assert find_ambiguities(ir) == []


def test_a_populated_ambiguity_is_found():
    ir = KqlPipeline(
        source_table=ASIMEventType.FILE,
        stages=[WhereStage(filters=[Filter(field="TargetFilePath", operator=FilterOperator.CONTAINS, value="Recycle")])],
        ambiguities=[Ambiguity(
            description="recycle bin: process executing from the folder vs. a file hidden inside it",
            options=["ProcessEvent: a process executes from the recycle bin folder",
                     "FileEvent: a file is created/hidden inside the recycle bin folder"],
            picked_option="FileEvent: a file is created/hidden inside the recycle bin folder",
        )],
    )
    ambs = find_ambiguities(ir)
    assert len(ambs) == 1
    assert ambs[0].options[0] != ambs[0].picked_option
    assert ambs[0].picked_option in ambs[0].options


def test_ambiguities_inside_a_joins_right_pipeline_are_found_recursively():
    right = KqlPipeline(
        source_table=ASIMEventType.DNS, stages=[],
        ambiguities=[Ambiguity(description="right side fork", options=["a", "b"], picked_option="a")],
    )
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=["SrcIpAddr"])],
    )
    ambs = find_ambiguities(ir)
    assert len(ambs) == 1
    assert ambs[0].description == "right side fork"


def test_ambiguity_requires_at_least_two_options():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Ambiguity(description="only one option", options=["just one"], picked_option="just one")


# --- §4AH: scan_ambiguities merges the dedicated scanner's findings with self-reports ---

def _plain_ir():
    return KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[Filter(field="CommandLine", operator=FilterOperator.CONTAINS, value="Recycle")])],
    )


def _fork(description="event-type fork: process vs file"):
    return Ambiguity(
        description=description,
        options=["ProcessEvent: executes from the folder", "FileEvent: file planted in the folder"],
        picked_option="ProcessEvent: executes from the folder",
    )


def test_scan_ambiguities_surfaces_scanner_findings_when_self_report_is_empty():
    """The whole point of the scanner (§4AG measured self-report at 0/6):
    a fork the IR Builder never self-reported must still surface."""
    scanner = _StubScanner([_fork()])
    merged = scan_ambiguities("some description", _plain_ir(), scanner)
    assert len(merged) == 1
    assert merged[0].description == "event-type fork: process vs file"
    assert scanner.calls == ["some description"]


def test_scan_ambiguities_dedupes_a_fork_found_by_both_paths():
    ir = _plain_ir()
    ir.ambiguities = [_fork("Event-Type Fork: Process vs File  ")]
    scanner = _StubScanner([_fork("event-type fork: process vs file")])
    merged = scan_ambiguities("some description", ir, scanner)
    assert len(merged) == 1
    # the self-reported entry wins on a duplicate — it came from the build itself
    assert merged[0].description == "Event-Type Fork: Process vs File  "


def test_scan_ambiguities_with_nothing_found_anywhere_is_empty():
    merged = scan_ambiguities("some description", _plain_ir(), _StubScanner([]))
    assert merged == []
