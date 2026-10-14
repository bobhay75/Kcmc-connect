# Owner Prayer & Care access

An active administrator whose ID matches `KCMC_OPERATIONS_OWNER_USER_ID` receives the existing member, prayer-team, pastoral and recovery route capabilities. The stored role is unchanged: a recovery owner retains account recovery controls while gaining Prayer & Care review and warrior approvals. The owner-only Operations guard remains unchanged.

No account records, other users' roles, prayer text, sharing choices, public content, or homepage files are modified. Existing private prayer records remain behind authentication. Prayer warrior approval does not grant the legacy prayer-team role. Even the owner cannot publish a request whose author chose pastoral-only privacy.

The override fails closed for an unset owner ID, a mismatched account, an inactive account, or a designated account without an administrator role. Empty role lists and unknown future roles are not granted. The existing configured owner is the sole identity source; there is no public signup or user-editable owner flag.

Release exactly `lib/bootstrap.php` and `lib/prayer-care.php` after verifying the current owner session passes Operations. Back up both files outside the web root, verify source preimages, lint staged PHP, and verify hashes after replacement. Do not edit users.json or prayer stores. Verify the private Review tab without opening existing prayer details or creating production signups.

Tests cover owner approval through a real synthetic browser session, other recovery denial, member denial, consent boundaries, unchanged roles and legacy records, private cache headers, Operations restrictions, and exact source provenance. Tests use only isolated synthetic data.
