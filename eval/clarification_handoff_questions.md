# Clarification handoff: questions across real, fresh held-out cases

Answer blind -- without looking at ground_truth_kql in eval/clarification_eval_set.json or
eval/results/clarification_eval_raw.json for these rule_ids. Fill answers into the
human_answer field of the matching gap in eval/results/clarification_eval_raw.json, then run
python eval/run_clarification_eval.py --resolve

## 1. 27f1a570-5f20-496b-88f6-a9aa2c5c9534 (simple)

> This rule identifies allowed inbound SSH, Telnet, and RDP connections. This analytic rule leverages the SonicWall Firewall ASIM Network Session parser (ASimNetworkSessionSonicWallFirewall).

- Q: The description didn't specify a concrete value for DstPortNumber — what should it be? (No concrete port numbers were given for the destination port filter, so no filter on DstPortNumber was added.)

## 2. 73c803aa-1188-45dd-8379-62a3319d3d9f (simple)

> The query identifies incident-level events received from the GravityZone Data Connector

- Q: The description didn't specify a concrete value — what should it be? (no concrete filters were given for event type or actor details in the description)

## 3. 6e575295-a7e6-464c-8192-3e1d8fd6a990 (moderate)

> Identifies a match across various data feeds for IP IOCs related to the Log4j vulnerability exploit aka Log4Shell described in CVE-2021-44228.
 References: https://cve.mitre.org/cgi-bin/cvename.cgi?name=2021-44228

- Q: The description didn't specify a concrete value for SrcIpAddr — what should it be? (no concrete IoC values were given for the source IP check, so no filter on SrcIpAddr was added)
- Q: The description didn't specify a concrete value for DstIpAddr — what should it be? (no concrete IoC values were given for the destination IP check, so no filter on DstIpAddr was added)

## 4. cd8faa84-4464-4b4e-96dc-b22f50c27541 (moderate)

> This detection rule detects scenarios when a particular port is being scanned by multiple external sources. The rule utilize [ASIM](https://aka.ms/AboutASIM) normalization, and is applied to any source which supports the ASIM Network Session schema.

- Q: What threshold/count should trigger this detection?
- Q: The description didn't specify a concrete value — what should it be? (no filter was added to restrict to only external sources because no definition or list of external IPs was provided.)

## 5. 3f0c20d5-6228-48ef-92f3-9ff7822c1954 (moderate)

> This rule identifies a web request with a user agent header known to belong to a hacking tool. This indicates a hacking tool is used on the host.<br>You can add custom hacking tool indicating User-Agent headers using a watchlist, for more information refer to the [UnusualUserAgents Watchlist](https://aka.ms/ASimUnusualUserAgentsWatchlist).
 This analytic rule uses [ASIM](https://aka.ms/AboutASIM) and supports any built-in or custom source that supports the ASIM WebSession schema (ASIM WebSession Schema)

- Q: The description didn't specify a concrete value for UserAgent — what should it be? (no concrete User-Agent values were given for the UserAgent check, so no filter on UserAgent was added)

## 6. 42436753-9944-4d70-801c-daaa4d19ddd2 (moderate)

> This rule identifies a web request with a user agent header known to belong PowerShell. <br>You can add custom Powershell indicating User-Agent headers using a watchlist, for more information refer to the [UnusualUserAgents Watchlist](https://aka.ms/ASimUnusualUserAgentsWatchlist).<br><br>
 This analytic rule uses [ASIM](https://aka.ms/AboutASIM) and supports any built-in or custom source that supports the ASIM WebSession schema (ASIM WebSession Schema)

- Q: The description didn't specify a concrete value for UserAgent — what should it be? (no concrete UserAgent values were given for the known PowerShell User-Agent strings, so no filter on UserAgent was added)

## 7. 01e8ffff-dc0c-43fe-aa22-d459c4204553 (moderate)

> Identifies callouts to Discord CDN addresses for risky file extensions. This detection will trigger when a callout for a risky file is made to a discord server that has only been seen once in your environment. 
 Unique discord servers are identified using the server ID that is included in the request URL (DiscordServerId in query). Discord CDN has been used in multiple campaigns to download additional payloads.
 This analytic rule uses [ASIM](https://aka.ms/AboutASIM) and supports any built-in or custom source that supports the ASIM WebSession schema (ASIM WebSession Schema)

- Q: The description didn't specify a concrete value — what should it be? (DiscordServerId is not a standard ASIM field; used Url as proxy for Discord server identification.)
- Q: The description didn't specify a concrete value — what should it be? (FileExtension is not a standard ASIM field; used Url endswith checks for risky file extensions.)

## 8. b1832f60-6c3d-4722-a0a5-3d564ee61a63 (complex)

> This rule identifies Web Sessions for which the target URL hostname is a known IoC. This rule uses the [Advanced Security Information Model (ASIM)](https:/aka.ms/AboutASIM) and supports any web session source that complies with ASIM.

- Q: The description didn't specify a concrete value for DstHostname — what should it be? (no concrete IoC values were given for the UrlHostname check, so no filter on DstHostname was added)

## 9. cbf07406-fa2a-48b0-82b8-efad58db14ec (complex)

> This rule detects anomalous pattern in port usage. The rule utilize [ASIM](https://aka.ms/AboutASIM) normalization, and is applied to any source which supports the ASIM Network Session schema. To tune the rule to your environment configure it using the 'NetworkSession_Monitor_Configuration' watchlist. This rule leverages log summaries generated by a Summary Rule or Summarized Playbook. If no such summaries are available, the rule falls back to direct analysis using ASIM function.

- Q: What threshold/count should trigger this detection?
- Q: What threshold/count should trigger this detection?

## 10. 6bfea14f-2122-46b3-8f8b-3947e0fb6d92 (complex)

> This query hunts for command line activity linked to Dev-0322's compromise of ZOHO ManageEngine ADSelfService Plus software. It focuses on commands used in post-exploitation activity. Hosts with higher risk scores should be prioritized.

- Q: What threshold/count should trigger this detection?
- Q: What threshold/count should trigger this detection?
- Q: The description didn't specify a concrete value — what should it be? (The actor name 'Dev-0322' is an attribution label, not literal log content, so it was omitted.)

## 11. 9d8b5a18-b7db-4c23-84a6-95febaf7e1e4 (complex)

> Identifies a match across various data feeds for  hashes and IP IOC related to Europium
 Reference: https://www.microsoft.com/security/blog/2022/09/08/microsoft-investigates-iranian-attacks-against-the-albanian-government

- Q: The description didn't specify a concrete value for DstIpAddr — what should it be? (no concrete IoC values were given for the source IP check, so no filter on DstIpAddr was added)
- Q: The description didn't specify a concrete value — what should it be? (no concrete IoC values were given for the hash check, so no filter on hash fields was added)

## 12. dbc2438a-0d16-4890-aaae-cbe0dc433b08 (complex)

> Recorded Future  URL  Threat Actor Hunt.

- Q: The description didn't specify a concrete value for Url — what should it be? (no concrete IoC values were given for the URL or threat actor details, so no filter on Url or related fields was added)

## 13. 906c20c6-b62c-4af7-be91-d7300e3bded2 (complex)

> This hunting query detect anomalous pattern in port usage with ASIM normalization. To tune the query to your environment configure it using the 'NetworkSession_Monitor_Configuration' watchlist.

- Q: What threshold/count should trigger this detection?
- Q: The description didn't specify a concrete value — what should it be? (the detection references an external watchlist 'NetworkSession_Monitor_Configuration' for tuning, but no concrete values were provided to implement)

## 14. d9e1646c-dc17-4150-ac85-581f5c9cb41f (complex)

> Google Threat Intelligence domain correlation.

- Q: The description didn't specify a concrete value for Domain — what should it be? (no concrete IoC values were given for the threat intelligence domain data, so no filter on Domain or DnsResponseName was added)

## 15. 999e9f5d-db4a-4b07-a206-29c4e667b7e8 (complex)

> Identifies a match in DNS events from any Domain IOC from TI
This analytic rule uses [ASIM](https://aka.ms/AboutASIM) and supports any built-in or custom source that supports the ASIM DNS schema

- Q: The description didn't specify a concrete value for DnsQuery — what should it be? (no concrete IoC values were given for the domain indicator of compromise check, so no filter on DnsQuery or DnsResponseName was added)

## 16. ae10c588-7ff7-486c-9920-ab8b0bdb6ede (complex)

> Identifies a match across various data feeds for domains, hashes and IP IOC related to Mercury
 Reference:  https://www.microsoft.com/security/blog/2022/08/25/mercury-leveraging-log4j-2-vulnerabilities-in-unpatched-systems-to-target-israeli-organizations/

- Q: The description didn't specify a concrete value for DstDomain — what should it be? (no concrete IOC values were given for the domain, hash, or IP checks, so no filters on DstDomain, File.Hash, or DstIpAddr were added)

## 17. 156997bd-da0f-4729-b47a-0a3e02dd50c8 (complex)

> This detection rule detects port usage above the configured threshold. The rule utilize [ASIM](https://aka.ms/AboutASIM) normalization, and is applied to any source which supports the ASIM Network Session schema. To tune the rule to your environment configure it using the 'NetworkSession_Monitor_Configuration' watchlist. This rule leverages log summaries generated by a Summary Rule or Summarized Playbook. If no such summaries are available, the rule falls back to direct analysis using ASIM function.

- Q: What threshold/count should trigger this detection?
- Q: What threshold/count should trigger this detection?

## 18. 34288e97-5194-4f2e-abf2-c2783189f6ae (complex)

> Google Threat Intelligence domain correlation.

- Q: The description didn't specify a concrete value — what should it be? (no concrete IoC values were given for the threat intelligence domain data, so no filter on the joined domain data was added)

## 19. 7edb2abb-7ef7-4685-92eb-a628703ccf9f (complex)

> Google Threat Intelligence IP correlation.

- Q: The description didn't specify a concrete value for SrcIpAddr — what should it be? (no concrete IoC values were given for the source IP check, so no filter on SrcIpAddr was added)
- Q: The description didn't specify a concrete value for DstIpAddr — what should it be? (no concrete IoC values were given for the destination IP check, so no filter on DstIpAddr was added)

## 20. ee1fd303-2081-47b7-8f02-e38bfd0868e6 (complex)

> ThreatConnect Specific:
This rule identifies a match Network Sessions for which the source or destination IP address is a known IoC.
This analytic rule uses [ASIM](https://aka.ms/AboutASIM) and supports any built-in or custom source that supports the ASIM NetworkSession schema

- Q: The description didn't specify a concrete value for SrcIpAddr — what should it be? (no concrete IoC values were given for the source or destination IP check, so no filter on SrcIpAddr or DstIpAddr was added)

## 21. a1705fa5-c904-4f1b-9e2d-a4ccb30377a2 (complex)

> Google Threat Intelligence Url correlation.

- Q: The description didn't specify a concrete value for Url — what should it be? (no concrete IoC values were given for the URL check, so no filter on Url was added)

## 22. 7b5eb44d-3533-440e-9774-73a4d99bc2b2 (complex)

> Recorded Future Threat Hunting IP correlation for all actors.

- Q: The description didn't specify a concrete value for SrcIpAddr — what should it be? (no concrete IoC values were given for the source IP check, so no filter on SrcIpAddr was added)
- Q: The description didn't specify a concrete value for DstIpAddr — what should it be? (no concrete IoC values were given for the destination IP check, so no filter on DstIpAddr was added)
- Q: The description didn't specify a concrete value for SrcUsername — what should it be? (no concrete actor values were given for ActorUsername or ActorHostname, so no filters on SrcUsername or SrcHostname were added)

## 23. 905da21a-c7d2-4f5b-b8fc-c8321da3ee83 (complex)

> Recorded Future Threat Hunting hash correlation for all actors.

- Q: The description didn't specify a concrete value for FileHash — what should it be? (no concrete IoC values were given for the hash correlation, so no filter on FileHash was added)

## 24. 074ce265-f684-41cd-af07-613c5f3e6d0d (complex)

> Matches domain name IOCs related to Forest Blizzard group activity published July 2019 with CommonSecurityLog, DnsEvents and VMConnection dataTypes.
References: https://blogs.microsoft.com/on-the-issues/2019/07/17/new-cyberthreats-require-new-ways-to-protect-democracy/.

- Q: The description didn't specify a concrete value for Domain — what should it be? (no concrete IOC values were given for the domain name check, so no filter on Domain was added)

## 25. 89290690-54c4-4196-91c5-d32b1df5d873 (complex)

> Google Threat Intelligence Url correlation.

- Q: The description didn't specify a concrete value for Url — what should it be? (no concrete IoC values were given for the URL threat intelligence feed, so no filter on Url was added)

## 26. faa83502-2763-49ae-9216-e576fa1fdccb (complex)

> Google Threat Intelligence IP correlation.

- Q: The description didn't specify a concrete value for SrcIpAddr — what should it be? (no concrete IoC values were given for the source IP check, so no filter on SrcIpAddr was added)
- Q: The description didn't specify a concrete value for DstIpAddr — what should it be? (no concrete IoC values were given for the destination IP check, so no filter on DstIpAddr was added)

## 27. bca9c877-2afc-4246-a26d-087ab1cdcd5f (complex)

> This query looks for file hashes and AV signatures associated with Prestige ransomware payload.

- Q: The description didn't specify a concrete value for Hash — what should it be? (no concrete file hash or antivirus signature values were given for filtering, so no filter on Hash or AVSignature was added)

## 28. acbf7ef6-f964-44c3-9031-7834ec68175f (complex)

> Recorded Future Threat Hunting domain correlation for all actors.

- Q: The description didn't specify a concrete value for DnsQuery — what should it be? (no concrete IoC values were given for the domain correlation check, so no filter on DnsQuery or DnsResponseName was added)

## 29. a924d317-03d2-4420-a71f-4d347bda4bd8 (complex)

> Detects a match in Workday activity from any IP Indicator of Compromise (IOC) provided by Threat Intelligence (TI).

- Q: The description didn't specify a concrete value for SrcIpAddr — what should it be? (no concrete IoC values were given for the source IP check, so no filter on SrcIpAddr was added)

## 30. 29a29e5d-354e-4f5e-8321-8b39d25047bf (complex)

> This hunting query looks for file paths/hashes related to observed activity by Dev-0228. The actor is known to use custom version of popular tool like PsExec, Procdump etc. to carry its activity.
 The risk score associated with each result is based on a number of factors, hosts with higher risk events should be investigated first.
 This query uses the Microsoft Sentinel Information Model - https://docs.microsoft.com/azure/sentinel/normalization

- Q: The description didn't specify a concrete value for FilePath — what should it be? (No concrete file paths or hashes were given for actor Dev-0228's activity, so no filters on FilePath or FileHash were added.)

## 31. 6db6a8e6-2959-440b-ba57-a505875fcb37 (complex)

> Recorded Future Threat Hunting hash correlation for all actors.

- Q: The description didn't specify a concrete value for Hash — what should it be? (no concrete IoC values were given for the hash correlation, so no filter on Hash was added)

## 32. 536e8e5c-ce0e-575e-bcc9-aba8e7bf9316 (complex)

> This rule identifies a match Network Sessions for which the source or destination IP address is a known GreyNoise IoC.
This analytic rule uses [ASIM](https://aka.ms/AboutASIM) and supports any built-in or custom source that supports the ASIM NetworkSession schema

- Q: The description didn't specify a concrete value for SrcIpAddr — what should it be? (no concrete IoC values were given for the source or destination IP check, so no filter on SrcIpAddr or DstIpAddr was added)

## 33. 9176b18f-a946-42c6-a2f6-0f6d17cd6a8a (complex)

> This rule identifies communication with hosts that have a domain name that might have been generated by a Domain Generation Algorithm (DGA).
DGAs are used by malware to generate rendezvous points that are difficult to predict in advance. This detection uses the top 1 million domain names to build a model of what normal domains look like nad uses the model to identify domains that may have been randomly generated by an algorithm. You can modify the triThreshold and dgaLengthThreshold query parameters to change Analytic Rule sensitivity. The higher the numbers, the less noisy the rule is.
 This analytic rule uses [ASIM](https://aka.ms/AboutASIM) and supports any built-in or custom source that supports the ASIM WebSession schema (ASIM WebSession Schema)

- Q: What threshold/count should trigger this detection?

## 34. 0051a0d9-684f-4317-abbd-c1e5c24b39cb (complex)

> Google Threat Intelligence hash correlation.

- Q: The description didn't specify a concrete value for Hash — what should it be? (no concrete IoC values were given for the file hash check, so no filter on Hash was added)

## 35. 92e8e945-6e99-4e4b-bef8-468b4c19fc3a (complex)

> Detects a match in Workday activity from any IP Indicator of Compromise (IOC) provided by Threat Intelligence (TI).

- Q: The description didn't specify a concrete value for SrcIpAddr — what should it be? (no concrete IoC values were given for the source IP check, so no filter on SrcIpAddr was added)

## 36. ce74dc9a-cb3c-4081-8c2f-7d39f6b7bae1 (complex)

> The query below identifies powershell commands used by the threat actor Mango Sandstorm.
Reference:  https://www.microsoft.com/security/blog/2022/08/25/mercury-leveraging-log4j-2-vulnerabilities-in-unpatched-systems-to-target-israeli-organizations/

- Q: The description didn't specify a concrete value — what should it be? (The actor name 'Mango Sandstorm' is an attribution label, not literal log content; no concrete actor-related filter was added.)

## 37. 8f9cd0e5-b4ab-4821-95e2-1082fcd784c7 (complex)

> Google Threat Intelligence hash correlation.

- Q: The description didn't specify a concrete value for Hash — what should it be? (no concrete IoC values were given for the file hash check, so no filter on Hash was added)

## 38. cd6def0d-3ef0-4d55-a7e3-faa96c46ba12 (complex)

> The rule identifies anomalous pattern in network session traffic based on previously seen data, different Device Action, Network Protocol, Network Direction or overall volume. The rule utilize [ASIM](https://aka.ms/AboutASIM) normalization, and is applied to any source which supports the ASIM Network Session schema. This rule leverages log summaries generated by a Summary Rule or Summarized Playbook. If no such summaries are available, the rule falls back to direct analysis using ASIM function.

- Q: What threshold/count should trigger this detection?

## 39. b7fe8f27-7010-404b-aec5-6e5245cea580 (complex)

> This detection mechanism identifies instances where requests are made to Discord CDN addresses for file extensions that are considered risky.
  It triggers when a callout is made to a Discord server that has only been encountered once in your environment. The uniqueness of Discord servers is determined based on the server ID present in the request URL (DiscordServerId in the query).
  Discord CDN has been utilized in numerous campaigns to download additional payloads, highlighting the importance of monitoring such activities.
  The query includes a sample set of popular web script extensions (scriptExtensions), which should be customized to align with the specific requirements of your environment

- Q: The description didn't specify a concrete value — what should it be? (DiscordServerId is not a standard ASIM field; assumed to be extracted or aliased from Url or AdditionalFields.)
- Q: The description didn't specify a concrete value — what should it be? (No concrete list of risky file extensions was given; used common script extensions from candidate_fields.)

## 40. 4bd7e93a-0646-4e02-8dcb-aa16d16618f4 (complex)

> Identifies a chain of events, where a new Power App is created, followed by mulitple users launching the app within the detection window and clicking on the same malicious URL.

- Q: What time window should this detection use? (default: 1 hour — the most common in this project's own ground-truth corpus) (suggested default: PT1H)
- Q: The description didn't specify a concrete value — what should it be? (No concrete malicious URL list or flag field was given; assumed Url field is already flagged as malicious.)
