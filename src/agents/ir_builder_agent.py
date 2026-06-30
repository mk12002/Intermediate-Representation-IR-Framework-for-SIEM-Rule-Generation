import json
import os
import re
from pathlib import Path
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

from src.agents.base_agent import BaseAgent, build_chat_model
from src.generator.compiler import generate_kql
from src.ir_engine.ir_schema import ExtractionOutput, KqlPipeline
from src.ir_engine.ir_validator import ValidationResult

_LABEL_VS_DATA_FULL = """Worked example — a named actor/tool/list with no recallable concrete
value. Description: "Hunts for file creation events linked to Dev-0322's
compromise of ZOHO ManageEngine ADSelfService Plus software. Focuses on
files dropped during post-exploitation activity." "Dev-0322" is an
attribution label, not data — there is no real file path or name given
in the text, and you do not know the specific files this actor drops
(unlike a tool's documented flags, this isn't general knowledge you
already have). The correct WhereStage filters ONLY on what's concretely
named: the software being targeted, if it appears in a path/process
field (e.g. CommandLine or FilePath contains "ManageEngine"). Do NOT
filter ActorUsername/DvcHostname/any field on "Dev-0322" — that is never
literal log content. If genuinely nothing concrete remains after
removing the attribution label, fall back to the broadest correct
event-type filter (here, just `imFileEvent` with no further WhereStage)
rather than inventing a placeholder check just to have one.

The same mistake is easy to miss when the actor/group name is also an
ordinary English word, unlike a clearly ID-styled label such as
"Dev-0322" or a distinctive two-word codename like "Nylon Typhoon" —
check WHO the sentence credits the action to, not whether the word looks
unusual. Description: "Looks for potential webshell creation by the
threat actor Mercury after the successful exploitation of SysAid
server." "Mercury" here is functioning exactly like "Dev-0322" above —
it names WHO is credited with the activity, not WHAT happened or WHERE —
even though "Mercury" also happens to be a common name/word elsewhere.
Found live: this exact phrasing produced `ActorUsername == "Mercury"`
across every retry — the single most consistently-missed case in this
whole category. The correct filter keeps only the concrete technical
detail actually given (the targeted software, "SysAid", in a
path/process field) and drops "Mercury" entirely, exactly as "Dev-0322"
is dropped above.

A CVE/vulnerability identifier is the same kind of label, not data —
even though, unlike an actor name, it has a very recognizable surface
form ("CVE-2022-29972") that can look like it would obviously be
present in a real log. Description: "Looks for potential command
injection via the vulnerable third-party driver against Azure IR with
Managed VNet or SHIR processes... Reference: CVE-2022-29972." Found
live: this produced `CommandLine contains "CVE-2022-29972"` — a CVE
number is never literal command-line content; no real attack embeds
its own CVE ID in the command it runs. The correct filter keeps only
the concrete component/software the description actually names (here,
"Azure Integration Runtime" / "Managed VNet" / "SHIR" process activity,
e.g. CommandLine or ProcessName referencing "IntegrationRuntime") and
drops the CVE ID entirely. If nothing more specific than the CVE number
and the affected component is given, that genuinely is the limit of
what this description supports — the exact parent-process names and
command-line tokens a real detection for this CVE would need are
threat-intel knowledge, not something to fabricate from the ID alone;
add a `caveats` entry saying so rather than substituting the CVE number
itself as if it were a technical indicator.

Worked example — an external list with NO example values given at all.
Description: "Flags web requests with a user agent recognized as
malicious, from a predefined list referenced in a CSV file." No actual
user-agent string appears anywhere in the text. The WRONG move is
inventing placeholder-looking literals (e.g. "known_malicious_user_agent_1")
— these are not real data and would compile into a filter that can never
match anything, while looking like a working detection. The correct
move: omit the WhereStage filter on HttpUserAgent entirely and keep only
what's actually given (here, just `imWebSession`) — the same "don't
invent what isn't there" principle already used for thresholds applies
to list-valued literals too. A query missing a filter it can't ground is
more honest and more useful than one with a fake filter that silently
never fires.

This applies just as much when there is no CSV/feed/watchlist named at
all — just the bare phrase "a known IoC" or "a known malicious X," with
zero examples and no named external source either. Description:
"Identifies DNS requests for which the response IP address is a known
IoC." Treat "a known IoC" exactly like the CSV-list case above: there is
still nothing concrete to filter on. Two specific wrong moves to avoid,
both seen live on this exact phrasing: (1) inventing placeholder strings
("known_ioc_ip_1") — the same mistake as above; (2) writing `in ()` with
an EMPTY list — this parses and validates, but is a semantically
degenerate filter that matches nothing, ever, which is worse than no
filter at all (it looks like a working IoC check and silently never
fires, rather than honestly reporting on the activity it can observe).
The correct move is identical to the CSV case: omit the WhereStage
filter on the IP field entirely and keep just the table
(`imDns`/`imWebSession`), not an empty-list filter standing in for one."""

# Compressed variant for the principle-compression experiment
# (PROJECT_STATUS.md §4V/§4W) — critique item 2: same underlying
# principle as _LABEL_VS_DATA_FULL above (a reference/label is not
# literal data), stated once with 2 compact examples instead of 5
# elaborate ones with extensive "found live" narrative. Opt in via
# COMPRESSED_LABELS_PROMPT=1; default behavior (_LABEL_VS_DATA_FULL) is
# completely unaffected unless this env var is set, so this experiment
# cannot destabilize the validated default prompt.
_LABEL_VS_DATA_COMPRESSED = """A NAMED REFERENCE in the description — a threat-actor/APT name
(Dev-0322, Mercury, Nylon Typhoon), a MITRE technique name, or a
CVE/vulnerability ID (CVE-2022-29972) — is a LABEL for what's being
discussed, never literal data a log field would contain, even when the
label is also an ordinary word (judge by whether the sentence is
crediting WHO/WHAT-CATEGORY, not by how the word looks). Extract ONLY
the concrete technical detail given alongside it (a named tool,
software, or component) and drop the label itself. Example: "webshell
creation by threat actor Mercury after exploiting SysAid" -> filter on
FilePath/CommandLine containing "SysAid", never on any field equal to
"Mercury". If nothing concrete remains once the label is dropped, fall
back to the broadest correct event-type filter with no further
WhereStage, rather than inventing a placeholder check just to have one.

A referenced EXTERNAL LIST/FEED with NO concrete values given at all (a
CSV file, a watchlist, a bare "known IoC" with no examples) has nothing
to recall. Do NOT invent placeholder-looking values
("known_malicious_user_agent_1") or a degenerate empty list (`in ()`,
which silently matches nothing while looking like a real check) — OMIT
the filter entirely and add a `caveats` entry stating what was left out
and why, the same "don't invent what isn't there" rule already used for
numeric thresholds, applied to list/string values too."""


def _label_vs_data_section() -> str:
    if os.getenv("COMPRESSED_LABELS_PROMPT") == "1":
        return _LABEL_VS_DATA_COMPRESSED
    return _LABEL_VS_DATA_FULL


_COMMON_MISTAKES = """Common mistakes to avoid:
- Whenever you OMIT a filter because the description referenced data you
  cannot concretely ground (see the several worked examples below for
  this exact situation — a named actor/group, an external CSV/watchlist/
  feed, a bare "known IoC" with no values given), add ONE short string to
  the top-level `caveats` list explaining specifically what you left out
  and why (e.g. "no concrete IoC values were given for the source IP
  check, so no filter on SrcIpAddr was added"). This is the ONLY place
  such a note belongs — do not let it change the structural decision
  itself, and do not add a caveat for anything you DID implement.
  `caveats` defaults to an empty list; leave it empty when nothing was
  omitted.
- Build the AST pipeline in the order KQL actually flows:
  source_table -> where (filter rows) -> summarize (aggregate) -> where
  (apply a threshold to an aggregation result) -> extend/project (shape
  output). A threshold is just a WhereStage placed AFTER the SummarizeStage
  whose result_alias it filters on — there is no separate "threshold"
  concept.
- likely_event_type was already pinned to an exact ASIM type name by the
  extraction step using the same keyword anchors below — in the normal
  case, source_table should just BE likely_event_type. Re-derive it
  yourself only as a fallback (e.g. if likely_event_type isn't one of the
  real ASIM type names, or visibly conflicts with the field reference
  actually provided) — these rules exist for that fallback case, not as
  the primary path anymore.
- Pick source_table by the technical activity being described, not surface
  wording — surface wording has repeatedly caused wrong picks in practice:
  - DNS lookups/queries/resolution/NXDOMAIN -> DnsEvent. Even if the
    description also mentions network connections, if the actual content
    being checked is a DNS query/response, use DnsEvent, not
    NetworkSessionEvent.
  - HTTP requests, URLs, status codes, User-Agent strings, web errors ->
    WebSessionEvent. Even if the description says "connection" or
    "session", or never says the word "HTTP" at all, HTTP-specific
    content (status codes, URLs, user agents, request methods) means
    WebSessionEvent, not NetworkSessionEvent. Reserve NetworkSessionEvent
    for generic port/protocol/byte-count detail with no DNS or
    HTTP-specific content.
  - Process or command-line execution -> ProcessEvent. A description
    mentioning files, folders, paths, or even "wiping"/"deletion" as the
    attacker's goal is still ProcessEvent if the actual detection is a
    process executing with that path/command-line content — only use
    FileEvent when the check is genuinely about a file being
    created/modified/read, not about which process ran.
  - Sign-in/login/authentication -> AuthenticationEvent. Registry key
    changes -> RegistryEvent. File or hash activity (not process
    execution) -> FileEvent.
- source_table MUST be a recognized ASIM event type from the field
  reference's own key (an exact match to one of the type names in this
  prompt, e.g. "AuthenticationEvent", "DnsEvent") — never a free-text
  label describing the technique or the data being looked for (e.g. "DNS
  query", "application error", "error event"). A label that isn't an
  exact match to a real ASIM event type fails validation immediately and
  every field reference after it fails too, since there's no schema to
  check them against.
- A SummarizeStage keeps ONLY its group_by keys and new aggregation
  aliases — every other field from before it is gone afterward. If a
  WhereStage needs to filter on a raw field (e.g. a port number, a status
  code) AND that field is not itself something you're aggregating or
  grouping by, that WhereStage must come BEFORE the SummarizeStage that
  would otherwise drop it — putting it after produces FIELD_NOT_FOUND, not
  a meaningful filter. If the description's grouping is described as a
  "pair" or "combination" of two fields (e.g. "per source/port pair"),
  group_by needs BOTH fields, in the SAME SummarizeStage, not just one —
  check every noun in a "per X" / "by X" phrase for a second field you
  may have dropped.
- A filter's "value" must be a literal data value the field would actually
  contain (an IP, a real string, a number, or a list of those for "in") —
  never a description of scope or grouping, and never a reference to
  another field (Filter.value is always a literal; to compare one field
  against another, use an ExtendStage to compute the comparison first, then
  filter on the computed field — see the worked examples below). It must
  also never be a KQL FUNCTION CALL written as a string, like
  '"ago(1h)"' or '"startofday(now())"' — Filter.value is compared
  literally, so a string that merely looks like a function call is
  compared as that exact text, never evaluated. Relative time windowing
  is already the SummarizeStage's time_window field's job (it compiles to
  a real bin(TimeGenerated, ...) call) — do not add a redundant WhereStage
  filter trying to express "today" or "the last hour" as a fake literal;
  if a stage genuinely needs a real ago()/now() comparison with no
  SummarizeStage to anchor it, that belongs in an ExtendStage's
  expression (a real, unquoted KQL expression), never inside Filter.value.
- An ExtendStage's "expression" must only call real, standard KQL
  functions (strcat, tostring, iff, datetime_diff, array_length, etc.) —
  never an invented function name that sounds plausible but doesn't exist
  in KQL (e.g. there is no array_avg() or array_stddev()). If the
  description needs a statistic KQL has no direct function for, use the
  closest real function or a simpler computation instead of inventing one
  — an invented function name fails at query time exactly like a
  hallucinated field name would.
- Aggregation functions (count, sum, avg, min, max, dcount, percentile,
  stdev, variance, make_set, make_list) ONLY exist inside a
  SummarizeStage's aggregations list — there is no scalar/row-wise form of
  any of them, so an ExtendStage expression must never call one directly
  (e.g. "extend X = stdev(Count)" is invalid KQL; stdev has no group of
  rows to operate over there). If a description needs a value computed
  FROM an aggregation (a margin, a ratio, a deviation, a coefficient of
  variation), compute the aggregation(s) in a SummarizeStage first (each
  with its own result_alias), then reference those aliases in a later
  ExtendStage to combine them — e.g. for "how consistent/regular" a
  per-group value is, aggregate with stdev() AND avg() as two separate
  columns in the SAME SummarizeStage, then extend a ratio of the two
  (coefficient of variation = stdev / avg) afterward. When this
  SummarizeStage is itself reducing a PRIOR SummarizeStage's per-entity
  results (e.g. computing the deviation of a daily count over a 14-day
  window), the FIRST stage's time_window must be a finer bucket (e.g.
  "P1D") than the overall window, producing multiple rows per entity for
  the second stage's stdev()/avg() to operate over — giving both stages
  the SAME wide time_window (e.g. "P14D" on both) collapses the first
  stage to exactly one row per entity, and stdev() of a single row is
  always 0 or null, silently making the whole detection match nothing.
  Watch which framing the description actually uses before reaching for
  stdev() at all: "how consistent/regular/variable is X" (an intrinsic
  property of X's own history, no notion of "current" vs "before") is
  the stdev/avg coefficient-of-variation pattern above. "X's deviation
  FROM its baseline/average, OVER the last N days" (comparing a CURRENT
  value against a HISTORICAL average) is a different question entirely —
  that is the baseline-vs-current JOIN pattern (current period's
  aggregate vs. a separately-computed prior-period average, see the
  worked example below), not a same-period stdev. Defaulting to stdev
  when the description is really asking for current-vs-baseline answers
  a different statistical question than the one asked.
- A threshold must actually reject some groups. "FailCount > 0" or
  "DistinctCount >= 1" is true for every group that exists in a summarize
  result (count/dcount can never be below 1 for a group that exists) and
  filters nothing. If the description gives no concrete number, omit the
  where-stage entirely rather than inventing one that can never fail. If
  the description DOES give a number, use that exact number — do not
  substitute a smaller or rounder one "to be safe."
- The same "omit, don't invent" rule applies when a threshold or filter
  VALUE is explicitly described as sourced from an external configuration
  mechanism by name — a watchlist, a config table, an external list —
  with no concrete number or value actually given in the text itself
  (e.g. "port usage higher than the threshold defined in the
  'NetworkSession_Monitor_Configuration' watchlist"). There is no IR
  construct for "look this value up from X," and there must not be one
  invented ad hoc — `Filter.value` is a literal (string/number/bool/list),
  never a nested lookup/reference object. Found live: attempting to
  express the watchlist reference as a structured value produced a hard
  schema validation failure, and the repair churn that followed landed on
  fabricated literal ports (e.g. 80/443/22/3389, never mentioned in the
  description) or a nonsensical self-join — both worse than just omitting
  the condition. Treat this exactly like a threshold with no number given:
  drop the WhereStage filter on that specific field entirely and keep
  only the structural part of the request (here, the SummarizeStage
  report on port usage), the same as the existing "no concrete number ->
  omit" rule above.
- Do not invent a summarize+threshold the description never asked for. A
  detection that's just "flag any process matching these filters" stays a
  flat list of WhereStage filters — adding an unrequested
  "summarize Count = count() by X | where Count > 0" stage doesn't add
  information, and (per the rule above) the ">0" part filters nothing
  anyway.
- The opposite mistake is just as common: a description asking for a
  "rundown", "breakdown", "summary", or "inventory" of some activity DOES
  need a SummarizeStage — it is asking for a grouped report covering
  every matching event, not a yes/no detection. Do NOT leave this as a
  bare WhereStage with no aggregation at all just because there's no
  threshold language — "report on X" and "alert if X happens too much"
  are different requests even when X is the same activity. Build it as a
  WhereStage filtering to the relevant activity, then a SummarizeStage
  grouping by whatever entity makes the report useful (e.g. script name,
  extracted command-line detail) with count() plus min/max(TimeGenerated)
  for the activity window, and NO threshold WhereStage afterward — a
  report wants everything that matched, not a filtered subset.
- "filters" items inside one WhereStage are AND-ed together by default —
  a plain filter entry means "this AND everything else in the list". When
  the detection needs "(A or B) and (C or D)"-style logic, use a
  FilterGroup entry (type="group", conditions=[...]) for each OR-set
  instead of flattening everything into separate AND-ed filters, which
  silently changes the meaning to "A and B and C and D" (much narrower,
  usually wrong). The opposite mistake is just as common: when the
  description requires ALL of several specific things together — e.g.
  "uses the accepteula, -s, -r, and -q flags together" (four flags that
  must ALL be present) on the SAME field — use ONE Filter with
  operator="has_all" and value=["accepteula", "-s", "-r", "-q"]; this is
  a real KQL operator (confirmed in ground truth, e.g. exactly this
  sdelete-flags case) and the more direct match for "all of these
  together" than four separate filters, though four separate plain "has"
  Filter entries in the same WhereStage compile to the identical AND
  logic and are equally correct when the terms are checked on DIFFERENT
  fields (has_all only applies within one field). Do not wrap required-
  together conditions in a FilterGroup just because there are several of
  them — a FilterGroup is an OR, so wrapping them in one would wrongly
  accept any single flag alone. Ask which word the description actually
  uses: "and"/"all of"/"together" means has_all (one field) or separate
  AND-ed filters (different fields); "or"/"either"/"any of" means
  has_any or a FilterGroup.
- `in`/`!in` are case-SENSITIVE by default in KQL, unlike contains/has/
  startswith/endswith above (all case-insensitive by default). When the
  description's list-membership check should match regardless of case
  (e.g. comparing a freeform username/hostname list with inconsistent
  casing), use operator="in~"/"!in~" — the explicit case-insensitive
  forms — instead of plain "in"/"!in".
- Symmetrically, plain "=="/"!=" are also case-SENSITIVE by default for
  strings in KQL. When an equality check should tolerate case variation
  the description doesn't promise to be consistent (e.g. a filename or
  process name: "FileName == 'powershell.exe'" would miss
  "PowerShell.EXE"), use operator="=~"/"!~" instead — the explicit
  case-insensitive equality forms. The negated form is exactly "!~" —
  NOT "!=~". Every OTHER negated operator in this schema is formed by
  prepending "!" to its positive spelling (contains -> !contains, in~ ->
  !in~, has_cs -> !has_cs), which makes "!=~" look like the same pattern
  applied to "=~" — it is not; "!=~" is not a real KQL operator and will
  fail validation. "=~"/"!~" is its own irregular pair, the same way
  "=="/"!=" is (not "==" and "!==" or "not =="). If you need a NEGATED
  case-insensitive equality check, write operator="!~", never "!=~".
  And the reverse case: contains/
  startswith/endswith/has are case-INSENSITIVE by default (see above) —
  use the explicit "_cs" suffixed forms (operator="contains_cs"/
  "startswith_cs"/"endswith_cs"/"has_cs", with negated "!..._cs"
  counterparts) only when the description's exact casing IS the
  detection signal — e.g. matching a base64-encoded command-line
  fragment, where a different-case string decodes to entirely different
  bytes, so a case-insensitive match would silently miss the real
  payload or over-match unrelated content. Default to the
  case-insensitive forms unless the description gives a specific reason
  casing matters; do not reach for "_cs"/"=~" operators out of caution
  alone — most fields (usernames, hostnames, process names as written by
  an analyst) have no casing guarantee, which is exactly why
  case-insensitive is each operator's own KQL default.
- Watch for a specific sentence shape: "(X1, X2, ..., or Xn) is/does Y" —
  e.g. "a known LOLBin (cmd.exe, ftp.exe, ..., or msiexec.exe) is executed
  with a command line referencing the recycler folder." The "or" here
  scopes ONLY the enumerated list (any one LOLBin name) — it does not
  extend to "Y" that follows. The correct structure is two separate
  AND-ed filters in the same WhereStage: one checking the process name is
  in the list (an "in" filter, or a FilterGroup if you must split it —
  both fine, since this part genuinely is an OR), AND a second, separate
  filter for Y (here, the command line referencing "recycler"). Folding Y
  into the same OR-set as the enumerated list — so the recycler check
  becomes optional too — is wrong even though "or" appears right before Y
  grammatically; check what the "or" is actually a list of.
- A comma-separated list of EXEMPLARS introduced by "such as", "like",
  "including", or "e.g.", and often closed with "etc."/"and so on" — even
  with NO literal word "or" anywhere — is still an OR-list, the same as
  an explicit "(X, Y, or Z)". E.g. "URLs containing file types such as
  .ps1, .bat, .vbs, .scr etc." means "matches ANY ONE of these
  extensions," not "matches ALL of them." Found live: a held-out
  generalization check produced four separate AND-ed `Url contains
  ".ext"` filters for exactly this phrasing — a query requiring all four
  extensions to appear in the same URL simultaneously, which real URLs
  essentially never do, so the detection silently never fires. The
  correct structure is one `has_any`/`in` filter (or a `FilterGroup`)
  over all the listed exemplars, exactly as if the description had
  written "or" between each one — "such as ... etc." is just a more
  natural-language way of writing the same enumerated alternative-set,
  not a different, conjunctive requirement.
- For negated conditions (e.g. "does NOT contain sdelete", "not in the
  allowlist"), use the negated operators: !contains, !startswith,
  !endswith, !in, !has. Do NOT try to express negation by inverting the
  threshold or using == with a negated value. Read the description
  carefully for which side of the check is negated: "flag X unless it also
  does Y" means flag X AND NOT Y, not flag NOT-X.
- When a condition uses word-boundary matching (e.g. "has 'error'"), use
  the "has" operator, not "contains" — "has" matches whole terms,
  "contains" matches arbitrary substrings. Use "has_any" for "matches any
  of these terms by word boundary".
- A detection for a tool used under a disguised or renamed name (e.g.
  "detect X even if the attacker renamed the binary to avoid detection")
  must NOT filter on the tool's own name or literal mention of it — that
  is the opposite of detecting evasion, since a renamed binary will not
  have that name anywhere. Instead: require the tool's distinctive,
  hard-to-avoid behavior (specific command-line flags that must ALL be
  present together, as separate AND-ed "has" filters in one WhereStage)
  AND explicitly exclude the cases where the name *does* obviously reveal
  the tool, using negated operators (!endswith / != on the process name,
  !has / !contains on the command line) — those excluded cases are the
  normal, non-evasive usage, not what this detection is for. Exclude only
  the ONE literal name the description actually names — do not invent
  additional name variants (e.g. a "64-bit" version) the description
  never mentions; every extra exclusion is one more condition that can
  get tangled into a wrong FilterGroup. Every filter in this detection is
  either a plain AND-ed "has" (the behavioral evidence) or a plain AND-ed
  negated filter (the exclusion) — never a FilterGroup; there is no OR
  anywhere in this pattern.

- A FilterGroup's conditions are normally flat individual Filters OR-ed
  together. But when the description needs "(A and B) or (C and D)" —
  several DIFFERENT cases, each itself requiring more than one condition
  together — a plain Filter inside the group can't express the "and B"
  part. Use an AndGroup entry (type="and_group", conditions=[...]) as one
  of the FilterGroup's conditions instead: each AndGroup is one OR-branch
  whose own conditions are AND-ed. Reach for this whenever the description
  describes several different per-category checks that must each be
  internally consistent (e.g. "this app type on this port, OR that app
  type on that port") — a single flat FilterGroup of plain Filters would
  wrongly let ANY one condition from ANY category satisfy the whole thing.

Worked example — app/port-mismatch detection requiring OR-of-AND-pairs.
Description: "Flag a session where the destination app is DNS but the
port isn't 53, OR the app is HTTP but the port isn't 80, OR the app is
SSL but the port isn't 443." The correct WhereStage has ONE FilterGroup
with three AndGroup entries (not three plain Filters, and not three
separate WhereStages): AndGroup 1 = [DstAppName == "dns", DstPortNumber
!= 53]; AndGroup 2 = [DstAppName == "http", DstPortNumber != 80];
AndGroup 3 = [DstAppName == "ssl", DstPortNumber != 443]. This compiles to
"(DstAppName == "dns" and DstPortNumber != 53) or (DstAppName == "http"
and DstPortNumber != 80) or (DstAppName == "ssl" and DstPortNumber !=
443)" — correctly requiring BOTH the app-type match AND its own port
mismatch together within each branch. Writing this as three plain
Filters in one FilterGroup instead (losing the AND within each branch)
makes the check satisfied by ANY mismatched port on ANY traffic
regardless of app type — almost always true, not a real check.
- FilterGroup REQUIRES at least 2 conditions — it exists ONLY to express
  a genuine OR between two or more alternatives. If the description
  only ever gives ONE concrete example of the category (e.g. "like DNS
  not running on port 53" with no second app named), there is no real OR
  to express yet — do NOT wrap that single AndGroup in a FilterGroup just
  because AndGroup-inside-FilterGroup is the pattern you saw worked; a
  FilterGroup with only one entry fails immediately (the schema requires
  2+). When there's only one concrete branch, skip both FilterGroup and
  AndGroup entirely and use plain, AND-ed Filter entries directly in the
  WhereStage instead — the same as any other single-conjunction check.
  Only reach for FilterGroup once the description actually names or
  implies a second, different alternative.

{label_vs_data_section}

Worked example — "external"/"internal" IP framing. Description:
"Detects external IP connections to management ports (5985, 5986,
1270)." "External" maps to a real KQL check, `ipv4_is_private(...)`
being false — there is no ASIM field that's already a boolean for this.
Build it as: an ExtendStage computing "IsExternal = not(ipv4_is_private(SrcIpAddr))",
then a WhereStage filtering "IsExternal == true" alongside the port
filter. Do NOT substitute an unrelated, always-true check like
"SrcIpAddr != \"\"" (checking the field isn't empty says nothing about
internal vs. external) — that silently drops the one condition the
description is actually built around.

Worked example — AND of two OR-sets (the mirror image of the pattern
above — do not confuse the two). Description: "Alert when a process is
invoked with 'user' or 'group' arguments TOGETHER WITH a /do or /domain
flag." This needs "(has 'user' or has 'group') AND (has '/do' or has
'/domain')" — both OR-groups must independently hold at once. This is
already expressible WITHOUT AndGroup: a WhereStage's filters list is
itself an AND of its entries, so use TWO separate FilterGroup entries in
the SAME WhereStage — FilterGroup 1 = [has "user", has "group"];
FilterGroup 2 = [has "/do", has "/domain"]. Compiles to two AND-ed
"| where (...)" conditions. The common, WRONG shortcut is collapsing both
OR-sets into ONE FilterGroup with has_any of all four terms — that turns
the AND into an OR, satisfied by "user" alone with no /domain flag at
all, which is a materially different (and much broader) detection than
the one being asked for. Ask: are there really TWO independent
either/or conditions that must BOTH hold, or just one list of
interchangeable options? Two conditions -> two FilterGroups in one
WhereStage; one list -> one FilterGroup (or AndGroup, if combined with a
second category, per the worked example above).

Worked example — a disguised/renamed-tool evasion detection. Description:
"Flag use of a secure-deletion tool's command-line flags (accepteula, -s,
-r, -q together), even if the attacker renamed the binary to avoid
detection." The correct WhereStage has exactly two plain, AND-ed
filters, no FilterGroup: one "has_all" filter on the command line field
with value=["accepteula", "-s", "-r", "-q"] (this is real KQL, matches
ground truth for this exact case, and is more direct than four separate
"has" filters — both compile to the same AND logic, so either is
correct, but prefer has_all when every term is checked on the SAME
field), PLUS one "!endswith" filter on the process name field for the
tool's own literal name. Two filters, one WhereStage, zero FilterGroups,
zero "or"s. Use ONLY the exact flag values given in the extraction's
candidate_fields/action_description — never invent a plausible-sounding
flag (e.g. "-p") that isn't one of them, and never add a positive
"has"/"contains" check for the tool's own name anywhere — that would
require the literal name to be present, defeating the renamed-binary
case the whole detection exists for. The "!endswith" value must be the
tool's FULL real filename, extension included (value="sdelete.exe", not
value="sdelete") — a process named exactly "sdelete.exe" still does NOT
end with the bare string "sdelete" (it ends with ".exe"), so a
truncated value silently fails to exclude the literal-name case it
exists to exclude, the opposite of what this filter is for.

Worked example — exact-casing matters (the case where the "_cs"/"=~"
operators above are the RIGHT choice, not the cautious-overuse mistake).
Description: "Flag a PowerShell command line containing an encoded
launcher flag together with a base64-encoded fragment of a known
malicious script's start." The flag check ("-enc"/"-EncodedCommand"
spelled inconsistently across real samples) still wants the ordinary
case-insensitive "has" — casing isn't the signal there. But the
base64 fragment itself needs operator="contains_cs": base64 is
case-sensitive by construction (it encodes raw bytes; changing the case
of a base64 character changes which bytes it decodes to), so a
case-insensitive "contains" could match a visually-similar but
actually-different encoded string, or silently miss the real one if the
casing in the live event differs from a same-meaning but
differently-encoded variant. Two AND-ed filters in one WhereStage: one
ordinary "has" on the command-line field for the encoded-launcher flag,
one "contains_cs" on the same field for the literal base64 fragment —
do not make the second filter case-insensitive just because the first
one is.
- Most ASIM fields come in Src*/Dst* pairs (SrcUsername/DstUsername,
  SrcHostname/DstHostname, SrcIpAddr/DstIpAddr). Pick the prefix by which
  entity the description is actually about: the entity generating or
  initiating the activity ("a single source", "the client") is Src*; the
  entity being connected to or acted upon ("the destination", "the target
  server") is Dst*. When several attributes describe the same actor
  together (e.g. "source IP/user/host combination"), they all take the
  SAME prefix and group_by must include all of them.
- A property belongs to the field of the THING it's actually a property
  of, not the field of whichever entity is the sentence's grammatical
  subject. Found live: "a source IP address accesses web URLs ending
  with .ps1" produced a filter checking SrcIpAddr endswith ".ps1" (or
  has ".ps1") instead of Url endswith ".ps1" — an IP address has no
  file extension, so this is never meaningful, but "source IP address"
  is the sentence's subject and ".ps1" is the sentence's last-mentioned
  detail, an easy but wrong pattern-match. Identify what the description
  is actually saying ENDS WITH/CONTAINS/IS the value — here, the URL,
  not the source — and filter THAT field, even when the source/actor is
  named earlier and more prominently in the sentence.
- A vague outcome word ("error", "failure", "denied") is not enough on its
  own — picking the right event type doesn't automatically cover the
  outcome. Find the field in the ASIM reference that actually encodes that
  outcome for this event type: for DnsEvent, "errors"/"failures" means
  DnsResponseCodeName != "NOERROR" — not just selecting DnsEvent with no
  outcome filter, and not EventResult (DNS events don't carry their result
  there).
- For "Nth percentile" detections (e.g. "bottom 5th percentile of
  duration"), use aggregation.function="percentile" with field set to the
  field being measured AND percentile set to N (0-100) — the only function
  needing a second number alongside the field. Do not substitute
  min()/max()/avg() for a percentile request.
- Most real detections compute more than one summarize column together,
  not just the one a threshold checks — e.g. a count to threshold on, PLUS
  a make_set() of URLs/usernames touched (analyst triage context), PLUS
  min/max(TimeGenerated) for the activity window. List every column as a
  separate entry in the SAME SummarizeStage's "aggregations" — do not
  invent a second summarize stage just to add an evidence column. Every
  aggregation in one SummarizeStage needs its own distinct result_alias.
  Critically: an evidence/context field (a URL, a user agent, a method, a
  hostname touched) belongs in "aggregations" via make_set()/make_list()
  — it must NEVER also appear in "group_by". Putting an evidence-type
  field in group_by silently fragments the very count the threshold is
  meant to measure into one row per combination (e.g. grouping by
  HttpUserAgent in addition to the source splits one busy source into
  many separate under-threshold rows, defeating the volume check) —
  the opposite of what an "evidence column" is for. group_by should
  contain ONLY the entity (or entity pair) the description names as the
  thing being measured per — e.g. "a single source" means group_by=
  [SrcIpAddr] alone; every other interesting field the description
  mentions is evidence, not an extra grouping key.
- A result_alias that names a SPECIFIC SUBSET of events (e.g.
  "NXDomainCount", "FailedLoginCount", "DeletedKeyCount") is a PROMISE
  that the events being counted were actually filtered to that subset
  first — found live: a count aliased "NXDomainCount" but computed as
  plain count()/count(DnsResponseCodeName) with NO preceding WhereStage
  filtering to DnsResponseCodeName=="NXDOMAIN" silently counts ALL DNS
  responses, not specifically NXDOMAIN ones — the alias name lies about
  what the number actually measures, and nothing downstream (the
  threshold, the anomaly check) can tell the difference from a
  genuinely-filtered count. If the description names a specific kind of
  event ("NXDomain response count", "creation AND deletion events"),
  add a WhereStage filtering to exactly that subset BEFORE the
  SummarizeStage that counts it (this IR has no countif/conditional-
  aggregation construct — filter-then-count is the only correct shape)
  — never name an aggregation after a subset you never actually
  selected.
- A description asking for "the most recent event per X" / "the latest
  activity for each host" / "the first occurrence per account" needs
  SummarizeStage.arg_max (most recent) or arg_min (first/earliest), NOT
  a plain max(TimeGenerated) aggregation — max(TimeGenerated) only
  returns the TIMESTAMP itself, dropping every other column from that
  row, while arg_max/arg_min return the FULL ROW at that timestamp
  (every other field the description also wants, e.g. "with the command
  line and account from that latest event"). Set order_field to the
  field being maxed/minned (almost always "TimeGenerated") and
  carry_fields to the other columns the description wants alongside it
  — use ["*"] for "every other field," or name them explicitly when
  only specific ones matter. arg_max and arg_min can combine with
  ordinary aggregations (count(), make_set(), etc.) in the SAME
  SummarizeStage — they are siblings, not an alternative to
  "aggregations". Do not invent a JoinStage or a second SummarizeStage
  to get "the row with the max timestamp" — that's exactly what
  arg_max already does in one stage. Set result_alias when the
  description names what to call this column (e.g. "the time of the
  most recent matching indicator" -> result_alias="LatestIndicatorTime")
  — real ground truth almost always renames it rather than leaving it
  under the raw order_field name (confirmed in 30+ real threat-intel-
  deduplication queries, all of the shape "LatestIndicatorTime =
  arg_max(TimeGenerated, *) by IndicatorId" before joining against the
  deduplicated, most-current version of each indicator). Leave
  result_alias unset only when nothing in the description suggests a
  name for it. CRITICAL: result_alias renames ONLY the order_field's own
  output column — every name in carry_fields ALWAYS keeps its own bare
  name in the output, NEVER prefixed by result_alias. Found live: a
  result_alias of "FirstQuery" with carry_fields=["DnsQuery"] produced a
  downstream ProjectStage referencing "FirstQuery_DnsQuery" — a field
  that doesn't exist (the real output columns are "FirstQuery" and
  "DnsQuery", two separate, unprefixed names) — every trial of this
  exact case failed validation the same way. Reference a carried field
  by its own plain name in any later stage (e.g. ProjectStage.fields,
  a WhereStage filter), never as a manufactured "alias_fieldname"
  combination.
- When the detection involves correlation between two data sources, a
  baseline-vs-current comparison, or an exclusion lookup, use a JoinStage.
  Its right_pipeline is a full, independent KqlPipeline (its own
  source_table and stages). Set join_on to the key(s) both sides share,
  and kind to "inner" (correlation), "leftanti" (exclusion), or
  "leftouter" (enrichment) for the vast majority of cases. Less common
  real KQL join kinds are also available when the description genuinely
  calls for them: "leftsemi" (keep only left rows with a match, but only
  left-side columns — a lighter-weight exclusion-lookup's opposite),
  "rightanti"/"rightsemi" (the same two ideas, mirrored to keep right-side
  rows/columns instead), "rightouter" (enrichment mirrored), and
  "innerunique" (KQL's default inner join, deduplicating left-side keys
  before joining — rarely what a detection actually wants, since it can
  silently drop legitimate duplicate rows; prefer plain "inner" unless the
  description specifically describes one-row-per-key semantics).
- When a field's value needs to be checked against ANOTHER field's value
  (not a literal, and not a fixed duration threshold) — most commonly
  "does this event's time fall within the window bounded by these two
  OTHER fields" after a join — use Filter.field_ref instead of value.
  Set field_ref to the other column's name; leave value unset. This is
  for a DYNAMIC bound defined by other columns, not for "within N minutes
  of a single other event" (that's the datetime_diff-then-filter pattern
  in the next worked example below — use field_ref only when there is no
  single fixed duration, only two other columns that themselves bound
  the range). Do NOT put the other field's name in `value` — Filter.value
  is always a literal and would be compared against that exact string,
  never the column's actual contents.

Worked example — field_ref bracketing a value between two joined
columns. Description: "Flag a PowerShell process launch that falls
within the span of authentication activity on the same host." Build it
as: (1) a WhereStage filtering to the named process; (2) a JoinStage,
kind "inner", join_on the shared host identifier, whose right_pipeline
summarizes the authentication table's min(TimeGenerated) as
result_alias "FirstAuthTime" and max(TimeGenerated) as result_alias
"LastAuthTime", grouped by the same host; (3) an ExtendStage computing
"ProcessTime" = TimeGenerated (so the comparison has a stable name
independent of which side of the join TimeGenerated came from); (4) a
WhereStage with TWO filters, both using field_ref instead of value:
one filter has field "ProcessTime", operator ">=", and field_ref
"FirstAuthTime" (value left unset); the other has field "ProcessTime",
operator "<=", and field_ref "LastAuthTime" (value left unset). A
filter that instead sets field "ProcessTime", operator ">=", and value
"FirstAuthTime" is WRONG — it compares ProcessTime against the literal
STRING "FirstAuthTime", which can never be a real timestamp and so can
never correctly match.

Worked example — a baseline-vs-current detection. Description: "Flag a
source whose connection count in the last 1-day window exceeds its 14-day
baseline average by more than 50." Build it as: (1) a SummarizeStage
computing the current count, result_alias "CurrentCount", grouped by the
source, time_window "P1D"; (2) a JoinStage, kind "inner", join_on the
source identifier, whose right_pipeline independently summarizes the same
table's count over time_window "P14D" as result_alias "BaselineCount" then
an ExtendStage dividing it by 14 into "BaselineAvg"; (3) back in the main
pipeline, an ExtendStage computing "Margin" = CurrentCount - BaselineAvg;
(4) a final WhereStage filtering "Margin > 50". A bare WhereStage
comparing CurrentCount directly against the LITERAL STRING "BaselineAvg + 50"
does NOT work — Filter.value is a plain literal (it would be compared
against that exact text, never evaluated as an expression). For a
field-vs-CONSTANT-expression comparison like this one (current count vs.
a computed margin), the extend-then-filter two-step above is the right
shape. For a field-vs-ANOTHER-FIELD comparison instead (e.g. "is this
field's value between two other fields' values"), use Filter.field_ref
— see the worked example after the JoinStage explanation below; do not
reach for field_ref here, where there is no second field to compare
against, only a computed threshold. If the description groups by a PAIR
of fields (e.g. "per
source/port pair", "per private-IP source/port pair") rather than a
single source identifier, that pair must appear, identically, in THREE
places, not just one: the main pipeline's SummarizeStage group_by, the
right_pipeline's SummarizeStage group_by, AND join_on — dropping the
second field from any one of those three breaks the per-pair correlation
even if the other two still have it. Check all three before finishing.

Worked example — two SPECIFIC, DIFFERENT named events for the SAME entity,
in order, within a window (distinct from baseline-vs-current, which
compares a magnitude, not event identity). Description: "Flag a host that
issues a New-MailboxExportRequest and then a Remove-MailboxExportRequest
for the same user within 1 hour." A simple count threshold ("2+
occurrences of either event") is WRONG here — it would also match two
exports with no delete, or a delete before any export. Build it as: (1) a
WhereStage filtering rows down to ONLY the first named event
(CommandLine has 'New-MailboxExportRequest'), then a SummarizeStage
computing ExportTime = min(TimeGenerated), grouped by the shared entity
(Dvc, ActorUsername); (2) a JoinStage, kind "inner", join_on the shared
entity, whose right_pipeline independently filters rows down to ONLY the
second named event (CommandLine has 'Remove-MailboxExportRequest') then
summarizes DeleteTime = min(TimeGenerated), grouped by the SAME entity
keys; (3) an ExtendStage computing "MinutesBetween" =
datetime_diff('minute', DeleteTime, ExportTime); (4) a WhereStage filtering
"MinutesBetween > 0 and MinutesBetween <= 60" — the ">0" half is required
and easy to drop: without it, a delete that happened BEFORE the export
would still match, which is backwards. Filtering to the specific event
BEFORE each summarize (not after, and not as a single combined count) is
what makes each side of the join actually mean "this specific named event
happened," rather than "some event in a list of two happened."

Worked example — percentile computed across groups, not within one
(harder, but now expressible). Description: "Surface processes whose
execution frequency over the last 3 days falls at or below the 5th
percentile of all processes' frequencies." A single SummarizeStage cannot
do this — percentile here must be computed ACROSS the per-process frequency
values, then compared back against each process's own frequency, which
needs two passes joined together: (1) a SummarizeStage computing each
process's frequency, result_alias "Frequency", grouped by process name,
time_window "P3D"; (2) an ExtendStage adding a constant "JoinKey" = 1 (a
trick to express a cross-join — every row joins to the single global
percentile row, since there's no per-process key the percentile shares);
(3) a JoinStage, kind "inner", join_on ["JoinKey"], whose right_pipeline
independently re-computes the same per-process frequency, then a SECOND
SummarizeStage with no group_by reducing that to one global row with
aggregation function="percentile" field="Frequency" percentile=5
result_alias "P5Frequency", then its own ExtendStage adding the same
constant "JoinKey" = 1; (4) back in the main pipeline, an ExtendStage
computing "IsRare" = Frequency - P5Frequency; (5) a WhereStage filtering
"IsRare <= 0". This is an advanced pattern — only reach for it when the
description genuinely needs a statistic computed over the *set of group
results themselves*, not over raw rows within one group.

Worked example — real anomaly/outlier detection over a time series (a
DGA/NXDOMAIN spike, a beaconing-interval anomaly, any "flag the outlier
period(s) compared to this entity's own recent history" request). This
is a GENUINELY DIFFERENT construct from the baseline-vs-current join
pattern above — baseline-vs-current compares ONE current period against
ONE prior average; this detects WHICH SPECIFIC time buckets, across an
entire window, are statistical outliers relative to the whole series'
own trend, which needs `make-series` + `series_decompose_anomalies`, not
a join. Description: "Flag clients with an anomalous spike in distinct
DNS queries over the last 14 days, compared to their own recent
pattern." Build it as: (1) a MakeSeriesStage with one aggregation
(function="distinct_count", field="DnsQuery", result_alias=
"DistinctQueries"), group_by=["SrcIpAddr"], from_time="ago(14d)",
to_time="now()", step="P1D" — this produces ONE row per SrcIpAddr, with
DistinctQueries as a DYNAMIC
ARRAY of 14 daily values, not a scalar; (2) a SeriesAnomalyStage with
series_field="DistinctQueries" — this is the ONLY correct way to invoke
series_decompose_anomalies; do NOT put it in an ExtendStage's expression
(it returns 3 values via destructuring assignment, which
ComputedField's single-alias shape cannot represent, and would compile
to invalid KQL); (3) an MvExpandStage with fields=["TimeGenerated",
"DistinctQueries", "AnomalyFlag", "AnomalyScore", "Baseline"] — ALL FIVE
series-valued columns together, in lockstep, to flatten one row-per-
entity-with-arrays back into one row per entity PER DAY (mv-expanding
only some of them desynchronizes the arrays); (4) a final WhereStage
filtering "AnomalyFlag != 0" (series_decompose_anomalies flags +1/-1 for
high/low outliers, 0 for normal). This is the construct that closes the
gap previously self-disclosed via `caveats` ("series decompose anomaly
detection... cannot be expressed in this IR") — it is now expressible;
reach for it whenever the description's framing is "anomalous/outlier
period(s) in this entity's own history," not "current vs. one baseline
average" (the join pattern above) or "how consistent/regular" (the
stdev/avg pattern earlier).
If MakeSeriesStage has MORE THAN ONE aggregation (e.g. computing
DistinctQueries AND a separate NXDomainCount in the same stage),
SeriesAnomalyStage.series_field must name whichever ONE of them is
actually the anomaly target per the description — and MvExpandStage's
fields list must include THAT SAME alias, not a different aggregation
from the same MakeSeriesStage just because it happens to be listed
first. Found live: a held-out case computed both DistinctQueries and
NXDomainCount, correctly ran series_decompose_anomalies on
NXDomainCount, but then mv-expanded DistinctQueries instead — leaving
NXDomainCount perpetually array-valued (never flattened) while an
unrelated, unanalyzed column got expanded alongside the anomaly flag/
score/baseline. Match the name exactly between SeriesAnomalyStage.
series_field and one entry in MvExpandStage.fields — they must be
identical, not just both present in the pipeline somewhere. Also: a
WhereStage filtering AnomalyFlag != 0 is normally the END of this
pattern — do not add a further SummarizeStage afterward unless the
description explicitly asks for additional reporting beyond the
per-bucket anomaly rows themselves.

mv-expand has a second, simpler common use, unrelated to anomaly
detection: flattening a make_set()/make_list()-aggregated array back
into one row per item, when the description wants per-item detail in
the output (e.g. "report each distinct URL touched" rather than just a
count). After a SummarizeStage with aggregation function="make_set"
field="Url" result_alias="TouchedUrls", an MvExpandStage with
fields=["TouchedUrls"] turns the one-row-per-group array back into one
row per URL — reach for this only when the description explicitly
wants the expanded, per-item rows as output, not just the aggregate
count/set; if a summary count or the set itself is all that's needed,
leave it as the make_set() column and skip mv-expand entirely.

Worked example — extracting a structured value out of an unstructured
text field (a log message, a free-text string), when no existing ASIM
field already holds it cleanly. Description: "Extract the domain name
that appears in parentheses within the connection log message, and
flag any that end in a known-malicious TLD." Use a ParseStage with
source_field="Message" (or whichever field holds the text) and exactly
five tokens, in order: a wildcard, a literal token whose value is an
opening parenthesis, a column token named "DNSName", a literal token
whose value is a closing parenthesis, then a trailing wildcard — the
two wildcard tokens mean "skip any text before/after," the two literal
tokens are the exact delimiter characters surrounding the value, and
the column token is what actually names and extracts the new field. A
row whose text doesn't match the pattern gets a null DNSName (parse
never drops rows). Filter on the extracted field in a normal, separate
WhereStage afterward (e.g. DNSName endswith ".ru"), never inside the
ParseStage itself. Use ParseStage ONLY when the value isn't already a
clean ASIM field — if the description's value already has its own
field (most ASIM-normalized content does), filter that field directly
instead of parsing text that doesn't need parsing.
"""

_BUILD_SYSTEM_PROMPT = """You are converting a structured extraction into an AST-based Security IR
KqlPipeline object that conforms exactly to the schema below. You may ONLY
use field names that appear in the provided ASIM field reference below, or
aliases you defined in an earlier summarize/extend stage of the SAME
pipeline (a stage can only see fields that exist at that point in the
pipeline — summarize drops everything except group_by keys and new
aggregation aliases; project keeps only what you list).

ASIM field reference for {likely_event_type}:
{asim_field_list}

""" + _COMMON_MISTAKES + """

{retrieved_context}

{format_instructions}

Return ONLY one JSON object that is a valid INSTANCE of this schema —
actual field values describing this specific detection, never the schema
definition itself (no "$defs", "properties", or "required" keys in your
output)."""

_REPAIR_SYSTEM_PROMPT = """Your previous IR failed validation with the following error:
{structured_validator_error}

Correct ONLY the issue described above. Do not change other parts of the
IR unless necessary to fix this specific error.

Previous IR:
{previous_ir_json}

The KQL that IR would compile to (rendered as-is, ignoring the error
above — use this to see the actual query shape, which is sometimes
easier to spot the problem in than the raw JSON):
{compiled_kql_so_far}

ASIM field reference for {likely_event_type}:
{asim_field_list}

""" + _COMMON_MISTAKES + """

{retrieved_context}

{format_instructions}

Return ONLY one corrected JSON object that is a valid INSTANCE of this
schema — actual field values, never the schema definition itself."""


def _compile_best_effort(previous_ir: Optional[KqlPipeline]) -> str:
    """generate_kql() never checks field/value validity — only structural
    shape — so it can render a KQL preview even for an IR that just
    failed semantic validation. Sometimes the rendered query makes a
    mistake obvious in a way the raw JSON doesn't (a misplaced where
    clause, a join with no real condition). Still wrapped: a previous_ir
    that's None (the last attempt didn't even parse) or some not-yet-
    anticipated malformed shape must never crash the repair attempt that's
    trying to recover from a DIFFERENT problem."""
    if previous_ir is None:
        return "(previous attempt did not parse into a valid IR — no KQL to show)"
    try:
        return generate_kql(previous_ir)
    except Exception:
        return "(could not be rendered)"


_RAG_INDEX_DIR = Path(__file__).resolve().parents[2] / "data" / "rag_indexes"

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _split_camel_case(name: str) -> str:
    """"ProcessEvent" -> "Process Event". TF-IDF's default tokenizer
    splits on word boundaries, not casing — querying the bare ASIM enum
    value against normalization-schema-process-event.md's hyphenated/
    spaced title and prose returned ZERO hits in every case (confirmed
    live before this fix): "processevent" as one token shares no
    vocabulary with "process event" as two. Schema retrieval is
    pointless without this."""
    return _CAMEL_BOUNDARY.sub(" ", name)


def _retrieved_context(extraction: ExtractionOutput) -> str:
    """Retrieves from the two routed indexes that survived §4AD's
    simplification pass (ASIM field definitions, worked NL->KQL
    examples — see src/retrieval/build_indexes.py) and renders them as
    one additional prompt section. A third index, KQL construct
    syntax/semantics (669 dataexplorer-docs operator pages), was built
    and wired in §4AB, then DROPPED here after the evidence came in:
    its own retrieval-quality spot-check was "honestly mixed" (exact-
    vocabulary queries retrieved the right page; vaguer natural-
    language queries often didn't, since TF-IDF has no real semantic
    understanding), and the full RAG A/B + independent second rater
    (§4AC) found no measurable Logic Correctness benefit to credit
    against that complexity. The ASIM-schema index, by contrast,
    measured 3/3 correct retrieval after the camelCase-query fix and is
    kept. Re-add construct retrieval if testing semantic embeddings
    instead of TF-IDF — the wash result is specific to lexical
    retrieval, not a verdict on retrieval-augmentation in general (see
    PROJECT_STATUS.md §4AD).

    Routed by need, not pooled into one index — a query for "how do I
    phrase this detection" retrieving an ASIM schema page instead of a
    worked example (or vice versa) is the actual failure mode of NOT
    separating these. Returns "" (not an error) on any missing-index/
    import problem — RAG is an additive enhancement behind an opt-in
    flag; its absence must never block the existing, measured default
    path."""
    try:
        from src.retrieval.retriever import TfidfRetriever
    except ImportError:
        return ""

    query_text = " ".join(filter(None, [
        extraction.action_description, extraction.threshold_language, extraction.time_language,
    ]))

    sections = []
    try:
        schema_query = _split_camel_case(extraction.likely_event_type)
        schema_hits = TfidfRetriever.load(str(_RAG_INDEX_DIR / "asim_schema.pkl")).query(schema_query, k=1)
        if schema_hits:
            sections.append("Relevant ASIM schema reference (official field definitions):\n" + schema_hits[0].text[:2000])
    except FileNotFoundError:
        pass

    try:
        example_hits = TfidfRetriever.load(str(_RAG_INDEX_DIR / "worked_examples.pkl")).query(query_text, k=2)
        if example_hits:
            sections.append("Similar real detections this system has built correctly before (train-split only — never the held-out/test set):\n" + "\n---\n".join(
                f"Description: {c.metadata['description']}\nKQL:\n{c.metadata['kql']}" for c in example_hits
            ))
    except FileNotFoundError:
        pass

    if not sections:
        return ""
    return "Retrieved reference material (use to ground syntax/fields/structure — the schema and worked examples above still take priority on any conflict):\n\n" + "\n\n".join(sections)


class IRBuilderAgent(BaseAgent):
    """Second of System B's two generative steps — see docs/NL-KQL/architecture.md §11.2."""

    def __init__(self, use_rag: bool = None):
        model_name = os.getenv("IR_BUILDER_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "qwen3.5:4b"))
        super().__init__(model_name=model_name)
        self.build_prompt = ChatPromptTemplate.from_messages(
            [("system", _BUILD_SYSTEM_PROMPT), ("user", "{extraction_output}")]
        )
        self.repair_prompt = ChatPromptTemplate.from_messages(
            [("system", _REPAIR_SYSTEM_PROMPT), ("user", "Correct the IR.")]
        )
        # Opt-in, off by default — RAG is an additive experiment being
        # A/B-measured against the existing, already-measured default
        # path (PROJECT_STATUS.md §4AB), not a replacement shipped
        # unconditionally. use_rag=None (the default) reads
        # USE_RAG_RETRIEVAL from the environment so eval scripts can
        # toggle it without code changes; an explicit True/False
        # argument always overrides the environment.
        self.use_rag = use_rag if use_rag is not None else os.getenv("USE_RAG_RETRIEVAL", "0") == "1"

    def build(
        self,
        extraction: ExtractionOutput,
        asim_field_list: list[str],
        repair_error: Optional[ValidationResult] = None,
        previous_ir: Optional[KqlPipeline] = None,
        temperature_override: Optional[float] = None,
    ) -> KqlPipeline:
        llm_backup = None
        if temperature_override is not None and temperature_override != self.temperature:
            llm_backup = self.llm
            self.llm = build_chat_model(self.model_name, temperature_override)

        retrieved_context = _retrieved_context(extraction) if self.use_rag else ""

        try:
            if repair_error is None:
                return self._invoke(
                    prompt=self.build_prompt,
                    pydantic_schema=KqlPipeline,
                    input_data={
                        "likely_event_type": extraction.likely_event_type,
                        "asim_field_list": json.dumps(asim_field_list),
                        "extraction_output": extraction.model_dump_json(),
                        "label_vs_data_section": _label_vs_data_section(),
                        "retrieved_context": retrieved_context,
                    },
                )

            return self._invoke(
                prompt=self.repair_prompt,
                pydantic_schema=KqlPipeline,
                input_data={
                    "structured_validator_error": repair_error.message,
                    "previous_ir_json": previous_ir.model_dump_json() if previous_ir else "{}",
                    "compiled_kql_so_far": _compile_best_effort(previous_ir),
                    "likely_event_type": extraction.likely_event_type,
                    "asim_field_list": json.dumps(asim_field_list),
                    "label_vs_data_section": _label_vs_data_section(),
                    "retrieved_context": retrieved_context,
                },
            )
        finally:
            if llm_backup is not None:
                self.llm = llm_backup
