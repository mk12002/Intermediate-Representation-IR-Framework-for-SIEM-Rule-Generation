"""Gap-checker: walks a built KqlPipeline's self-disclosed omissions
(`caveats`/`abstained`) and turns each into a structured, askable
`Gap` — the foundational piece for clarification (PROJECT_STATUS.md
§4AF). Reusable beyond clarification itself: `len(find_gaps(ir))` is
also a free "completeness score" for any result.

Why this sits on `caveats`, not a fresh NL-level gap analysis: the IR
Builder already detects "missing" at the only point where it's
concrete and typed — a caveat is written exactly when a filter/value
couldn't be grounded (PROJECT_STATUS.md §1.8/§4U's "omit, don't
invent" mechanism). Re-deriving that from the NL would duplicate work
the IR Builder already did correctly and risk disagreeing with its
own account of what it omitted.

Why every caveat counts as load-bearing, with no separate frequency x
logic-impact filter applied here: the IR Builder is only ever
instructed to write a caveat for a filter/value that affects the
detection's actual firing behavior — a cosmetic decision (output
column order, which evidence field to make_set()) never gets one.
That filtering already happened upstream, at the point the caveat was
(or wasn't) written; re-filtering here would just be guessing at the
same judgment call a second time with less context.

Scope, stated honestly: this finds MISSING gaps — a concrete value
that isn't groundable at all, the caveats mechanism's entire reason
for existing. It does NOT find AMBIGUOUS gaps (multiple valid
readings of information that IS present, e.g. the §4Q stdev-vs-
baseline fork, or count vs. distinct_count for "DGA query volume") —
that needs the model to recognize and report multiple candidate
readings, which neither caveats nor this checker do yet. Scoped out
deliberately, not silently assumed solved.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from src.ir_engine.ir_schema import Ambiguity, KqlPipeline

# Computed directly from data/processed/pairs_verified.jsonl's real
# ground-truth queries (66 train-split pairs) — NOT an invented
# default. Frequency table (bin(TimeGenerated, X) bucket widths across
# the verified corpus): 1h=9, 5m=5, 1m=3, 15m=2, 1d=2, 10min=1, 5min=1.
# 1 hour is the most common real value, so it's the offered default —
# re-derive by scanning the corpus again if it changes meaningfully.
_DEFAULT_TIME_WINDOW_ISO = "PT1H"
_DEFAULT_TIME_WINDOW_HUMAN = "1 hour"

_FIELD_MENTION_RE = re.compile(r"\bon\s+([A-Z][A-Za-z0-9_]+)\b")
_THRESHOLD_KEYWORDS = ("threshold", "concrete number", "numeric value", "how many")
_TIME_KEYWORDS = ("time window", "lookback", "duration")


@dataclass
class Gap:
    """One load-bearing piece of missing information, derived from a
    single `caveats` entry."""
    caveat_text: str
    question: str
    default: Optional[str] = None
    affected_field: Optional[str] = None
    kind: str = "missing_value"  # "missing_value" | "missing_time_window" | "missing_threshold"


def _affected_field(caveat: str) -> Optional[str]:
    m = _FIELD_MENTION_RE.search(caveat)
    return m.group(1) if m else None


def _classify(caveat: str) -> str:
    lowered = caveat.lower()
    if any(k in lowered for k in _TIME_KEYWORDS):
        return "missing_time_window"
    if any(k in lowered for k in _THRESHOLD_KEYWORDS):
        return "missing_threshold"
    return "missing_value"


def _question_for(caveat: str, kind: str, field_name: Optional[str]) -> str:
    if kind == "missing_time_window":
        return (
            f"What time window should this detection use? "
            f"(default: {_DEFAULT_TIME_WINDOW_HUMAN} — the most common in this "
            f"project's own ground-truth corpus)"
        )
    if kind == "missing_threshold":
        return "What threshold/count should trigger this detection?"
    target = f" for {field_name}" if field_name else ""
    return f"The description didn't specify a concrete value{target} — what should it be? ({caveat})"


def _default_for(kind: str) -> Optional[str]:
    return _DEFAULT_TIME_WINDOW_ISO if kind == "missing_time_window" else None


def find_gaps(ir: KqlPipeline) -> List[Gap]:
    """Every `caveats` entry on this pipeline (including, recursively,
    any join's `right_pipeline`, mirroring `compiler.py`'s own
    `_collect_caveats`) becomes one `Gap`. A fully `abstained` pipeline
    is covered by the same path — the prompt requires a caveats entry
    explaining the abstention, so there is nothing special to detect
    beyond reading that entry."""
    gaps = []
    for caveat in ir.caveats:
        kind = _classify(caveat)
        field_name = _affected_field(caveat)
        gaps.append(Gap(
            caveat_text=caveat,
            question=_question_for(caveat, kind, field_name),
            default=_default_for(kind),
            affected_field=field_name,
            kind=kind,
        ))
    for stage in ir.stages:
        if stage.type == "join":
            gaps.extend(find_gaps(stage.right_pipeline))
    return gaps


def find_ambiguities(ir: KqlPipeline) -> List[Ambiguity]:
    """§4AG — the disambiguation half of clarification: closed-option
    questions for genuine FORKS the IR Builder recognized (see
    Ambiguity's own docstring in ir_schema.py), as opposed to
    find_gaps()'s open questions for information that's simply absent.
    A thin accessor today (the model self-reports these directly on
    `ir.ambiguities`) — kept as its own function, mirroring find_gaps,
    so callers have one consistent interface for both gap kinds and so
    a future structural detection pass (independent of the model's own
    self-report) has an obvious place to plug in without changing every
    call site."""
    ambiguities = list(ir.ambiguities)
    for stage in ir.stages:
        if stage.type == "join":
            ambiguities.extend(find_ambiguities(stage.right_pipeline))
    return ambiguities


def scan_ambiguities(nl_description: str, ir: KqlPipeline, scanner) -> List[Ambiguity]:
    """§4AH — the structural detection pass find_ambiguities' docstring
    reserved a place for: combines the IR Builder's own self-reported
    entries (measured 0/6 at ever appearing, §4AG, but kept — a free
    signal if the model ever does self-report) with a dedicated
    AmbiguityScanAgent's post-build scan. Deduplicates on normalized
    `description` text so a fork found by both paths is asked about
    once. `scanner` is any object with a
    `scan(nl_description, ir) -> List[Ambiguity]` method — passed in
    rather than constructed here so callers control when the extra LLM
    call is spent (and unit tests can pass a stub)."""
    merged = find_ambiguities(ir)
    seen = {a.description.strip().lower() for a in merged}
    for amb in scanner.scan(nl_description, ir):
        key = amb.description.strip().lower()
        if key not in seen:
            seen.add(key)
            merged.append(amb)
    return merged
