# Complete the inspected October 20 content publication

The live preflight stopped because the reviewed Friends of Faith event ID was
absent. The owner returned a read-only inspection of related event IDs, titles,
locations and descriptions, including future and hidden records. It contained
only Hope Keepers, whose description includes the unrelated word “friendship.”
The live content hash was unchanged from the original preflight:

`966fd76335dab9a1f7a4bf85edc889a2aa49fe1093fb40249741ca792cb2035b`

The observation establishes absence in this exact snapshot. It does not establish
why the class was absent. The owner has already approved publication of the
reviewed October 20–25 content, including the continuing Sunday class.

## Exact correction

`reconcile-observed-live.py` is a separate operation for this inspected snapshot.
It leaves `publish.py`, its pinned fixture, and its missing-known-record guard
unchanged. Its fixed stage is the verified directory returned by the live check:

`/home/bobsome1/kcmc-pr161-check-z8h3hqw2`

The added record is the complete, unchanged target object in the pinned fixture:

| Field | Reviewed value |
| --- | --- |
| ID | `faith-friends-20261018` |
| Title | Friends of Faith Sunday Bible Study |
| Schedule | Sundays, 10:20 AM, beginning October 18, 2026 |
| Location | KCMC — Pairs & Spares Classroom |
| Study | Becoming Like Jesus by Matt Chandler |
| Recurrence | Weekly, with no invented end date |
| Publication | Published; no active expiry |

The separately expired October 18 launch announcement remains skipped. The old
one-time expiry is retained in the event's provenance field, as already reviewed.

## Transaction and limits

1. Verify the fixed hosting account and exact staged publisher/fixture hashes.
2. Require the exact observed live-content hash and the original planner's
   single known missing-class conflict. Any additional conflict stops the work.
3. Check every event for plausible class identities, including legacy titles,
   underscore IDs, hidden/deleted records and future-start recurrences.
4. Add the pinned target to a fresh copy of the original document and rerun the
   unchanged planner for all remaining approved bulletin/event changes.
5. Acquire the application's content lock, reread the live bytes, and repeat
   the planning and exact-hash checks.
6. Save and verify a private backup of the actual original bytes and a receipt
   compatible with the original publisher's conditional rollback.
7. Replace the content file once, preserving its mode and owner. Verify the
   final hash and require the unchanged planner to report no remaining changes.

The backup and receipt are under `/home/bobsome1/kcmc-content-oct20-backups`.
They contain live data and must remain private. The receipt path and exact
rollback command are printed before the atomic replacement, so they remain
available if the process is interrupted immediately afterward.

There are no configurable host paths, replacement-hash overrides, force flags,
network calls or changes to application code, configuration, authentication,
private prayer, timeclock, payroll or mail. The original October 20–25 Central
publication window remains enforced. An intervening live edit or a repeat
`apply` fails the fixed before-hash check and performs no second publication.

## Operation

Use an immutable-commit download and a separately verified script SHA256. If
saving the script to the hosting account, keep it outside `public_html`.

```sh
python3 -I -B reconcile-observed-live.py check
python3 -I -B reconcile-observed-live.py apply
python3 -I -B /home/bobsome1/kcmc-pr161-check-z8h3hqw2/content-publication/publish.py check
```

The standalone `check` performs no writes. The prepared `apply` is covered by
the owner's existing release approval. Successful output is `published` with
`publisher_check: already_current`. The final original-publisher check must also
say `already_current`. Verify the public bulletin, the October 22 meeting at
1:30 PM, and the recurring Sunday class at 10:20 AM after the host succeeds.

If interrupted or stopped, retain the complete output and printed receipt.
Use only the printed original-publisher rollback command after checking the
receipt and current hash; its conditional rollback refuses intervening edits.
Do not modify the fixed snapshot hash or the original publication fixture to
make a failed run pass.

## Verification

Run the original publisher suite and the reconciliation suite on synthetic stores:

```sh
python3 -B tools/kcmc-content-oct20/test_publish.py
python3 -B tools/kcmc-content-oct20/test_reconcile_observed_live.py
```

The synthetic store is constructed from the historical source fixture and
represents the observed missing-class condition. It is not a copy of the live
store, and the production hash remains fixed independently of test fixtures.
