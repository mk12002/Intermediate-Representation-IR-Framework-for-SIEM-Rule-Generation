import json
import os
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

from src.ir_engine.ir_schema import SecurityIR

from .base_agent import BaseAgent, build_chat_model

_SYSTEM_PROMPT = """You are converting a natural language detection description
directly into a Security IR object that conforms exactly to the schema below.
You may ONLY use field names that appear in the provided ASIM field reference
below — do not infer or guess field names from general knowledge of similar
platforms.

ASIM field reference:
{asim_field_list}

Common mistakes to avoid:
- A filter's "value" must be a literal data value the field would actually
  contain (an IP, a real string, a number) — never a description of scope
  or grouping. If the NL says results should be grouped or considered "per
  X" / "from a single X" (e.g. "from a single source"), that describes a
  group_by key, not something to compare a field against. Never invent a
  filter whose value is itself a description like "single source" or
  "IP address" — such a filter can never match real data.
- Pick event_type by the technical activity being described, not surface
  wording — surface wording has repeatedly caused wrong picks in practice:
  - DNS lookups/queries/resolution/NXDOMAIN -> DnsEvent. Even if the
    description also mentions network connections, if the actual content
    being checked is a DNS query/response, use DnsEvent, not
    NetworkSessionEvent.
  - HTTP requests, URLs, status codes, web errors -> WebSessionEvent. Even
    if the description says "connection" or "session", HTTP-specific
    content (status codes, URLs, user agents) means WebSessionEvent, not
    NetworkSessionEvent. Reserve NetworkSessionEvent for generic
    port/protocol/byte-count detail with no DNS or HTTP-specific content.
  - Process or command-line execution -> ProcessEvent. A description
    mentioning files, folders, or paths (e.g. "hidden in the recycle bin")
    is still ProcessEvent if the actual detection is a process executing
    with that path/folder referenced in its command line — only use
    FileEvent when the check is genuinely about a file being
    created/modified/read, not about which process ran.
  - Sign-in/login/authentication -> AuthenticationEvent. Registry key
    changes -> RegistryEvent. File or hash activity (not process
    execution) -> FileEvent.
- A threshold must actually reject some groups. "count > 0" or
  "distinct_count >= 1" is true for every group that exists in the result
  and filters nothing. If the description gives no concrete number, omit
  the threshold entirely rather than inventing one that can never fail.
  If the description DOES give a number (e.g. "more than 5", "at least
  100"), threshold.value must be that number — do not substitute a
  smaller or rounder number "to be safe."
- "filters" items are AND-ed together by default — a plain filter entry
  means "this AND everything else in the list". When the detection needs
  "(A or B) and (C or D)"-style logic — e.g. "contains 'user' or 'group',
  AND ends with '/do' or '/domain'" — use a FilterGroup entry (type="group",
  conditions=[...]) for each OR-set instead of flattening everything into
  separate AND-ed filters, which silently changes the meaning to "A and B
  and C and D" (much narrower, and usually wrong). The opposite mistake is
  just as wrong and just as common: when the description requires ALL of
  several specific things together — e.g. "uses the accepteula, -s, -r,
  and -q flags together" (four flags that must ALL be present) — those
  stay as separate, plain AND-ed filters, one per flag. Do NOT wrap a list
  of required conditions in a FilterGroup just because there are several
  of them; a FilterGroup is an OR, so wrapping required-together conditions
  in one would wrongly accept any single flag alone. Ask which word the
  description actually uses — "and"/"all of"/"together" means separate
  AND-ed filters; "or"/"either"/"any of" means a FilterGroup.
- Watch for a specific sentence shape: "(X1, X2, ..., or Xn) is/does Y" —
  e.g. "a known LOLBin (cmd.exe, ftp.exe, ..., or msiexec.exe) is executed
  with a command line referencing the recycler folder." The "or" here
  scopes ONLY the enumerated list (any one LOLBin name) — it does not
  extend to "Y" that follows. The correct structure is two separate
  AND-ed filters: one checking the process name is in the list (an `in`
  filter with all the names, or a FilterGroup if you must split it — both
  fine, since this part genuinely is an OR), AND a second, separate
  filter for Y (here, the command line referencing "recycler"). Folding Y
  into the same OR-set as the enumerated list — so that the recycler
  check becomes optional too — is wrong even though "or" appears right
  before Y grammatically; check what the "or" is actually a list of.
- For negated conditions (e.g. "does NOT contain sdelete", "not in the
  allowlist"), use the negated operators: !contains, !startswith, !endswith,
  !in, !has. Do NOT try to express negation by inverting the threshold or
  using == with a negated value — use the actual negated operator. Read the
  description carefully for which side of the check is negated: "flag X
  unless it also does Y" means flag X AND NOT Y, not flag NOT-X.
- When a condition uses word-boundary matching (e.g. "has 'error'"), use the
  "has" operator, not "contains". "has" matches whole terms (word boundaries),
  "contains" matches arbitrary substrings. Use "has_any" when checking if a
  field matches any value in a list by word boundary.
- group_by must include only the key(s) the description explicitly needs
  results broken down by — almost always just the actor/source identifier
  (e.g. SrcIpAddr or ActorUsername). Do not add extra keys the description
  never mentions (e.g. also grouping by hostname or username when it only
  says "per source"). Every extra group_by key splits one intended group
  into many smaller ones, so a threshold meant to fire on the source's
  total activity may never be reached. When in doubt, use fewer group_by
  keys, not more. The exception: when the description explicitly names
  several attributes of one actor together (e.g. "a single source
  IP/user/host combination"), group_by must include all of them — that
  phrasing is specifying the grouping granularity on purpose, not asking
  for a broader rollup.
- Most ASIM fields come in Src*/Dst* pairs (SrcUsername/DstUsername,
  SrcHostname/DstHostname, SrcIpAddr/DstIpAddr, etc.). Pick the prefix by
  which entity the description is actually about: the entity generating
  or initiating the activity ("a single source", "the client", "the
  account doing X") is Src*; the entity being connected to or acted upon
  ("the destination", "the target server") is Dst*. When several
  attributes describe the same actor (e.g. "source IP/user/host
  combination"), they all take the SAME prefix — picking DstUsername
  alongside SrcIpAddr and SrcHostname for what is the same single actor
  is wrong even though DstUsername is a real field.
- A vague outcome word ("error", "failure", "denied") is not enough on its
  own — picking the right event_type does not automatically cover the
  outcome. Find the field in the ASIM reference that actually encodes
  that outcome for this event type, and filter on it explicitly: for
  DnsEvent, "errors"/"failures" means the response code field is not the
  success value, DnsResponseCodeName != "NOERROR" — not just selecting
  DnsEvent with no outcome filter at all, and not EventResult (DNS events
  don't carry their result there). Check what the event type's own
  result/response/status-coded field actually is before assuming a
  generic EventResult=="Failure" covers it.
- For "Nth percentile" detections (e.g. "flag sessions in the bottom 5th
  percentile of duration", "top 1st percentile of bytes transferred"),
  use aggregation.function="percentile" with aggregation.field set to the
  field being measured AND aggregation.percentile set to N (0-100) — this
  is the only function that needs a second number alongside the field.
  Do not substitute min()/max()/avg() for a percentile request; they
  compute a different statistic and will misrepresent the detection. Note
  this computes the Nth percentile of field's values *within* each group
  — it cannot express a percentile taken *across* groups' own aggregate
  results (e.g. "processes at or below the 5th percentile of their own
  execution frequency, computed across all processes"), which needs a
  second pass over the first aggregation's output and is out of scope;
  if the description needs that, get as close as the IR allows rather
  than inventing an unrelated filter.
- Most real detections compute more than one summarize column together,
  not just the one the threshold checks — e.g. a count to threshold on,
  PLUS a make_set() of URLs/usernames/hostnames touched (for analyst
  triage context), PLUS min/max(TimeGenerated) for the activity window.
  Put the threshold-bearing column in "aggregation" and every other
  column in "additional_aggregations" — same Aggregation shape, just a
  list. Use function="make_set" or "make_list" to collect distinct
  values of a field into the output (limit is optional, e.g. 100, to cap
  collection size; KQL defaults to 128 if omitted). Every column across
  aggregation and additional_aggregations needs its own distinct
  result_alias — reusing one is rejected. Do not invent a second
  "aggregation" field or a second summarize clause for this — it is one
  summarize clause with several columns.
- A detection for a tool being used under a disguised or renamed name
  (e.g. "detect X even if the attacker renamed the binary to avoid
  detection") must NOT filter on the tool's own name or literal mention of
  it — that is the opposite of detecting evasion, since a renamed binary
  will not have that name anywhere. Instead: require the tool's
  distinctive, hard-to-avoid behavior — specific command-line flags that
  must ALL be present together, as separate AND-ed "has" filters, one per
  flag (NOT a FilterGroup — these flags are required together, not any
  one of them; there is no "has_all" operator, only "has", used once per
  flag) — AND explicitly exclude the cases where the name *does* obviously
  reveal the tool, using negated operators (!endswith / != on the process
  name, !has / !contains on the command line) — those excluded cases are
  the normal, non-evasive usage, not what this detection is for.
- When the detection involves correlation between two data sources, a
  baseline-vs-current comparison, or an exclusion lookup (e.g. "compare
  DNS queries today vs last 14 days", "exclude known-good IPs"), use the
  "join" field to define a JoinStage sub-query. The join stage has its own
  event_type, filters, aggregation, group_by, and time_window. Set join_on
  to the key(s) both sides share, and join_kind to "inner" (correlation),
  "leftanti" (exclusion), or "leftouter" (enrichment).
- For a baseline-vs-current detection specifically (e.g. "current count
  exceeds the 14-day baseline average by more than 50"), a plain threshold
  is not enough — comparing the current aggregation to a fixed number
  ignores the baseline entirely. Set threshold.compare_to_join_field to the
  join stage's own aggregation.result_alias (they must match exactly); the
  compiler then compares the main aggregation result against that joined
  column plus threshold.value as a margin, instead of against a bare
  number. Use threshold.value=0 if the description gives no margin and
  just wants current strictly greater than baseline.

Worked example — a baseline-vs-current detection. Description: "Flag a
source whose connection count in the last 1-day window exceeds its 14-day
baseline average by more than 50." The correct IR has, on the main object:
event_type the relevant session event type; an aggregation that counts
events with result_alias "CurrentCount"; group_by on the source identifier;
time_window "P1D"; and a threshold with operator ">", value 50, and
compare_to_join_field set to "BaselineAvg". The join object has its own
matching event_type; an aggregation that averages a count-like field with
result_alias "BaselineAvg" (note: avg/sum/min/max/distinct_count all
require a field — only count does not); group_by on the same source
identifier; time_window "P14D"; join_on the source identifier; and
join_kind "inner". Notice that "BaselineAvg" is spelled identically in both
the join's aggregation.result_alias and the main threshold's
compare_to_join_field — a mismatch here is rejected.

Worked example — a disguised/renamed-tool evasion detection. Description:
"Flag use of a secure-deletion tool's command-line flags (accepteula, -s,
-r, -q together), even if the attacker renamed the binary to avoid
detection." The correct IR filters are: one filter (or FilterGroup) for
each of the four flags appearing in the command line, all AND-ed together
(this is the actual evidence); PLUS a filter excluding the process name
that would obviously reveal the tool, using operator !endswith or != (this
is what makes it a renamed-binary detection); PLUS, if the description
also says the literal tool name must not appear anywhere, a filter on the
command line using !has or !contains for that name. There is no filter
requiring the tool's name to be present anywhere — every filter in this
detection either checks the behavioral evidence (the flags) or excludes
the obvious, non-disguised case.

Worked example — collecting evidence alongside the threshold. Description:
"Alert when a single source IP generates more than 100 HTTP 403 responses
in a day." The correct IR has aggregation: function="count", result_alias
"ForbiddenCount" (the threshold compares against this one); group_by the
source IP; threshold operator ">" value 100. To also surface the actual
URLs hit and the activity window for the analyst reviewing the alert — not
asked for explicitly here, but standard practice and often implied by "for
analyst triage" or similar phrasing — additional_aggregations would have
three more entries: function="make_set" field="Url" result_alias "Urls"
limit 100; function="min" field="TimeGenerated" result_alias
"EventStartTime"; function="max" field="TimeGenerated" result_alias
"EventEndTime". All four columns render in the same summarize clause;
only "ForbiddenCount" is ever referenced by the threshold.

{format_instructions}

Return ONLY one JSON object that is a valid INSTANCE of this schema —
actual field values describing this specific detection, never the schema
definition itself (no "$defs", "properties", or "required" keys in your
output)."""


class MonolithicAgent(BaseAgent):
    """Ablation 2 — merges Extraction + IR Builder into one prompt, skipping
    the intermediate ExtractionOutput structure. Isolates whether agent
    decomposition itself helps (RQ2). See docs/NL-KQL/MASTER_PLAN.md §18.
    """

    def __init__(self):
        model_name = os.getenv("IR_BUILDER_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "qwen3.5:4b"))
        super().__init__(model_name=model_name)
        self.prompt = ChatPromptTemplate.from_messages(
            [("system", _SYSTEM_PROMPT), ("user", "{nl_description}")]
        )

    def build(
        self,
        nl_description: str,
        asim_field_list: list[str],
        temperature_override: Optional[float] = None,
    ) -> SecurityIR:
        llm_backup = None
        if temperature_override is not None and temperature_override != self.temperature:
            llm_backup = self.llm
            self.llm = build_chat_model(self.model_name, temperature_override)

        try:
            return self._invoke(
                prompt=self.prompt,
                pydantic_schema=SecurityIR,
                input_data={
                    "nl_description": nl_description,
                    "asim_field_list": json.dumps(asim_field_list),
                },
            )
        finally:
            if llm_backup is not None:
                self.llm = llm_backup
