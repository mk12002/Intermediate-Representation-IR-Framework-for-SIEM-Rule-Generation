"""A dedicated ambiguity-scanning agent (PROJECT_STATUS.md §4AG/§4AH).

Why this is its own LLM call and not one more instruction in the IR
Builder's prompt: §4AG measured the self-report approach at 0/6 — the
IR Builder never populated `ambiguities`, even on the exact NLs its own
worked examples describe, and even after a second round of prompt
strengthening added a mandatory pre-finalization self-check. The
documented hypothesis: every other instruction in that prompt reinforces
decisive, single-interpretation construction, and asking the SAME
generative call to also monitor itself for forks it's busy resolving is
structurally self-defeating. This agent tests that hypothesis directly —
it runs AFTER the pipeline is built, sees the committed reading as a
finished fact it has no stake in, and its ONLY output is a report of
genuine forks (usually empty).

Deliberately additive and off the critical path: the scanner can only
ADD entries for the clarification UI to ask about — it never edits the
pipeline, never blocks a result, and a scan failure of any kind
degrades to "no ambiguities found" (the exact behavior the system had
before this agent existed).
"""
import os
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.base_agent import BaseAgent
from src.generator.compiler import generate_kql
from src.ir_engine.ir_schema import Ambiguity, KqlPipeline


class AmbiguityScanReport(BaseModel):
    """The scanner's whole output: zero or more genuine structural
    forks. A separate wrapper model (not bare List[Ambiguity]) so the
    empty case parses as an explicit `{"ambiguities": []}` rather than
    relying on the parser accepting a bare empty array."""
    ambiguities: List[Ambiguity] = Field(default_factory=list)


_SCAN_SYSTEM_PROMPT = """You are an independent reviewer of an ALREADY-BUILT security detection.
You are NOT building or fixing anything. Your only job is to answer one
question: does the description support a SECOND, structurally different
reading that a different, equally reasonable analyst would defensibly
have built instead — with nothing in the text to break the tie?

"Structurally different" means one of exactly these three things:
- a different EVENT TYPE / source table (the description's activity could
  genuinely be observed as two different kinds of event),
- a different AGGREGATION FUNCTION measuring a different quantity (e.g. a
  raw event count vs. a count of DISTINCT values — different numbers,
  different detection),
- a different FILTER TARGET — the description's key property could
  genuinely belong to a different entity/field-concept than the one used.

What is NOT an ambiguity — never report any of these:
- MISSING information (no threshold given, no IoC values, no time window,
  an external list with no values). That is a gap, not a fork — the
  pipeline's `caveats` mechanism already handles it, and reporting it
  here would duplicate a question the user is already being asked.
- Routine choices with an established convention: Src*/Dst* prefix
  selection, which ASIM table a keyword maps to, operator
  case-sensitivity defaults, field naming.
- A reading the description itself rules out ("process executing from the
  folder" is not a defensible alternative when the text explicitly says a
  file was CREATED there).
- Stylistic differences that compile to the same firing behavior (has vs
  contains on the same value, one where-stage vs. two, filter order).
- A reading that is technically constructible but clearly worse — the
  bar is EQUALLY defensible, not merely possible.

Calibration, stated plainly: most real detection descriptions have ONE
reasonable reading. On a typical batch, the correct report for the large
majority is an EMPTY list — an empty report is a successful scan, not a
failed one. Only report a fork you could argue for either side of in
front of another analyst.

Two real forks (report shapes like these):
- "Identifies malware that has been hidden in the recycle bin" — forks
  on EVENT TYPE: a process executing FROM that folder (ProcessEvent) vs.
  a file planted IN it (FileEvent). Both real, nothing in the text
  breaks the tie.
- "detect clients with a high NXDomain response count... indicative of a
  DGA" — forks on AGGREGATION: raw count() of NXDOMAIN responses vs.
  dcount(DnsQuery) of distinct domains queried (DGA malware generates
  many DIFFERENT domains, so distinct-count is a defensible,
  more-specific reading; raw volume is the literal reading). This fork
  exists WHEREVER the aggregation lives — a summarize clause or a
  make-series — and it exists EVEN IF the committed choice is arguably
  the smarter one: when the description's own wording names one
  quantity (e.g. "response count", a raw volume) but the built query
  measures a different one (e.g. dcount of distinct values), the query
  has silently committed to a non-literal reading, and surfacing that
  choice is precisely what this scan is for. "The committed reading is
  better" resolves the fork in the analyst's head, not in the text —
  report it.

Two non-forks (report NOTHING for shapes like these):
- "Flag use of sdelete's accepteula, -s, -r, -q flags together, even if
  the binary was renamed" — the behavior, flags, and evasion framing are
  fully specified; there is exactly one reasonable structure.
- "Identifies DNS requests for which the response IP is a known IoC" —
  the IoC values are MISSING, which is a caveat/gap, not a second
  reading; the structure itself is unambiguous.

For each genuine fork you do find, output one entry with:
- "description": one sentence naming what forks and why the text
  doesn't resolve it,
- "options": 2+ short human-readable readings. One of them MUST describe
  the reading the built query below actually committed to,
- "picked_option": copied EXACTLY (character-for-character) from the
  option in "options" that describes the built query's committed
  reading.

The detection description:
{nl_description}

The reading the pipeline actually committed to (source table
{source_table}; the compiled query, or its abstention notice):
{committed_kql}

{format_instructions}

Return ONLY one JSON object that is a valid INSTANCE of this schema —
usually {{"ambiguities": []}}."""


class AmbiguityScanAgent(BaseAgent):
    """Runs after System B completes; see module docstring."""

    def __init__(self):
        model_name = os.getenv("AMBIGUITY_SCAN_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "qwen3.5:4b"))
        super().__init__(model_name=model_name)
        self.scan_prompt = ChatPromptTemplate.from_messages(
            [("system", _SCAN_SYSTEM_PROMPT),
             ("user", "Scan the description against the committed reading and report genuine forks only.")]
        )

    def scan(self, nl_description: str, ir: KqlPipeline) -> List[Ambiguity]:
        """Never raises past this method: any parse/LLM failure returns
        [] — the scanner is additive-only, and a failed scan must
        degrade to exactly the pre-scanner behavior (no ambiguities
        surfaced), never block or fail a result that is already built
        and validated."""
        try:
            committed_kql = generate_kql(ir)
        except Exception:
            committed_kql = "(could not be rendered)"
        source_name = getattr(ir.source_table, "value", str(ir.source_table))
        try:
            report = self._invoke(
                prompt=self.scan_prompt,
                pydantic_schema=AmbiguityScanReport,
                input_data={
                    "nl_description": nl_description,
                    "source_table": source_name,
                    "committed_kql": committed_kql,
                },
            )
        except Exception:
            return []
        return report.ambiguities
