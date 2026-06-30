"""True end-to-end integration tests: the real Extraction Agent and IR
Builder Agent (a live LLM call, no mocking) wired through the real repair
loop, validator, and compiler. Skipped automatically when no LLM backend
is configured.

This project's own history (see PROJECT_STATUS.md) found bugs that ONLY
showed up when the full chain ran for real — an isolated unit trace of
validate_ir() in isolation passing while the same case failed 0/4 through
run_system_b(), because run_with_repair calls additional checks
(_check_constraint_traceability) a unit-level trace skipped. These tests
exist specifically to catch that class of gap, anchored on the exact live
cases this round traced and fixed:
  - 5b6ae038 (sdelete renamed-binary evasion) — was inverting/hallucinating
    command-line flags on the -original paraphrase.
  - 8717e498 (SMB baseline-vs-current) — was failing 100% of the time on
    BOTH paraphrases due to a false THRESHOLD_VALUE_MISMATCH on an
    extend-derived comparison field.

Costs real API calls — kept to a small, fixed set of regression anchors,
not a full sweep of the dataset (that's eval/run_comparison.py's job).
"""
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.pipeline.system_b import run_system_b

pytestmark = pytest.mark.skipif(
    not (os.getenv("LLM_PROVIDER") and os.getenv("AZURE_FOUNDRY_API_KEY")) and not (
        os.getenv("LLM_PROVIDER") == "ollama"
    ),
    reason="no LLM backend configured (set LLM_PROVIDER + provider credentials in .env to run)",
)

ASIM_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "schema", "asim_field_reference.json"
)


@pytest.fixture(scope="module")
def asim_schema():
    import json
    with open(ASIM_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def extraction_agent():
    return ExtractionAgent()


@pytest.fixture(scope="module")
def ir_builder():
    return IRBuilderAgent()


def test_sdelete_renamed_binary_evasion_succeeds_with_real_flags_not_invented_ones(
    asim_schema, extraction_agent, ir_builder
):
    nl = (
        "This detection looks for command line parameters associated with the use of "
        "Sysinternals sdelete (https://docs.microsoft.com/sysinternals/downloads/sdelete) "
        "to delete multiple files on a host's C drive.\n"
        "A threat actor may re-name the tool to avoid detection and then use it for "
        "destructive attacks on a host."
    )
    result = run_system_b(nl, asim_schema, extraction_agent, ir_builder, max_attempts=3)

    assert result.success is True, f"reason={result.reason}"
    kql = result.kql.lower()
    # The four real sdelete flags must all be present; "-p" is a model-
    # invented flag seen live before the Extraction Agent fix.
    for real_flag in ("accepteula", '"-s"', '"-r"', '"-q"'):
        assert real_flag in kql, f"missing real flag {real_flag} in:\n{result.kql}"
    assert '"-p"' not in kql, f"invented flag '-p' leaked into:\n{result.kql}"
    # Evasion logic must exclude the literal name, never require it.
    assert "!endswith" in kql


def test_smb_baseline_vs_current_succeeds_on_explicit_sop_description(
    asim_schema, extraction_agent, ir_builder
):
    nl = (
        "Using a 14-day baseline (ending 1 day ago) of average SMB (ports 139/445) "
        "connection counts per private-IP source/port pair, flag sources in the most "
        "recent 1-day window whose connection count exceeds the baseline average by "
        "more than 50."
    )
    result = run_system_b(nl, asim_schema, extraction_agent, ir_builder, max_attempts=3)

    assert result.success is True, f"reason={result.reason}"
    assert "join kind=" in result.kql
    assert "50" in result.kql


def test_simple_brute_force_detection_still_succeeds_end_to_end(asim_schema, extraction_agent, ir_builder):
    """Sanity anchor: the easy path (a single-stage, no-join, no-derived-
    field detection) must keep working unaffected by this round's changes
    aimed at the hard, multi-stage cases."""
    nl = (
        "Alert when the same user account fails to authenticate more than 10 times "
        "within a 10 minute window."
    )
    result = run_system_b(nl, asim_schema, extraction_agent, ir_builder, max_attempts=3)

    assert result.success is True, f"reason={result.reason}"
    assert "summarize" in result.kql.lower()


def test_verifier_catches_a_real_logic_inversion_through_the_real_repair_loop(asim_schema, extraction_agent):
    """The VerifierAgent (§4Q) is the one semantic, non-rule-based check in
    the pipeline — schema validation cannot tell an AND from an OR meaning
    something different than intended. Wires a REAL VerifierAgent through
    the real repair loop in BLOCKING mode (verifier_blocking=True) with a
    stubbed IR Builder that deliberately returns the exact known-wrong IR
    found live for 7b3ed03a (an OR where the description needs AND) first,
    then the corrected version — proving the verifier's critique CAN drive
    a successful repair, not just classify a string in isolation. Blocking
    mode is demonstrated here, not recommended for production use: measured
    on the full 45-pair dataset it cost 20+ points of completion/FVR and 33
    points of RRR, almost entirely on a join+bin pattern it systematically
    misjudges (PROJECT_STATUS.md §4Q). The default, advisory mode (used
    everywhere else this agent is wired in) never blocks on this verdict."""
    from unittest.mock import MagicMock

    from src.agents.verifier_agent import VerifierAgent
    from src.ir_engine.ir_schema import (
        ASIMEventType, Filter, FilterGroup, FilterOperator, KqlPipeline, WhereStage,
    )
    from src.pipeline.repair_loop import run_with_repair

    nl = "catch someone running net user or net group with the /domain flag to snoop on accounts"
    extraction = extraction_agent.extract(nl)

    wrong_ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[FilterGroup(conditions=[
            Filter(field="ActingProcessCommandLine", operator=FilterOperator.HAS_ANY, value=["user", "group"]),
            Filter(field="ActingProcessCommandLine", operator=FilterOperator.HAS, value="/domain"),
        ])])],
    )
    fixed_ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[
            FilterGroup(conditions=[
                Filter(field="ActingProcessCommandLine", operator=FilterOperator.HAS, value="user"),
                Filter(field="ActingProcessCommandLine", operator=FilterOperator.HAS, value="group"),
            ]),
            Filter(field="ActingProcessCommandLine", operator=FilterOperator.HAS, value="/domain"),
        ])],
    )
    ir_builder = MagicMock()
    ir_builder.build.side_effect = [wrong_ir, fixed_ir]

    result = run_with_repair(
        extraction, asim_schema, ir_builder, max_attempts=3,
        nl_description=nl, verifier=VerifierAgent(), verifier_blocking=True,
    )

    assert result.success is True, f"reason={result.reason}"
    assert ir_builder.build.call_count == 2
    repair_kwargs = ir_builder.build.call_args_list[1].kwargs
    assert repair_kwargs["repair_error"].error_type.startswith("VERIFIER_")
