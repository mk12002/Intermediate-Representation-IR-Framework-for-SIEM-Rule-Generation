### Authentication-specific fields
| Field | Class |
| --- | --- |
| **LogonMethod** | Optional |
| **LogonProtocol** | Optional |

### Actor fields
| Field | Class |
| --- | --- |
| **ActorUserId** | Optional |
| **ActorScope** | Optional |
| **ActorScopeId** | Optional |
| **ActorUserIdType** | Conditional |
| **ActorUsername** | Optional |
| **ActorUsernameType** | Conditional |
| **ActorUserType** | Optional |
| **ActorOriginalUserType** | Optional |
| **ActorSessionId** | Optional |

### Acting Application fields
| Field | Class |
| --- | --- |
| **ActingAppId** | Optional |
| **ActingAppName** | Optional |
| **ActingAppType** | Optional |
| **ActingOriginalAppType** | Optional |
| **HttpUserAgent** | Optional |

### Target user fields
| Field | Class |
| --- | --- |
| **TargetUserId** | Optional |
| **TargetUserScope** | Optional |
| **TargetUserScopeId** | Optional |
| **TargetUserIdType** | Conditional |
| **TargetUsername** | Optional |
| **TargetUsernameType** | Conditional |
| **TargetUserType** | Optional |
| **TargetSessionId** | Optional |
| **TargetOriginalUserType** | Optional |
| **User** | Alias |

### Source system fields
| Field | Class |
| --- | --- |
| **Src** | Recommended |
| **SrcDvcId** | Optional |
| **SrcDvcScopeId** | Optional |
| **SrcDvcScope** | Optional |
| **SrcDvcIdType** | Conditional |
| **SrcDeviceType** | Optional |
| **SrcHostname** | Optional |
| **SrcDomain** | Optional |
| **SrcDomainType** | Conditional |
| **SrcFQDN** | Optional |
| **SrcDescription** | Optional |
| **SrcIpAddr** | Recommended |
| **SrcPortNumber** | Optional |
| **SrcDvcOs** | Optional |
| **IpAddr** | Alias |
| **SrcIsp** | Optional |
| **SrcGeoCountry** | Optional |
| **SrcGeoCity** | Optional |
| **SrcGeoRegion** | Optional |
| **SrcGeoLongitude** | Optional |
| **SrcGeoLatitude** | Optional |
| **SrcRiskLevel** | Optional |
| **SrcOriginalRiskLevel** | Optional |

### Target application fields
| Field | Class |
| --- | --- |
| **TargetAppId** | Optional |
| **TargetAppName** | Optional |
| **Application** | Alias |
| **TargetAppType** | Conditional |
| **TargetOriginalAppType** | Optional |
| **TargetUrl** | Optional |
| **LogonTarget** | Alias |

### Target system fields
| Field | Class |
| --- | --- |
| **Dst** | Alias |
| **TargetHostname** | Recommended |
| **TargetDomain** | Recommended |
| **TargetDomainType** | Conditional |
| **TargetFQDN** | Optional |
| **TargetDescription** | Optional |
| **TargetDvcId** | Optional |
| **TargetDvcScopeId** | Optional |
| **TargetDvcScope** | Optional |
| **TargetDvcIdType** | Conditional |
| **TargetDeviceType** | Optional |
| **TargetIpAddr** | Optional |
| **TargetDvcOs** | Optional |
| **TargetPortNumber** | Optional |
| **TargetGeoCountry** | Optional |
| **TargetGeoRegion** | Optional |
| **TargetGeoCity** | Optional |
| **TargetGeoLatitude** | Optional |
| **TargetGeoLongitude** | Optional |
| **TargetRiskLevel** | Optional |
| **TargetOriginalRiskLevel** | Optional |

### Inspection fields
| Field | Class |
| --- | --- |
| **RuleName** | Optional |
| **RuleNumber** | Optional |
| **Rule** | Alias |
| **ThreatId** | Optional |
| **ThreatName** | Optional |
| **ThreatCategory** | Optional |
| **ThreatRiskLevel** | Optional |
| **ThreatOriginalRiskLevel** | Optional |
| **ThreatConfidence** | Optional |
| **ThreatOriginalConfidence** | Optional |
| **ThreatIsActive** | Optional |
| **ThreatFirstReportedTime** | Optional |
| **ThreatLastReportedTime** | Optional |
| **ThreatIpAddr** | Optional |
| **ThreatField** | Conditional |
