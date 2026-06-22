"""Few-shot examples for the System A baseline prompt.

DRAFT — sourced from real (NL, KQL) pairs in data/raw/detections_raw.jsonl
(Azure-Sentinel repo, commit 012a82a2, see data/raw/SOURCE_ATTRIBUTION.md),
lightly trimmed for prompt length. Not yet manually verified against the
dataset construction rubric (docs/NL-KQL/MASTER_PLAN.md §16.2 Step 4) — review
before locking these into the frozen System A prompt for evaluation.
"""

FEW_SHOT_EXAMPLE_1 = {
    "nl_description": (
        "This query searches for failed attempts to log in from more than 15 "
        "various users within a 5 minute timeframe from the same source. This "
        "is a potential indication of a password spray attack."
    ),
    "kql": (
        "let FailureThreshold = 15;\n"
        "imAuthentication\n"
        "| where EventType == 'Logon' and EventResult == 'Failure'\n"
        "| where EventResultDetails in ('No such user or password', 'Incorrect password')\n"
        "| summarize UserCount=dcount(TargetUserId), Vendors=make_set(EventVendor), Products=make_set(EventVendor)\n"
        "    , Users = make_set(TargetUserId,100)\n"
        "    by SrcDvcIpAddr, SrcGeoCountry, bin(TimeGenerated, 5m)\n"
        "| where UserCount > FailureThreshold"
    ),
    "source_file": "Detections/ASimAuthentication/imAuthPasswordSpray.yaml",
}

FEW_SHOT_EXAMPLE_2 = {
    "nl_description": (
        "This creates an incident in the event a client generates excessive "
        "amounts of DNS queries for non-existent domains."
    ),
    "kql": (
        "let threshold = 200;\n"
        "_Im_Dns(responsecodename='NXDOMAIN')\n"
        "| where isnotempty(DnsResponseCodeName)\n"
        "| summarize count() by SrcIpAddr, bin(TimeGenerated,15m)\n"
        "| where count_ > threshold\n"
        "| join kind=inner (_Im_Dns(responsecodename='NXDOMAIN')\n"
        "    ) on SrcIpAddr"
    ),
    "source_file": "Detections/ASimDNS/imDns_ExcessiveNXDOMAINDNSQueries.yaml",
}
