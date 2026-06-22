# Source Attribution

## Detection rule pairs

- Source: https://github.com/Azure/Azure-Sentinel (MIT License)
- Commit: `012a82a211647a541a5975c860c756311278cf12`
- Pulled: 2026-06-22
- Folders used: `Detections/`

## ASIM field reference

The Azure-Sentinel repo's `ASIM/schemas/*.yaml` files use a declarative
format (`Include:` directives, `<<Role>>` placeholder substitution resolved
per-entity) that requires reimplementing ASIM's own schema compiler to
resolve correctly — out of scope here. There is no `ASIM/ASimSchemas/*.md`
folder in the repo (an earlier, incorrect assumption).

Instead, `data/raw/asim_docs/*.md` are condensed field tables transcribed
from the authoritative published reference at:

- https://learn.microsoft.com/en-us/azure/sentinel/normalization-common-fields
- https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-authentication
- https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-network
- https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-process-event
- https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-file-event
- https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-dns
- https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-web
- https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema-registry-event

Fetched: 2026-06-22. Doc source git_commit_id (MicrosoftDocs/defender-docs-pr):
`758c40dcd3c98207d86c06af4af61ecc23c8ad96`.

`WebSessionEvent` includes all `NetworkSessionEvent` fields — the Web Session
schema is documented as a superset of the Network Session schema.

Field names were transcribed by hand from the fetched pages (not the full
verbatim doc text — descriptions were dropped, only `Field`/`Class` kept)
since only the field-existence set is needed for validation. Re-verify
against the live docs before relying on this for anything beyond this
project's schema-validation use case, and re-pull if ASIM schema versions
referenced in `data/raw/asim_docs/*.md` (see per-schema "Schema updates"
sections on the live pages) have since advanced.
