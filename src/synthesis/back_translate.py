"""Back-translates a generated (KqlPipeline, GenerationMeta) pair into a
natural-language detection description — the one uncertain step in the
reverse-generation pipeline (PROJECT_STATUS.md §4Z), everything upstream
of it (the IR, the compiled KQL, the should-fire/should-not-fire
fixtures) is correct by construction. Spot-check the NL, not the KQL.

Two styles (§4Z follow-up, the synthetic-vs-real NL gap measurement):
side-by-side comparison against real ground truth found that every
"rich" back-translation follows a rigid "this rule detects X, which may
indicate Y" template, while real descriptions are far more varied —
some are a few words with no rationale clause at all (e.g. `bd89c7a0`:
"breakdown of scripts running in the environment"). "terse" deliberately
degrades toward that real-world sparseness — no rationale clause, no
"this rule"/"this detection" framing, as short as a real analyst would
plausibly write — so the resulting accuracy can be compared against
"rich" on the SAME generated IRs: if accuracy drops noticeably under
"terse", the "rich"-style numbers reported elsewhere are inflated
relative to real-world input variety, and the size of that drop is
itself the gap's measured size.
"""
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from src.agents.base_agent import BaseAgent
from src.synthesis.ir_generator import GenerationMeta

_RICH_SYSTEM_PROMPT = """You are a security analyst writing a one- or two-sentence natural-language
description of a detection rule, given its compiled KQL query. Write the
way a real Sentinel/ASIM detection rule's description field reads: plain
prose, no markdown, no code, no field names verbatim unless a security
analyst would naturally say them (e.g. "command line", "destination
port" are fine; "DstPortNumber" is not). Describe WHAT the rule detects
and WHY it matters, the way the query's logic actually behaves — do not
invent a more sophisticated-sounding detection than the query actually
implements, and do not omit a real condition the query checks.

KQL query:
{compiled_kql}

{format_instructions}

Return ONLY one JSON object with a single field "description" containing
the natural-language text."""

_TERSE_SYSTEM_PROMPT = """You are a security analyst jotting down the bare minimum description for a
detection rule, given its compiled KQL query. Real analysts often write
very sparse descriptions — sometimes just a noun phrase, with NO
explanation of why it matters and no "this rule detects" framing. Match
that sparseness: as few words as possible while still naming WHAT is
being checked, no rationale, no markdown, no code, no field names
verbatim unless a security analyst would naturally say them. Do not pad
it into a full, well-formed sentence if a fragment would do — a real
example of the target style is "breakdown of scripts running in the
environment" (six words, no rationale clause).

KQL query:
{compiled_kql}

{format_instructions}

Return ONLY one JSON object with a single field "description" containing
the natural-language text."""


class BackTranslation(BaseModel):
    description: str


class BackTranslator(BaseAgent):
    def __init__(self):
        import os
        model_name = os.getenv("BACK_TRANSLATE_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "qwen3.5:4b"))
        super().__init__(model_name=model_name)
        self.rich_prompt = ChatPromptTemplate.from_messages([("system", _RICH_SYSTEM_PROMPT)])
        self.terse_prompt = ChatPromptTemplate.from_messages([("system", _TERSE_SYSTEM_PROMPT)])

    def translate(self, compiled_kql: str, meta: GenerationMeta, style: str = "rich") -> str:
        prompt = self.terse_prompt if style == "terse" else self.rich_prompt
        result = self._invoke(
            prompt=prompt,
            pydantic_schema=BackTranslation,
            input_data={"compiled_kql": compiled_kql},
        )
        return result.description
