# Event reconciliation review — 30 September 2026

## Scope and status
This is a read-only maintenance tool, not another app feature and not a deployment. No app, `.cpanel.yml`, content, configuration, role, private-store, or hosting file is modified. Keep the existing release pinned to `2146af219d2fd23136eae1685f91a2a2caec030e` (PRs #83–84).

The existing deployment intentionally excludes `data/content.json`. A code deployment therefore does not copy missing public events into an existing production content store. A public webpage or filtered API response cannot prove whether the raw host record is absent, hidden, expired, or edited. Do not use either as the host input for this tool.

## Provenance
- Source request: PR #81, `Update KCMC public events from September 25 Front Pew News`.
- Baseline before PR #81: `8e2ce75dfcef240a153778a7c1a4ae1e5041fbc7`.
- Reviewed source release: `2146af219d2fd23136eae1685f91a2a2caec030e`.
- Content path: `KCMC-Connect-Phase6-Recreated/data/content.json`.
- Source includes Methodist Men's Breakfast on October 3 and Hope Keepers on October 13. These are repository-backed candidates, not proof that production has published them or that leadership has approved every calendar item for front-page display.
- September 29 events are past on September 30. Do not extend expired dates or invent future recurrence merely to make the list look populated.

## Usage
Requires PHP 8+ CLI. Run from a separate reviewed checkout of this branch outside `public_html`, never by switching the live cPanel deployment checkout. The tool does not load app bootstrap, call the network, or write any file. It prints a review proposal to standard output.

After authenticated access is available, create a private working directory outside the public document root. Export the two pinned repository snapshots and take an unfiltered copy of the real live `data/content.json`. Do not copy member/prayer stores. Example commands for the existing account, to be run only after confirming these paths:

```bash
umask 077
REVIEW=$(mktemp -d /home/bobsome1/kcmc-event-review.XXXXXXXX)
REPO=/home/bobsome1/repositories/Kcmc-connect-live
CONTENT=KCMC-Connect-Phase6-Recreated/data/content.json

git -C "$REPO" show "8e2ce75dfcef240a153778a7c1a4ae1e5041fbc7:$CONTENT" > "$REVIEW/baseline.json" || exit 1
git -C "$REPO" show "2146af219d2fd23136eae1685f91a2a2caec030e:$CONTENT" > "$REVIEW/source.json" || exit 1
cp /home/bobsome1/public_html/kcmc-connect/data/content.json "$REVIEW/live-snapshot.json" || exit 1

# Execute from the separate reviewed checkout containing the new tool.
# Replace the example as-of with the actual review time, including its UTC offset.
php tools/plan-event-reconciliation.php \
  --baseline="$REVIEW/baseline.json" \
  --source="$REVIEW/source.json" \
  --live="$REVIEW/live-snapshot.json" \
  --as-of=2026-09-30T04:00:00-05:00 > "$REVIEW/proposal.json"
```

If a pinned revision is not available locally, stop and inspect the repository; do not substitute a different revision. Never redirect output over an input or into `public_html`. Keep snapshots/proposals private: the live snapshot can contain unpublished editorial material even though only event IDs are reported from it.

## Interpretation and safety
- `proposed_additions`: missing IDs newly introduced after the baseline, published in the source, with valid date/time/expiry, not expired, and not before the current America/Chicago date. These are suggestions for editorial review, not authorization to publish.
- `already_present`: exact source records already exist on the host; object-key order is ignored.
- `preserved_host_only_ids`: host records absent from repository source; no removal is proposed.
- `preserved_missing_baseline_ids`: old repository records absent from host; no resurrection is proposed.
- `conflicts`: same ID with different contents, changed pre-existing repository events, or possible same-title/date duplicates under another ID. Resolve explicitly; never force overwrite.
- `skipped`: hidden, future publication, incomplete, expired, past-date or invalid new records. No dates, times, statuses or titles are invented.
- `input_sha256`: exact input-byte fingerprints. Before any future authorized write, re-read live content and compare its hash with the reviewed snapshot; re-plan if it changed.

No combined replacement `content.json` is produced. There is no `--apply`, upload, publish, or write command. There is no deletion mode. Display classification is separate from editorial suitability: staff/internal items still require a deliberate choice. Potential duplicates with substantially different spelling remain a human-review responsibility.

Exit codes: `0` proposal generated without detected conflicts; `2` proposal generated with conflicts requiring review; `1` invalid input/options or read failure. A zero exit code does not mean production is synchronized, editorial approval is complete, or deployment is authorized.

## Tests
`php tests/event-reconciliation-plan-contract.php` exercises additions, baseline deletions, host-only preservation, host edits, conflicts, duplicates, idempotency, date boundaries, invalid data, read-only CLI behavior, fingerprints, and non-disclosure of unrelated host fields. The existing Tony cleanup pull-request workflow runs all `tests/*contract.php` plus public/signed-in browser and security checks. Synthetic fixture results must not be represented as tests against the actual production content file.

## Remaining deployment gate
The cloud browser profile has no saved cPanel session; the prior sign-in window expired. This branch does not solve authentication and does not bypass it. Once authenticated, the existing reviewed code deployment and a separately reviewed, privately backed-up content reconciliation can proceed. Actual host content and private-screen rendering remain unverified until then.
