"""Execution-validated Logic Correctness — runs the IR Builder's ACTUAL
live output through src/execution/ir_interpreter.py against synthetic
should-fire/should-not-fire events, instead of relying on manual/LLM
judgment of whether the pipeline "looks right" (PROJECT_STATUS.md §4Y).

This is a live test (real LLM calls, real generated IR) — named with
the live_e2e substring (the project's actual convention for excluding
these from the fast default run; see test_live_e2e.py) so the standard
`pytest tests/unit tests/integration -q -k "not live_e2e"` skips it.
Run explicitly via `pytest tests/integration/test_live_e2e_execution_validation.py`.

Every test in this file is also marked `@pytest.mark.regression_gate`
(registered in pytest.ini) — each targets one specific, previously-
fixed bug class (the label-vs-data recall bug, the sdelete rename-
evasion bug, the DGA dcount-vs-count ambiguity, the §4U OR-list-as-
AND-chain regression, the §4V CVE-ID-as-literal bug), not a fresh
capability. §4T found one of these (c6608467) regress silently on the
exact prompt that had already fixed it — prompt churn at scale makes
that MORE likely over time, not less, without something automated
watching for it. Run `pytest -m regression_gate` after ANY edit to
src/agents/extraction_agent.py, src/agents/ir_builder_agent.py, or
src/execution/ir_interpreter.py, BEFORE considering that edit complete
— this is a standing project rule, not a one-time check.

Each case's synthetic events are written generously across the
plausible ASIM field-name variants for that concept (e.g. CommandLine
AND ProcessCommandLine), since the goal here is checking the IR's
SELECTED LOGIC fires on the right scenario, not penalizing a reasonable
field-name choice this same project's worked examples treat as
equally-valid — that's a different, already-covered concern, not what
this file tests.
"""
import json
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.execution.ir_interpreter import pipeline_fires
from src.pipeline.system_b import run_system_b
from src.synthesis.fixture_generator import _placeholder_fields

pytestmark = pytest.mark.skipif(
    not (os.getenv("LLM_PROVIDER") and os.getenv("AZURE_FOUNDRY_API_KEY")) and not (
        os.getenv("LLM_PROVIDER") == "ollama"
    ),
    reason="no LLM backend configured (set LLM_PROVIDER + provider credentials in .env to run)",
)

ASIM_SCHEMA = json.loads(open("data/schema/asim_field_reference.json", encoding="utf-8").read())


@pytest.fixture(scope="module")
def agents():
    return ExtractionAgent(), IRBuilderAgent()


def _build(nl: str, agents):
    extraction_agent, ir_builder = agents
    result = run_system_b(nl, ASIM_SCHEMA, extraction_agent, ir_builder, max_attempts=3)
    assert result.success, f"pipeline failed to produce a valid IR: {result.reason}"
    return result.ir


@pytest.mark.regression_gate
def test_lolbin_in_recycle_bin_fires_on_match_not_on_benign(agents):
    nl = "Identifies malware that has been hidden in the recycle bin."
    ir = _build(nl, agents)

    # This vague NL genuinely supports two independent axes of valid
    # variance, confirmed live: event type (ProcessEvent — a process
    # executing FROM the folder — vs FileEvent — a file hidden IN it,
    # both real readings of "hidden in the recycle bin") and path
    # convention (ground truth's legacy "recycler", vs the modern
    # "$Recycle.Bin" the model also produces once the literal-English-
    # phrase bug below is fixed). The synthetic event covers all of
    # them at once rather than over-narrowing to one specific choice.
    should_fire = [{
        "CommandLine": "C:\\RECYCLER\\$Recycle.Bin\\S-1-5-21\\svchost.exe", "Process": "svchost.exe",
        "ProcessCommandLine": "C:\\RECYCLER\\$Recycle.Bin\\S-1-5-21\\svchost.exe", "TargetFilename": "svchost.exe",
        "FilePath": "C:\\RECYCLER\\$Recycle.Bin\\S-1-5-21\\svchost.exe", "ActingProcessName": "svchost.exe",
        "FileName": "svchost.exe",
    }]
    should_not_fire = [{
        "CommandLine": "C:\\Program Files\\Notepad++\\notepad++.exe readme.txt", "Process": "notepad++.exe",
        "ProcessCommandLine": "C:\\Program Files\\Notepad++\\notepad++.exe readme.txt",
        "TargetFilename": "notepad++.exe", "FilePath": "C:\\Program Files\\Notepad++\\notepad++.exe",
        "ActingProcessName": "notepad++.exe", "FileName": "notepad++.exe",
    }]
    assert pipeline_fires(ir, should_fire) is True
    assert pipeline_fires(ir, should_not_fire) is False


@pytest.mark.regression_gate
def test_sdelete_renamed_binary_evasion_fires_on_flags_not_on_real_name(agents):
    """Known, precisely-characterized model-reliability residual
    (PROJECT_STATUS.md §4AC, §4AD policy note): the Extraction Agent
    correctly extracts the real flags (["accepteula", "-s", "-r", "-q"])
    into candidate_fields on every trial — confirmed live, 5/5 — but
    the IR Builder ignores that already-correct list roughly 1/5 times
    and invents a non-existent flag ("-p") instead, the EXACT wrong
    answer the prompt's own worked example already names by example.
    This is not a missing-guidance gap; it is raw model non-determinism
    on this specific hard case, confirmed rather than assumed after a
    real second attempt at tracing it.

    A permanently-red anchor trains the gate's signal into noise (the
    exact failure mode this gate exists to prevent, §4T) — so this
    runs the build 5 times and requires >=3/5 on the fire-check
    specifically. Re-measuring this exact threshold live (this round)
    found more variance than the single-session "~1/5" estimate
    suggested — one run of 5 scored 3/5, a second scored 5/5 — so the
    floor is set at 3/5 (60%), not the more optimistic 4/5 (80%) first
    assumed, until a larger-N measurement narrows it further. The two
    no-fire
    checks are NOT flaky in this project's own measurement (every
    trial across every round that found this residual still correctly
    excluded the literal-name and unrelated-process cases) and stay at
    the normal 5/5 bar — if THOSE start failing, that is a new,
    different bug, not this residual, and must not be masked by the
    relaxed threshold."""
    nl = (
        "This detection looks for command line parameters associated with the use of Sysinternals "
        "sdelete to delete multiple files on a host's C drive. A threat actor may re-name the tool "
        "to avoid detection."
    )
    renamed_evasion = [{
        "CommandLine": "svc_update.exe -accepteula -s -r -q C:\\Users\\victim\\Documents",
        "ProcessCommandLine": "svc_update.exe -accepteula -s -r -q C:\\Users\\victim\\Documents",
        "Process": "svc_update.exe", "ActingProcessName": "svc_update.exe",
    }]
    real_name_used_openly = [{
        "CommandLine": "sdelete.exe -accepteula -s -r -q C:\\Users\\victim\\Documents",
        "ProcessCommandLine": "sdelete.exe -accepteula -s -r -q C:\\Users\\victim\\Documents",
        "Process": "sdelete.exe", "ActingProcessName": "sdelete.exe",
    }]
    unrelated_process = [{
        "CommandLine": "explorer.exe", "ProcessCommandLine": "explorer.exe",
        "Process": "explorer.exe", "ActingProcessName": "explorer.exe",
    }]

    n = 5
    fire_passes = nofire_real_name_passes = nofire_unrelated_passes = 0
    for _ in range(n):
        ir = _build(nl, agents)
        fire_passes += int(pipeline_fires(ir, renamed_evasion))
        nofire_real_name_passes += int(not pipeline_fires(ir, real_name_used_openly))
        nofire_unrelated_passes += int(not pipeline_fires(ir, unrelated_process))

    assert fire_passes >= 3, (
        f"renamed-evasion fire check passed only {fire_passes}/{n} — at or below the "
        f"measured model-reliability floor (§4AC/§4AD); if this drops further, "
        f"re-investigate rather than assume it's still the same characterized residual"
    )
    assert nofire_real_name_passes == n, (
        f"real-name-present exclusion failed {n - nofire_real_name_passes}/{n} times — "
        f"this is NOT the known residual (that's fire-check only) — investigate as a new bug"
    )
    assert nofire_unrelated_passes == n


@pytest.mark.regression_gate
def test_dga_anomaly_detection_fires_on_spike_not_on_steady_baseline(agents):
    nl = (
        "This rule makes use of the series decompose anomaly method to detect clients with a high "
        "NXDomain response count, which could be indicative of a DGA. An alert is generated when "
        "new IP address DNS activity is identified as an outlier when compared to the baseline."
    )
    ir = _build(nl, agents)

    # The model sometimes analyzes raw NXDOMAIN count, sometimes
    # dcount(DnsQuery) (a defensible DGA-specific reading — real DGA
    # malware queries many DIFFERENT algorithmically-generated domains,
    # not one repeated domain). Confirmed live: a fixed repeated DnsQuery
    # satisfies the first but not the second. Varying the domain per
    # spike event satisfies both AND is the more realistic DGA pattern
    # either way.
    quiet_days = ["2026-06-17", "2026-06-18", "2026-06-19", "2026-06-20", "2026-06-21", "2026-06-22"]
    spike_day = "2026-06-23"
    # _placeholder_fields walks the model's OWN regenerated IR for every
    # group_by/aggregation field it actually references and fills in a
    # constant placeholder — found live: this NL's "new IP address ...
    # outlier" framing sometimes leads the model to group/aggregate on a
    # geo/IP-enrichment field (e.g. DnsResponseIpCity) the hardcoded
    # base_fields below never anticipated, crashing the interpreter with
    # a KeyError instead of a clean pass/fail — the same field-identity-
    # coupling lesson src/synthesis/fixture_generator.py's docstring
    # already documents for the synthesis eval, recurring here in this
    # hand-written fixture. A CONSTANT placeholder (not varied per row)
    # keeps any such extra field non-discriminative, so the actual
    # spike-vs-flat distinction this test exists to check still comes
    # entirely from DnsQuery/TimeGenerated as intended.
    base_fields = {
        **_placeholder_fields(ir),
        "DnsResponseCodeName": "NXDOMAIN", "DnsQueryTypeName": "NXDOMAIN", "SrcIpAddr": "10.0.0.7",
    }

    spike_rows = [
        {**base_fields, "TimeGenerated": f"{d}T12:00:00Z", "DnsQuery": "stable-domain.invalid"}
        for d in quiet_days for _ in range(2)
    ] + [
        {**base_fields, "TimeGenerated": f"{spike_day}T12:00:00Z", "DnsQuery": f"dga{i:03d}.invalid"}
        for i in range(40)
    ]
    flat_rows = [
        {**base_fields, "TimeGenerated": f"{d}T12:00:00Z", "DnsQuery": "stable-domain.invalid"}
        for d in (quiet_days + [spike_day]) for _ in range(2)
    ]
    assert pipeline_fires(ir, spike_rows) is True
    assert pipeline_fires(ir, flat_rows) is False


# --- Regression gate (§4Z follow-up) ---------------------------------------
#
# A permanent should-pass anchor per previously-fixed bug class — the
# critique's point that §4T's c6608467 (an OR-list silently regressing
# into an AND-chain on the exact prompt that had already fixed it) shows
# scale and prompt churn make silent regression MORE likely over time,
# not less, without something automated watching for it. This is that
# something: each test below targets one specific, historically-real bug
# this project found and fixed, not a fresh capability.

@pytest.mark.regression_gate
def test_url_extension_or_list_fires_on_any_one_extension_not_all_of_them(agents):
    """Regression anchor for §4U's c6608467 finding: a comma-separated
    list of exemplars introduced by "such as" (no literal word "or")
    was being compiled as an AND-chain requiring every extension in the
    same URL at once — a query that can never fire on a real URL."""
    nl = (
        "This rule detects web requests made to URLs containing file types such as .ps1, .bat, "
        ".vbs, .scr etc. which have the potential to be harmful if downloaded."
    )
    ir = _build(nl, agents)
    # _placeholder_fields: the model sometimes wraps the filter in a
    # SummarizeStage (e.g. grouping by HttpRequestMethod, or computing
    # min/max(TimeGenerated) as a "first/last seen" evidence column, for
    # a breakdown-style reading of "detects ... requests"), which this
    # fixture's single-field row never anticipated — the same field-
    # identity-coupling lesson as the DGA test above, not a logic bug in
    # the IR. TimeGenerated is added explicitly alongside _placeholder_
    # fields (which deliberately excludes it — see its own docstring —
    # on the assumption the caller provides it, which this fixture
    # didn't before this fix).
    extra = {**_placeholder_fields(ir), "TimeGenerated": "2026-06-24T01:00:00Z"}
    assert pipeline_fires(ir, [{**extra, "Url": "http://evil.example.com/payload.ps1"}]) is True
    assert pipeline_fires(ir, [{**extra, "Url": "http://evil.example.com/installer.bat"}]) is True
    assert pipeline_fires(ir, [{**extra, "Url": "http://contoso.com/report.pdf"}]) is False


@pytest.mark.regression_gate
def test_cve_id_is_not_used_as_literal_command_line_content(agents):
    """Regression anchor for §4V's CVE-ID-as-literal-data finding: the
    model was echoing a CVE identifier itself as a CommandLine filter
    value — a string that can never appear in a real command line,
    silently never firing on the actual exploit pattern."""
    nl = (
        "This hunting query looks for potential command injection attempts via the vulnerable "
        "third-party driver against Azure IR with Managed VNet or SHIR processes. "
        "Reference: CVE-2022-29972."
    )
    ir = _build(nl, agents)
    assert pipeline_fires(ir, [{"CommandLine": "powershell -enc CVE-2022-29972 exploit.ps1"}]) is False, (
        "must NOT fire on a command line containing only the literal CVE ID — "
        "that string never appears in a real exploit command"
    )


@pytest.mark.regression_gate
def test_process_time_bracketed_by_joined_auth_window_uses_field_ref_not_literal(agents):
    """Regression anchor for §4AA's field-to-field comparison gap: found
    via combination testing (arg_max inside a join) that the model
    correctly recognizes a detection needs to bracket one field's value
    between two OTHER fields' values (a joined event's time window), but
    Filter.value can only hold a literal — so it fell back to comparing
    against the quoted STRING NAME of the other column
    (`where ProcessTime >= "FirstAuthTime"`), syntactically valid but
    silently never correct. Fixed by adding Filter.field_ref (compiler
    renders it unquoted; interpreter reads it from the row instead of
    treating it as a literal) plus a worked example teaching the
    pattern. This anchor would have caught the gap before field_ref
    existed (every trial failed it) and must keep passing now.

    The interpreter's join is table-agnostic — both sides see the SAME
    row set (ir_interpreter.py's run_pipeline reuses the original rows
    for right_pipeline, not the left side's filtered subset). Found via
    two failed iterations of this fixture before this one: (1) varying
    only the process timestamp is unreliable, since the minority answer
    shape that reuses bare "TimeGenerated" for both the join-side
    aggregation AND the process event's own time leaks that same
    out-of-range timestamp into the right side's own min/max, making it
    trivially become its own boundary; (2) giving the excluded row a
    NON-matching host but STILL a "TimeGenerated" value doesn't avoid
    the leak either — the right_pipeline's OWN groupby still includes
    that row (it groups ALL input rows by host, regardless of which
    "table" they're conceptually from), creating a SPURIOUS
    self-correlated group for the excluded host where
    FirstAuthTime == LastAuthTime == the row's own timestamp, which the
    bracket check then trivially satisfies against itself. The fix:
    the excluded row omits "TimeGenerated"/"EventStartTime" entirely,
    so its right-side group (if one even forms) has NaN/NaT bounds,
    and a comparison against NaT is always False regardless of which
    field the model used for the process side — confirmed directly
    against the interpreter before re-running live. The inclusion case
    still directly exercises the field_ref bracket itself (and would
    fail exactly as before field_ref existed, since the original bug
    compared against the literal string "FirstAuthTime", which can
    never be >= a real timestamp either)."""
    nl = (
        "This rule flags a PowerShell process launch on a host that falls within the time window "
        "of authentication activity on that same host, joining process creation events against "
        "authentication events grouped by host to compute the earliest and latest authentication "
        "times, then checking whether the process launch time falls between them."
    )
    ir = _build(nl, agents)
    # Dvc/DvcHostname/HostName: confirmed live the model varies which
    # ASIM host-identifier it groups/joins by — generous across all
    # three rather than penalizing a reasonable field-name choice (same
    # principle as every other case in this file).
    def host(name: str) -> dict:
        return {"Dvc": name, "DvcHostname": name, "HostName": name}

    auth_rows = [
        {**host("host-A"), "TimeGenerated": "2026-06-24T01:00:00Z", "EventStartTime": "2026-06-24T01:00:00Z"},
        {**host("host-A"), "TimeGenerated": "2026-06-24T02:00:00Z", "EventStartTime": "2026-06-24T02:00:00Z"},
    ]
    within_window = auth_rows + [{
        **host("host-A"), "ActingProcessName": "powershell.exe", "Process": "powershell.exe",
        "TimeGenerated": "2026-06-24T01:30:00Z", "ActingProcessCreationTime": "2026-06-24T01:30:00Z",
    }]
    no_correlated_auth_activity = auth_rows + [{
        **host("host-B"), "ActingProcessName": "powershell.exe", "Process": "powershell.exe",
        "ActingProcessCreationTime": "2026-06-24T01:30:00Z",
    }]
    assert pipeline_fires(ir, within_window) is True
    assert pipeline_fires(ir, no_correlated_auth_activity) is False


@pytest.mark.regression_gate
def test_total_abstention_never_fires_on_anything(agents):
    """Regression anchor for §4AE's severe finding: a KqlPipeline that
    could not ground ANY concrete detection logic was being expressed
    as an empty `stages` list — which does NOT fail safe. A pipeline
    with no WhereStage filters fires on EVERY row of source_table when
    actually deployed; in a real SOC that is worse than not shipping a
    rule at all (it buries the analyst in false positives and trains
    them to ignore the alert). Fixed with KqlPipeline.abstained: True
    means no concrete logic was groundable; the validator hard-rejects
    an empty `stages` list that isn't explicitly marked abstained;
    generate_kql() refuses to emit a runnable query for it; and
    pipeline_fires() always returns False for it regardless of input.

    This NL is deliberately maximally under-specified — a bare "known
    IoC" reference with zero concrete values anywhere in the text — to
    reliably trigger total (not partial) abstention. If the model finds
    SOME partial signal and builds a real, narrower filter instead of
    abstaining, that is also a correct, safe outcome (the prompt's own
    guidance prefers partial-real over abstention) — this anchor checks
    the should-not-fire property holds EITHER way, not that abstention
    specifically occurs."""
    nl = (
        "This rule identifies web sessions for which the source IP address is a known IoC. "
        "This rule uses ASIM and supports any web session source that complies with ASIM."
    )
    ir = _build(nl, agents)
    should_not_fire = [
        {"SrcIpAddr": "203.0.113.99", "Url": "http://totally-unrelated.example.com", "TimeGenerated": "2026-06-24T01:00:00Z"},
        {"SrcIpAddr": "8.8.8.8", "Url": "https://contoso.com/login", "TimeGenerated": "2026-06-24T02:00:00Z"},
    ]
    assert pipeline_fires(ir, should_not_fire) is False, (
        "a pipeline with no groundable detection logic must never fire on arbitrary "
        "input — if it does, it is silently alerting on everything when deployed"
    )
    if ir.abstained:
        assert ir.stages == [], "abstained=True must mean no executable logic, not a stale/inconsistent partial pipeline"
