# October 20–25 public content publication

This is a record-level update for the existing KCMC publishing store. It does not
replace the store with the repository's `data/content.json`. The source is the
October 16 Front Pew News, the owner-corrected Friends of Faith slide, and the
reviewed October 14/18 public content already in Git. The four bulletin fields,
specific record IDs, and accepted previous field values are pinned in
`reviewed-content.json` and verified before use.

## What becomes current

- Community Updates dated October 20, covering October 20–25, with current Sunday
  worship times and the requested “Called to love and serve” welcome.
- Way Forward All Church Informational Meeting with Pastor Tony on October 22 at
  1:30 PM, in both Events and Church Updates.
- Friends of Faith on Sundays at 10:20 AM in the Pairs & Spares Classroom, starting
  October 18. The supplied slide explicitly confirms weekly recurrence. There is
  no invented end date; the expired launch announcement is not republished.
- The remaining unexpired October 16 calendar items, the October 25 bottle
  return deadline, October 31 Trunk or Treat, and November 14 memorial dinner.
- Trunk signup wording now refers people to the office. “This Sunday” referred to
  October 18 and is removed. Existing confirmed 4:30–6:30 PM event hours remain.

Past dated events are skipped at publication time using local Central dates.
The package accepts publication only during October 20–25, 2026. A later week
needs a fresh editorial review. Rollback remains available after that window.
The authentic newsletter's unusual 5:17 PM times remain unchanged.

## Fixed host paths

Target: `/home/bobsome1/public_html/kcmc-connect/data/content.json`.
Private backups and receipts: `/home/bobsome1/kcmc-content-oct20-backups`.
The script uses Python 3.6 or newer, has no network operation, and never opens
configuration, accounts, prayer requests, payroll, subscriptions, or mail.

Place these three files together in a private staging directory outside
`public_html`. Verify the containing release package's published SHA256 and run:

```sh
python3 -I -B publish.py check
```

`check` is read-only. Review its exact action list and conflicts. A result of
`ready` permits preparation of the specified changes; it is not deployment
approval. Keep the reported SHA256. A result of `already_current` requires no
publication. Any conflict requires reviewing the live record in the publishing
desk; do not rewrite the fixture or bypass the refusal.

After release authorization, substitute the exact SHA256 from the successful
check, without angle brackets:

```sh
python3 -I -B publish.py apply --expected-sha256 <SHA256_FROM_CHECK>
python3 -I -B publish.py check
```

Apply takes the same file lock as the app, repeats the comparison, creates and
verifies a private actual-byte backup, then atomically replaces only the merged
document. It preserves unrelated records, extra fields, modes, and ownership.
It refuses changed bulletin fields, changed record fields/times, hidden or deleted
records, missing previously known records, and possible duplicate gatherings.
An existing matching weekly event is retained instead of adding another copy.
Repeating an already-current apply is a no-op with no additional backup.

The final check must report `already_current`. Verify the public bulletin and
Events in the browser, including Thursday's 1:30 PM meeting and Sunday's 10:20 AM
class. The tool does not make those public requests or claim production success.
There may already be unrelated expired or repeated records in the live store;
this package preserves them for staff review rather than guessing their intent.

## Rollback

Use the exact private receipt path returned by apply:

```sh
python3 -I -B publish.py rollback --receipt <RETURNED_RECEIPT_PATH>
```

Rollback verifies the backup and current applied hash, restores the actual
previous bytes and metadata, and refuses to overwrite any intervening staff edit.
Keep backups and receipts private. They contain the actual live content store and
must never be committed, uploaded with code, or placed under `public_html`.

## Local acceptance

From the repository root, run `python3 -B tools/kcmc-content-oct20/test_publish.py`.
Tests use temporary synthetic stores only. They cover expiry, recurrence,
duplicate conflicts, staff edits/removals, unrelated-data preservation, stale
hashes, private backups, atomic publication, idempotency, rollback, and unsafe
paths. No test reads the fixed host target.
