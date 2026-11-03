# Cultiva portable package (.cultiva)

Cultiva's `.cultiva` file is a ZIP-based portable data package. It is produced by
**Library → Export .cultiva** and can be selected in **Library → Import files**.

## Package contents

- `manifest.json`: format identifier, package version, creation time, module counts,
  and compatibility metadata.
- `records.csv`: UTF-8 CSV with a `record_type` column. The importer routes each
  row to its corresponding Cultiva module.

## Supported record modules

Crops, Workers, Plots, Plantings, Tasks, Shifts, Attendance, Journal, and Notes.

## Portability and import behavior

- Source auto-increment IDs are not exported.
- Relationships are represented using human-readable natural keys (for example,
  crop name, plot name, worker name, and planting date) and resolved against the
  receiving database.
- Parent records are imported before dependent records.
- Existing matching records are skipped; existing records are not overwritten.
- Validation occurs before database writes. Inserts run in one database transaction;
  a failure rolls back the package import.
- `.csv`, `.xlsx`, and `.xls` import remains available as before.

## Current package boundary

Version 1 packages portable module records only. Binary Library resources and
attachments linked to Notes or Journal entries are not included. Those files remain
in each installation's own Library and are not silently copied or referenced across
machines. A future package version can add resource payloads and portable resource
links with their own integrity checks.

## Compatibility

The manifest uses `format_id: cultiva.portable` and `package_version: 1`. The importer
rejects unknown formats and unsupported versions rather than guessing how to read them.
