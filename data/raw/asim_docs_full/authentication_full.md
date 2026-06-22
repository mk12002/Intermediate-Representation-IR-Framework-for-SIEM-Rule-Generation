### Common fields with specific guidelines
| Field | Class |
| --- | --- |
| **EventType** | Mandatory |
| **EventResultDetails** | Recommended |
| **EventSubType** | Optional |
| **EventSchemaVersion** | Mandatory |
| **EventSchema** | Mandatory |

### Authentication-specific fields
| Field | Class | Type | Description |
| --- | --- | --- | --- |
| **LogonMethod** | Optional | String | The method used to perform authentication. |
| **LogonProtocol** | Optional | String | The protocol used to perform authentication. |

### Actor fields
| Field | Class | Type | Description |
| --- | --- | --- | --- |
| **ActorUserId** | Optional | String | A machine-readable, alphanumeric, unique representation of the Actor. |
| **ActorScope** | Optional | String | The scope, such as Microsoft Entra tenant. |
| **ActorScopeId** | Optional | String | The scope ID. |
| **ActorUserIdType** | Conditional | UserIdType | The type of the ID stored in the ActorUserId field. |
| **ActorUsername** | Optional | Username (String) | The Actor's username. |
| **ActorUsernameType** | Conditional | UsernameType | Specifies the type of the user name. |
| **ActorUserType** | Optional | UserType | The type of the Actor. |
| **ActorOriginalUserType** | Optional | String | The user type as reported by the reporting device. |
| **ActorSessionId** | Optional | String | The unique ID of the sign-in session of the Actor. |

### Acting Application fields
| Field | Class | Type | Description |
| --- | --- | --- | --- |
| **ActingAppId** | Optional | String | The ID of the application authorizing on behalf of the actor. |
| **ActingAppName** | Optional | String | The name of the application authorizing on behalf of the actor. |
| **ActingAppType** | Optional | AppType | The type of acting application. |
| **ActingOriginalAppType** | Optional | String | The type of the acting application as reported by the reporting device. |
| **HttpUserAgent** | Optional | String | When authentication is performed over HTTP or HTTPS. |

### Target user fields
| Field | Class | Type | Description |
| --- | --- | --- | --- |
| **TargetUserId** | Optional | String | A machine-readable, alphanumeric, unique representation of the target user. |
| **TargetUserScope** | Optional | String | The scope, such as Microsoft Entra tenant. |
| **TargetUserScopeId** | Optional | String | The scope ID. |
| **TargetUserIdType** | Conditional | UserIdType | The type of the user ID stored in the TargetUserId field. |
| **TargetUsername** | Optional | Username (String) | The target user username. |
| **TargetUsernameType** | Conditional | UsernameType | Specifies the type of the username stored in the TargetUsername field. |
| **TargetUserType** | Optional | UserType | The type of the Target user. |
| **TargetSessionId** | Optional | String | The sign-in session identifier of the TargetUser. |
| **TargetOriginalUserType** | Optional | String | The user type as reported by the reporting device. |
| **User** | Alias | Username (String) | Alias to the TargetUsername or to the TargetUserId. |

### Source system fields
| Field | Class | Type | Description |
| --- | --- | --- | --- |
| **Src** | Recommended | String | A unique identifier of the source device. |
| **SrcDvcId** | Optional | String | The ID of the source device. |
| **SrcDvcScopeId** | Optional | String | The cloud platform scope ID. |
| **SrcDvcScope** | Optional | String | The cloud platform scope. |
| **SrcDvcIdType** | Conditional | DvcIdType | The type of SrcDvcId. |
| **SrcDeviceType** | Optional | DeviceType | The type of the source device. |
| **SrcHostname** | Optional | Hostname | The source device hostname. |
| **SrcDomain** | Optional | Domain (String) | The domain of the source device. |
| **SrcDomainType** | Conditional | DomainType | The type of SrcDomain. |
| **SrcFQDN** | Optional | FQDN (String) | The source device hostname, including domain. |
| **SrcDescription** | Optional | String | A descriptive text associated with the device. |
| **SrcIpAddr** | Recommended | IP Address | The IP address of the source device. |
| **SrcPortNumber** | Optional | Integer | The IP port from which the connection originated. |
| **SrcDvcOs** | Optional | String | The OS of the source device. |
| **IpAddr** | Alias |  | Alias to SrcIpAddr |
| **SrcIsp** | Optional | String | The Internet Service Provider used by the source device. |
| **SrcGeoCountry** | Optional | Country | Source country. |
| **SrcGeoCity** | Optional | City | Source city. |
| **SrcGeoRegion** | Optional | Region | Source region. |
| **SrcGeoLongitude** | Optional | Longitude | Source longitude. |
| **SrcGeoLatitude** | Optional | Latitude | Source latitude. |
| **SrcRiskLevel** | Optional | Integer | The risk level associated with the source. |
| **SrcOriginalRiskLevel** | Optional | String | The risk level as reported by the reporting device. |

### Target application fields
| Field | Class | Type | Description |
| --- | --- | --- | --- |
| **TargetAppId** | Optional | String | The ID of the application to which the authorization is required. |
| **TargetAppName** | Optional | String | The name of the application to which the authorization is required. |
| **Application** | Alias |  | Alias to TargetAppName. |
| **TargetAppType** | Conditional | AppType | The type of the application authorizing on behalf of the Actor. |
| **TargetOriginalAppType** | Optional | String | The type of the application as reported by the reporting device. |
| **TargetUrl** | Optional | URL | The URL associated with the target application. |
| **LogonTarget** | Alias |  | Alias to either TargetAppName, TargetUrl, or TargetHostname. |

### Target system fields
| Field | Class | Type | Description |
| --- | --- | --- | --- |
| **Dst** | Alias | String | A unique identifier of the authentication target. |
| **TargetHostname** | Recommended | Hostname | The target device hostname. |
| **TargetDomain** | Recommended | Domain (String) | The domain of the target device. |
| **TargetDomainType** | Conditional | Enumerated | The type of TargetDomain. |
| **TargetFQDN** | Optional | FQDN (String) | The target device hostname, including domain. |
| **TargetDescription** | Optional | String | A descriptive text associated with the device. |
| **TargetDvcId** | Optional | String | The ID of the target device. |
| **TargetDvcScopeId** | Optional | String | The cloud platform scope ID. |
| **TargetDvcScope** | Optional | String | The cloud platform scope. |
| **TargetDvcIdType** | Conditional | Enumerated | The type of TargetDvcId. |
| **TargetDeviceType** | Optional | Enumerated | The type of the target device. |
| **TargetIpAddr** | Optional | IP Address | The IP address of the target device. |
| **TargetDvcOs** | Optional | String | The OS of the target device. |
| **TargetPortNumber** | Optional | Integer | The port of the target device. |
| **TargetGeoCountry** | Optional | Country | Target country. |
| **TargetGeoRegion** | Optional | Region | Target region. |
| **TargetGeoCity** | Optional | City | Target city. |
| **TargetGeoLatitude** | Optional | Latitude | Target latitude. |
| **TargetGeoLongitude** | Optional | Longitude | Target longitude. |
| **TargetRiskLevel** | Optional | Integer | The risk level associated with the target. |
| **TargetOriginalRiskLevel** | Optional | String | The risk level as reported by the reporting device. |

### Inspection fields
| Field | Class | Type | Description |
| --- | --- | --- | --- |
| **RuleName** | Optional | String | The name or ID of the rule. |
| **RuleNumber** | Optional | Integer | The number of the rule. |
| **Rule** | Alias | String | Either the value of RuleName or RuleNumber. |
| **ThreatId** | Optional | String | The ID of the threat or malware identified. |
| **ThreatName** | Optional | String | The name of the threat or malware identified. |
| **ThreatCategory** | Optional | String | The category of the threat or malware identified. |
| **ThreatRiskLevel** | Optional | RiskLevel (Integer) | The risk level associated with the identified threat. |
| **ThreatOriginalRiskLevel** | Optional | String | The risk level as reported by the reporting device. |
| **ThreatConfidence** | Optional | ConfidenceLevel (Integer) | The confidence level of the threat identified. |
| **ThreatOriginalConfidence** | Optional | String | The original confidence level of the threat identified. |
| **ThreatIsActive** | Optional | Boolean | True if the threat identified is considered an active threat. |
| **ThreatFirstReportedTime** | Optional | datetime | The first time identified as a threat. |
| **ThreatLastReportedTime** | Optional | datetime | The last time identified as a threat. |
| **ThreatIpAddr** | Optional | IP Address | An IP address for which a threat was identified. |
| **ThreatField** | Conditional | Enumerated | The field for which a threat was identified. |
