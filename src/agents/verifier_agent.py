import os
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from .base_agent import BaseAgent


class VerificationResult(BaseModel):
    matches_intent: bool
    issue: str = ""
    # Which of the verifier's own 3 checks the issue falls under, or
    # "other" for anything outside that structure. Lets repair_loop.py
    # phrase the repair instruction the same structured way a validator
    # error is phrased (named field/category up front) instead of
    # passing the free-text issue through verbatim — §4S found the IR
    # Builder could act reliably on a precise structured error within 3
    # attempts but not on free text, and this is the bridge between the
    # two. category is meaningless when matches_intent is true.
    category: Literal["event_type", "comparison_direction", "aggregation_grouping", "other"] = "other"


_VERIFIER_SYSTEM_PROMPT = """You are reviewing a generated KQL detection query against the natural
language description it was supposed to implement. Do NOT check syntax
or field names — that has already been validated separately and is
guaranteed correct here. Your ONLY job is semantic: does this query
actually implement what the description asks for?

Check exactly these three things, in this order, and stop at the first
real problem:
1. Event type / table: does the query operate on the right kind of
   event for what's described (e.g. a DNS query check should not run on
   process events)?
2. Comparison direction: if there's a threshold or comparison, is it
   pointed the right way (e.g. "more than 100" must not compile to a
   condition that's true below 100, or compare the wrong two values)?
3. Aggregation / grouping: if the description implies grouping by an
   entity (a source, an account, a named pair of fields), does the query
   group by that SAME entity? Is a percentile/count/sum/etc. computed
   over the right thing, not a proxy that changes the meaning?

Be LENIENT about: a threshold number the description itself never gave
(you cannot fault a query for omitting a number that was never stated);
a real ASIM field name choice that reasonably represents the same
concept as a different one would; an aggregation window or bin size
that's a reasonable reading of vague time language; correlating two
related events by binning both sides to the same time window before
joining (e.g. "happened within an hour of each other" implemented as a
shared hourly bin) — this is a known, accepted approximation of "within
N minutes," not a logic bug, even though it can theoretically miss a
pair that straddles a bin boundary; a detection for a tool used under a
DISGUISED OR RENAMED name that excludes the tool's own obvious literal
name (e.g. "flag X's behavior even if renamed, AND exclude cases
literally named X.exe") — that exclusion is deliberate, not a bug: the
query is specifically about the evasive/renamed case, and the literally-
named case is intentionally out of scope for it, not mistakenly dropped;
a query that has NO filter at all on a value the description references
but never gives concretely (an external CSV/watchlist/IoC feed with zero
example values stated) — an absent filter is the correct, honest
response to ungroundable data and must not be flagged as failing to
"implement" that part of the description. This is the specific
distinction that matters: a MISSING filter on ungroundable data is
correct; a PRESENT filter whose literal values are obviously fabricated
placeholders (see the STRICT item below) is the actual bug — judge by
whether a filter clause with suspicious values exists, not by whether
that part of the description was technically left unaddressed.

Be STRICT about: the query checking the OPPOSITE of what was described;
the query operating on data that's conceptually different from what was
described (the wrong event category entirely); a grouping that drops an
entity the description explicitly named (e.g. "per source/port pair"
needs both fields, not just one); an OR where the description needs AND
or vice versa, when that changes what the query actually flags; a filter
whose VALUE is a word lifted from a MITRE ATT&CK technique name or the
attacker's stated goal rather than a concrete technical detail the
description actually gives (e.g. a filter for the literal word "signed"
because the description mentions "Signed Binary Proxy Execution" — that
technique name describes a category of attack, not literal log content,
and a filter built from it is not a legitimate defensive narrowing, it's
a misread); a filter VALUE that is an obviously fabricated placeholder
standing in for data the description never gave (e.g. `in
("known_ioc_ip_1", "known_ioc_ip_2")`, `in ("known_malicious_user_agent_1",
...)`, `"<known IoC IPs>"`) — these read as plausible IoC/list values at
a glance, but are clearly invented labels, not real IP addresses or
user-agent strings, and compile into a filter that can never match
anything real while looking like a working detection.

One specific KQL fact, since getting this backwards produces a confident
but wrong critique: `datetime_diff(unit, datetime1, datetime2)` means
`datetime1 - datetime2` — the FIRST datetime argument is the later one
when the result should be positive. Do not flag a query as having its
time-difference arguments backwards unless you have actually worked out
which of the two named datetimes is later in the scenario described.

Description: {nl_description}

Generated KQL:
{compiled_kql}

{format_instructions}

Return ONLY one JSON object. If everything checks out, set
matches_intent=true and leave issue as an empty string. If there is a
real problem, set matches_intent=false, issue to ONE specific,
actionable sentence describing exactly what's wrong — phrased the same
way a validator error would be, since this is fed back to the model that
built the query for one targeted repair attempt, not shown to a human —
and category to whichever of the three numbered checks above the
problem falls under ("event_type", "comparison_direction", or
"aggregation_grouping"), or "other" if it genuinely does not fit any of
them."""


class VerifierAgent(BaseAgent):
    """Checks semantic intent-match between the NL description and the
    compiled KQL — the one dimension nothing else in this pipeline ever
    checks. Schema/syntax validation (ir_validator.py,
    syntax_validators.py) is deliberately rule-based and stays that way;
    this is deliberately not — "does this capture the right intent" is
    exactly the kind of judgment a fixed rule set cannot make. This is
    the actual mechanism behind Logic Correctness's plateau across every
    round of this project: nothing upstream of this agent ever verified
    intent-match at all, only schema validity."""

    def __init__(self):
        model_name = os.getenv("VERIFIER_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "qwen3.5:4b"))
        super().__init__(model_name=model_name)
        self.prompt = ChatPromptTemplate.from_messages([("system", _VERIFIER_SYSTEM_PROMPT)])

    def verify(self, nl_description: str, compiled_kql: str) -> VerificationResult:
        return self._invoke(
            prompt=self.prompt,
            pydantic_schema=VerificationResult,
            input_data={"nl_description": nl_description, "compiled_kql": compiled_kql},
        )
