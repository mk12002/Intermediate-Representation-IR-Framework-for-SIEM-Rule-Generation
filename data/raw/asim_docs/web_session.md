Note: Web Session schema is a documented superset of the Network Session
schema (network_session.md) — all NetworkSession fields apply here too,
per https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-web
("the Web Session schema is a super set of the ASIM Network Session schema").

### HTTP session fields
| Field | Class |
| --- | --- |
| **Url** | Mandatory |
| **UrlCategory** | Optional |
| **UrlOriginal** | Optional |
| **HttpVersion** | Optional |
| **HttpRequestMethod** | Recommended |
| **HttpStatusCode** | Alias |
| **HttpContentType** | Optional |
| **HttpContentFormat** | Optional |
| **HttpReferrer** | Optional |
| **HttpUserAgent** | Optional |
| **UserAgent** | Alias |
| **HttpRequestXff** | Optional |
| **HttpRequestTime** | Optional |
| **HttpResponseTime** | Optional |
| **HttpHost** | Optional |
| **FileName** | Optional |
| **FileMD5** | Optional |
| **FileSHA1** | Optional |
| **FileSHA256** | Optional |
| **FileSHA512** | Optional |
| **Hash** | Alias |
| **HashType** | Conditional |
| **FileSize** | Optional |
| **FileContentType** | Optional |
| **HttpCookie** | Optional |
| **HttpIsProxied** | Optional |
| **HttpRequestBodyBytes** | Optional |
| **HttpRequestCacheControl** | Optional |
| **HttpRequestHeaderCount** | Optional |
| **HttpResponseBodyBytes** | Optional |
| **HttpResponseCacheControl** | Optional |
| **HttpResponseExpires** | Optional |
| **HttpResponseHeaderCount** | Optional |
