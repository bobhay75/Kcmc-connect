# Scoped credential-session repair

This separate installer repairs sessions that remain authenticated after a password change or reset. It installs exactly four code files, in this dependency order:

1. `lib/session-lifetime.php`
2. `lib/bootstrap.php`
3. `member/login.php`
4. `member/password.php`

The application patch is exactly the reviewed literal delta in `provenance/session-credential-reviewed.json` (SHA256 `85acda478e90d091f46f290018ab4eca65283e380b0eefa87752b1d27a8128c8`). Both supported source bundles receive those same replacements, with all other bytes preserved. The canonical after hashes match the reviewed application source; the older approved host variant preserves its own unrelated bootstrap code.

There are no account, role, owner-configuration or editorial migrations. The installer does not read or replace account records, passwords, prayer records, timecards, configuration or content. The earlier timecard/token/skip-link repair remains independently hash-verifiable: `member/activate.php`, `member/reset-password.php`, `lib/timeclock.php` and `app.js` are outside this installer. The fish homepage and service worker are outside its scope.

## Exact accepted bundles

`live154` is the approved October 13 source `154b779a0ea3d27a11300bfe0454f8a7c4aca355`, also independently represented by the frozen October 13 approved inventory. `main93` is `93c72f4fc430d311e01108d3a30d0561bb701c9d`. Source identity is evidence of approved bytes, not a claim about the current host. Selection uses the complete four-file hash/size tuple, not Git HEAD or matching patch anchors.

| Bundle | Bootstrap before SHA256 | Bootstrap after SHA256 |
|---|---|---|
| `live154` | `8c21edc4b25eecade0f792cf20038c73b71270934d0932e4e72432dc8b57d903` | `06380830080e186652125d74a27e506f351301a0953138c301d0bbc67ab82385` |
| `main93` | `96590431ef787a6a689a3c9e1655cdb4cac10c7c86e5cde8f579cd0b3571c518` | `d4eecc7375f6e678632b8b88fb8c64faaba6ac43513a59bae42fe673505bc263` |

The other three files are identical across the two bundles:

| File | Before SHA256 | After SHA256 |
|---|---|---|
| `lib/session-lifetime.php` | `470b60f55cc24a058bef4d4e5aa6f30a30ee34548702dd414ffda800fa72bd47` | `68a3b95a1f97b92d4fcba816d45d644df1ac46998b982ad3c085541c8a8b50e7` |
| `member/login.php` | `2db61ebc38cbb126a6f67d858bdb60e2553ea015d36cfdced869828887ddc4de` | `e94a975e0a7aaffd381e032f42f9a155c5fe5d1acd8119773277428ba008f4bb` |
| `member/password.php` | `75bcf891ef0d79c74567b4ec7b8e2e356bc7f797bca2234a36d5729973f9722b` | `2faa3fb20ff436afc518d2c5463435d1761abd084c6bcfc520cf21587563ee80` |

The complete byte lengths, exact before sources and reversible replacements are included in `runtime-reviewed.json` and `evidence/`. Any unknown file, unsafe file metadata or partial before/after state refuses. The installer never tries a generic patch on unknown code.

## Hosting commands

Use only the separately supplied immutable, checksum-verified launcher. The production paths are fixed to `/home/bobsome1/public_html/kcmc-connect`, hosting UID2162/GID2147, and a separate private backup root for each exact variant. Neither command-line arguments nor environment variables can override them.

`python3 -I -B installer.py` defaults to read-only `check`. It verifies the exact code bundle and, for a before bundle, discovers a real PHP8.2 CLI with a version-only probe before declaring `READY`. It checks cPanel/CloudLinux locations and the account's ordinary `php` command; CGI or another PHP version is refused before backup or live replacement. No account/config/application code is executed by these probes.

`python3 -I -B installer.py diagnose` reads only the four fixed code files and prints their hashes, byte lengths and metadata. It works for unknown regular code bytes and creates no backup or deployment. It shows no source, passwords, account records or configuration. Linked/unsafe files still refuse. Send this output for review if the bundle is unrecognized; do not bypass the exact-source gate.

`python3 -I -B installer.py apply` replaces only a complete approved before bundle. It preserves existing0644/0664 modes and file ownership. Private0700 backup/session directories,0600 original files, durable journals, locks, no-follow path descriptors and full file leases protect staging/replacement/recovery. All four staged hashes and PHP8.2 syntax are verified before any live replacement. The helper is installed before bootstrap calls it. The sequence is not an atomic bundle switch; staff should pause account/security operations during the short update.

After `apply`, save `PRIVATE_ROLLBACK` and run `check` again. A complete after bundle is a verified no-op with no new backup and no PHP-discovery requirement. Code hashes do not establish staff/browser acceptance.

Rollback requires the exact printed variant and session basename:

```sh
python3 -I -B installer.py rollback --variant live154 --session repair-PRINTED-SESSION-BASENAME
```

It refuses later file edits, replaced inodes, changed metadata, corrupt originals, uncertain transactions and unfinished operations in another variant. It restores only the same verified installed code identities. It restores consumers before dependencies, including old bootstrap before the old session helper. If a newer consumer may remain uncertain or unrestored, recovery keeps the verified new helper and its installed lease, records a conflict and requires manual review. It never reports that mixed recovery as successful rollback. A missing or changed helper is left untouched and also requires manual review. It does not restore or roll back accounts/content/private records. Retain any reported manual-review session; do not delete locks/backups to bypass a refusal.

## Expected account behavior

Existing sessions require one fresh sign-in after this security update because older sessions have no trustworthy credential binding. This leaves account identity, roles and owner authority unchanged. After signing in, an ordinary password change preserves that browser, rotates its ID/CSRF and retains its original absolute expiry; other sessions require sign-in on their next authenticated lookup. A password reset invalidates all older sessions and does not automatically authenticate its bearer. Automatic password-hash upgrades also invalidate older sessions. Already authorized requests are not cancelled mid-request.

The actual application tests use temporary synthetic accounts only. Complete the authorized staff acceptance separately; never test by changing a real owner's password just to validate installation.

## Reproducibility and validation

`derive_installer.py` starts from the frozen SHA256-pinned transaction engine. Alongside explicit inventory/root/release/messages/staging substitutions and stronger exact-byte PHP stage lint, it makes one required recovery adjustment: after verifying the helper's installed lease, retain it when uncertainty or earlier consumer conflicts remain. The new helper is compatible with old consumers; an old helper lacks the functions required by newer consumers. This guard preserves genuine recovery ownership and manual-review status. `provenance.json` records its exact before/after literal insertion, and the AST proof permits no other transaction-policy change. The wrapper adds exact-variant selection, PHP8.2 CLI discovery and a read-only hashes diagnostic.

The current-Python gate verifies the evidence against the immutable Git source objects and the canonical repaired app, reproducible generation, exact variant/partial-state selection, dependency order, untouched private/editorial/unrelated repair files, safe no-op/rollback and the inherited transaction failure cases. Actual Python3.6 runs the same temporary transaction/provenance tests. Real PHP8.2 verifies syntax and complete temporary apply/no-op/rollback on both variants. It also checks uncertain bootstrap/password commits, concurrent consumer edits during rollback and damaged/missing helpers. In mixed recovery, a pure temporary helper probe executes the binding and lifetime functions without loading bootstrap, configuration or real accounts. `CHECKSUMS.sha256` covers the package, excluding itself.
