"""Live verification of the clarification loop (PROJECT_STATUS.md
§4AF) — a FRESH capability, not a previously-fixed bug class, so this
is its own file rather than added to
test_live_e2e_execution_validation.py (whose own docstring scopes it
to one anchor per historically-fixed bug). Real LLM calls; named with
the live_e2e substring so the standard
`pytest tests/unit tests/integration -q -k "not live_e2e"` skips it.
Run explicitly via `pytest tests/integration/test_clarification_loop.py`.
"""
import json
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from src.agents.ambiguity_scan_agent import AmbiguityScanAgent
from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.clarification import find_gaps, resolve_ambiguity, resolve_clarification, scan_ambiguities
from src.execution.ir_interpreter import pipeline_fires
from src.pipeline.system_b import run_system_b

pytestmark = pytest.mark.skipif(
    not (os.getenv("LLM_PROVIDER") and os.getenv("AZURE_FOUNDRY_API_KEY")) and not (
        os.getenv("LLM_PROVIDER") == "ollama"
    ),
    reason="no LLM backend configured (set LLM_PROVIDER + provider credentials in .env to run)",
)

ASIM_SCHEMA = json.loads(open("data/schema/asim_field_reference.json", encoding="utf-8").read())


@pytest.fixture(scope="module")
def agents():
    return ExtractionAgent(), IRBuilderAgent(use_rag=False)


def test_total_abstention_resolves_to_a_real_firing_pipeline_once_clarified(agents):
    """The maximally under-specified "known IoC" case (also the
    test_total_abstention_never_fires_on_anything anchor's trigger NL)
    abstains with zero groundable signal. Answering the gap-checker's
    one question with concrete IoC values must produce a real,
    correctly-firing pipeline -- not another abstention, not a
    fire-on-everything pipeline."""
    extraction_agent, ir_builder = agents
    nl = (
        "This rule identifies web sessions for which the source IP address is a known IoC. "
        "This rule uses ASIM and supports any web session source that complies with ASIM."
    )
    result = run_system_b(nl, ASIM_SCHEMA, extraction_agent, ir_builder, max_attempts=3)
    assert result.success
    gaps = find_gaps(result.ir)
    assert len(gaps) >= 1, "this NL has zero groundable signal -- the gap-checker must find the abstention's caveat"

    extraction = extraction_agent.extract(nl)
    answers = {gaps[0].caveat_text: "203.0.113.5, 198.51.100.20"}
    clarified = resolve_clarification(extraction, result.ir, gaps, answers, ir_builder, ASIM_SCHEMA)

    assert clarified.success
    assert clarified.ir.abstained is False, "answering the only gap must resolve the total abstention"
    assert pipeline_fires(clarified.ir, [{"SrcIpAddr": "203.0.113.5"}]) is True
    assert pipeline_fires(clarified.ir, [{"SrcIpAddr": "8.8.8.8"}]) is False


def test_threshold_gap_resolves_with_the_supplied_number(agents):
    """A watchlist-driven threshold ("defined in a watchlist with no
    concrete number given") is a different gap KIND (missing_threshold,
    no real-data default offered) than the IoC case above
    (missing_value) -- confirms the classifier and resolver both
    generalize beyond the one case they were built against."""
    extraction_agent, ir_builder = agents
    nl = (
        "There is a normal amount of traffic that goes on a particular port in any organization. "
        "This hunting query identifies port usage higher than a threshold defined in a watchlist "
        "to determine high port usage."
    )
    result = run_system_b(nl, ASIM_SCHEMA, extraction_agent, ir_builder, max_attempts=3)
    assert result.success
    gaps = find_gaps(result.ir)
    assert len(gaps) >= 1
    threshold_gaps = [g for g in gaps if g.kind == "missing_threshold"]
    assert threshold_gaps, f"expected a missing_threshold gap, got kinds={[g.kind for g in gaps]}"

    extraction = extraction_agent.extract(nl)
    answers = {threshold_gaps[0].caveat_text: "500"}
    clarified = resolve_clarification(extraction, result.ir, gaps, answers, ir_builder, ASIM_SCHEMA)

    assert clarified.success
    assert "500" in clarified.kql


# --- §4AH: the dedicated ambiguity-scan agent (the second call §4AG's
# 0/6 self-report negative result pointed at). Live-measured at build
# time: 6/6 fork detection across both documented ambiguous NLs (3
# trials each), 0/6 false positives on three single-reading NLs, and a
# clean resolve_ambiguity round-trip switching the recycle-bin case's
# event type. These anchors hold the scanner to that standard. ---

def test_scanner_finds_the_recycle_bin_event_type_fork_and_resolution_switches_tables(agents):
    """The §4T/§4AG recycle-bin case: "hidden in the recycle bin" forks
    on event type (file planted IN the folder vs. process executing
    FROM it). The IR Builder never self-reports this (0/6, §4AG); the
    dedicated scanner must find it, and choosing the other option must
    rebuild onto the other table."""
    extraction_agent, ir_builder = agents
    nl = "Identifies malware that has been hidden in the recycle bin."
    result = run_system_b(nl, ASIM_SCHEMA, extraction_agent, ir_builder, max_attempts=3)
    assert result.success

    ambiguities = scan_ambiguities(nl, result.ir, AmbiguityScanAgent())
    assert ambiguities, "the scanner must find the documented event-type fork the builder never self-reports"
    amb = ambiguities[0]
    assert amb.picked_option in amb.options
    other = next(o for o in amb.options if o != amb.picked_option)

    extraction = extraction_agent.extract(nl)
    resolved = resolve_ambiguity(extraction, result.ir, [amb], {amb.description: other}, ir_builder, ASIM_SCHEMA)
    assert resolved.success
    old_table = getattr(result.ir.source_table, "value", str(result.ir.source_table))
    new_table = getattr(resolved.ir.source_table, "value", str(resolved.ir.source_table))
    assert new_table != old_table, (
        f"choosing the other event-type reading must actually switch tables "
        f"(stayed on {new_table})"
    )


def test_scanner_stays_empty_on_a_fully_specified_description(agents):
    """Precision guard — the scanner's value depends on empty being the
    common answer. A description with an explicit threshold, window,
    entity, and aggregation has exactly one reasonable reading; any
    reported fork here is a false positive."""
    extraction_agent, ir_builder = agents
    nl = (
        "Alert when a single source IP fails to authenticate against more "
        "than 15 distinct user accounts within a 5-minute window."
    )
    result = run_system_b(nl, ASIM_SCHEMA, extraction_agent, ir_builder, max_attempts=3)
    assert result.success

    ambiguities = scan_ambiguities(nl, result.ir, AmbiguityScanAgent())
    assert ambiguities == [], (
        f"fully-specified NL must scan clean, got: {[a.description for a in ambiguities]}"
    )
