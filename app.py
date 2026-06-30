"""Streamlit demo UI for the NL -> KQL Security IR project.

Type a detection description, get back System A's direct-generation KQL
side-by-side with System B's IR-mediated KQL (plus the intermediate IR
and repair-loop status) — the same two systems eval/run_comparison.py
measures, run live against whatever LLM_PROVIDER/model is set in .env.

Run with: streamlit run app.py
"""
import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.baseline.few_shot_examples import FEW_SHOT_EXAMPLE_1, FEW_SHOT_EXAMPLE_2
from src.baseline.run import BaselineRunner
from src.pipeline.system_b import run_system_b

DATA_DIR = Path(__file__).parent / "data"

EXAMPLE_DESCRIPTIONS = {
    "(type your own)": "",
    "Password spray": (
        "Alert when a single source IP fails to authenticate against more "
        "than 15 distinct user accounts within a 5-minute window."
    ),
    "DNS errors (top noisy clients)": (
        "Over the last 24 hours, rank source IPs by count of non-NOERROR "
        "DNS responses and return the top 25."
    ),
    "HTTP 403 abuse": (
        "Over a 1-day window, alert when a single source IP generates more "
        "than 100 HTTP 403 Forbidden responses."
    ),
    "Disguised sdelete usage": (
        "Flag use of a secure-deletion tool's command-line flags "
        "(accepteula, -s, -r, -q together), even if the attacker renamed "
        "the binary to avoid detection."
    ),
    "Baseline-vs-current (DNS)": (
        "Flag a source whose DNS query count in the last 1-day window "
        "exceeds its 14-day baseline average by more than 50."
    ),
}


@st.cache_resource
def load_schema() -> dict:
    return json.loads((DATA_DIR / "schema" / "asim_field_reference.json").read_text(encoding="utf-8"))


@st.cache_resource
def load_agents():
    return ExtractionAgent(), IRBuilderAgent(), BaselineRunner()


def resolve_field_list(likely_event_type: str, asim_schema: dict) -> list[str]:
    """Same fallback as src/pipeline/repair_loop.py: likely_event_type is
    free text and rarely matches a schema key exactly, so fall back to the
    union of every event type's fields rather than an empty list."""
    if likely_event_type in asim_schema:
        return asim_schema[likely_event_type]["fields"]
    return sorted({f for event in asim_schema.values() for f in event["fields"]})


st.set_page_config(page_title="NL -> KQL", layout="wide")
st.title("NL -> KQL: IR-mediated vs. direct generation")
st.caption(
    "Type a detection description below. System A asks the model for KQL "
    "directly; System B extracts structure, builds a schema-validated IR, "
    "and deterministically compiles it — with up to 3 repair attempts if "
    "the IR fails validation."
)

provider = os.getenv("LLM_PROVIDER", "(not set)")
model = os.getenv("IR_BUILDER_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "(not set)"))
st.sidebar.markdown(f"**Provider:** `{provider}`  \n**Model:** `{model}`")
st.sidebar.caption("Set in .env — see .env.example.")

choice = st.selectbox("Try an example, or pick \"(type your own)\" below:", list(EXAMPLE_DESCRIPTIONS.keys()))
default_text = EXAMPLE_DESCRIPTIONS[choice]
nl_description = st.text_area("Detection description", value=default_text, height=120)

if st.button("Generate", type="primary", disabled=not nl_description.strip()):
    try:
        asim_schema = load_schema()
        extraction_agent, ir_builder, baseline = load_agents()
    except Exception as e:
        st.error(f"Failed to initialize agents/schema — check your .env config. {e}")
        st.stop()

    col_a, col_b = st.columns(2)

    with st.spinner("Running System B (extraction + IR build + repair)..."):
        try:
            result_b = run_system_b(nl_description, asim_schema, extraction_agent, ir_builder)
            extraction = extraction_agent.extract(nl_description)
        except Exception as e:
            result_b = None
            extraction = None
            st.session_state["b_error"] = str(e)

    with st.spinner("Running System A (direct generation)..."):
        try:
            field_list = resolve_field_list(extraction.likely_event_type, asim_schema) if extraction else \
                sorted({f for event in asim_schema.values() for f in event["fields"]})
            kql_a = baseline.run(
                nl_description=nl_description,
                asim_field_reference=json.dumps(field_list),
                few_shot_example_1=f"{FEW_SHOT_EXAMPLE_1['nl_description']}\n{FEW_SHOT_EXAMPLE_1['kql']}",
                few_shot_example_2=f"{FEW_SHOT_EXAMPLE_2['nl_description']}\n{FEW_SHOT_EXAMPLE_2['kql']}",
            )
            a_error = None
        except Exception as e:
            kql_a = None
            a_error = str(e)

    with col_a:
        st.subheader("System A — direct generation")
        if a_error:
            st.error(a_error)
        else:
            st.code(kql_a, language="sql")
        st.caption("No validation, no repair — whatever the model outputs is final.")

    with col_b:
        st.subheader("System B — IR-mediated")
        if result_b is None:
            st.error(st.session_state.get("b_error", "Unknown error"))
        elif result_b.success:
            st.success(f"Valid after {result_b.attempts_used} attempt(s)")
            st.code(result_b.kql, language="sql")
        else:
            st.warning(f"Did not converge — {result_b.reason}")
            if result_b.kql:
                st.code(result_b.kql, language="sql")

        if result_b is not None and result_b.ir is not None:
            with st.expander("Intermediate IR (what System B actually built)"):
                st.json(json.loads(result_b.ir.model_dump_json(exclude_none=True)))
        if extraction is not None:
            with st.expander("Extraction Agent output"):
                st.json(json.loads(extraction.model_dump_json(exclude_none=True)))

st.divider()
st.caption(
    "This mirrors eval/run_comparison.py's live comparison — see "
    "docs/NL-KQL/RESULTS_DRAFT.md and docs/NL-KQL/PROJECT_STATUS.md for "
    "the full evaluation, including known limitations and architectural gaps."
)
