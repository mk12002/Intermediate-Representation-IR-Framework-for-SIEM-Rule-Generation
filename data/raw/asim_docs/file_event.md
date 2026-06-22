### Target file fields
| Field | Class |
| --- | --- |
| **TargetFileCreationTime** | Optional |
| **TargetFileDirectory** | Optional |
| **TargetFileExtension** | Optional |
| **TargetFileMimeType** | Optional |
| **TargetFileName** | Recommended |
| **FileName** | Alias |
| **TargetFilePath** | Mandatory |
| **TargetFilePathType** | Mandatory |
| **FilePath** | Alias |
| **TargetFileMD5** | Optional |
| **TargetFileSHA1** | Optional |
| **TargetFileSHA256** | Optional |
| **TargetFileSHA512** | Optional |
| **Hash** | Alias |
| **HashType** | Conditional |
| **TargetFileSize** | Optional |

### Source file fields
| Field | Class |
| --- | --- |
| **SrcFileCreationTime** | Optional |
| **SrcFileDirectory** | Optional |
| **SrcFileExtension** | Optional |
| **SrcFileMimeType** | Optional |
| **SrcFileName** | Recommended |
| **SrcFilePath** | Recommended |
| **SrcFilePathType** | Recommended |
| **SrcFileMD5** | Optional |
| **SrcFileSHA1** | Optional |
| **SrcFileSHA256** | Optional |
| **SrcFileSHA512** | Optional |
| **SrcFileSize** | Optional |

### Actor fields
| Field | Class |
| --- | --- |
| **ActorUserId** | Recommended |
| **ActorScope** | Optional |
| **ActorScopeId** | Optional |
| **ActorUserIdType** | Conditional |
| **ActorUsername** | Mandatory |
| **User** | Alias |
| **ActorUsernameType** | Conditional |
| **ActorSessionId** | Optional |
| **ActorUserType** | Optional |
| **ActorOriginalUserType** | Optional |

### Acting process fields
| Field | Class |
| --- | --- |
| **ActingProcessCommandLine** | Optional |
| **ActingProcessName** | Optional |
| **Process** | Alias |
| **ActingProcessId** | Optional |
| **ActingProcessGuid** | Optional |

### Source system related fields
| Field | Class |
| --- | --- |
| **SrcIpAddr** | Recommended |
| **IpAddr** | Alias |
| **Src** | Alias |
| **SrcPortNumber** | Optional |
| **SrcHostname** | Optional |
| **SrcDomain** | Optional |
| **SrcDomainType** | Conditional |
| **SrcFQDN** | Optional |
| **SrcDescription** | Optional |
| **SrcDvcId** | Optional |
| **SrcDvcScopeId** | Optional |
| **SrcDvcScope** | Optional |
| **SrcDvcIdType** | Conditional |
| **SrcDeviceType** | Optional |
| **SrcGeoCountry** | Optional |
| **SrcGeoRegion** | Optional |
| **SrcGeoCity** | Optional |
| **SrcGeoLatitude** | Optional |
| **SrcGeoLongitude** | Optional |

### Acting application fields
| Field | Class |
| --- | --- |
| **ActingAppName** | Optional |
| **ActingAppId** | Optional |
| **ActingAppType** | Optional |
| **HttpUserAgent** | Optional |
| **NetworkApplicationProtocol** | Optional |

### Target application fields
| Field | Class |
| --- | --- |
| **TargetAppName** | Optional |
| **Application** | Alias |
| **TargetAppId** | Optional |
| **TargetAppType** | Conditional |
| **TargetOriginalAppType** | Optional |
| **TargetUrl** | Optional |
| **Url** | Alias |

### Inspection fields
| Field | Class |
| --- | --- |
| **RuleName** | Optional |
| **RuleNumber** | Optional |
| **Rule** | Conditional |
| **ThreatId** | Optional |
| **ThreatName** | Optional |
| **ThreatCategory** | Optional |
| **ThreatRiskLevel** | Optional |
| **ThreatOriginalRiskLevel** | Optional |
| **ThreatFilePath** | Optional |
| **ThreatField** | Conditional |
| **ThreatConfidence** | Optional |
| **ThreatOriginalConfidence** | Optional |
| **ThreatIsActive** | Optional |
| **ThreatFirstReportedTime** | Optional |
| **ThreatLastReportedTime** | Optional |
