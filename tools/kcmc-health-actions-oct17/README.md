# Scoped health actions repair

This offline, hash-pinned installer replaces only `admin/health.php` when its
existing bytes exactly match the verified installed image. The replacement adds
expandable health checks, links to existing tools and status filters. The frozen
transaction engine and corrected policy extension are reused without changes.

The 21 imported-library, shared-screen and linked-tool prerequisites are read-only
guards. Their bytes and filesystem leases must remain unchanged through the
transaction. The public homepage is not a prerequisite: the hosting site's
reviewed calendar variant is preserved.

Run the separately supplied pinned download and SHA256 verification first, then:

```sh
python3 -I -B installer.py check
python3 -I -B installer.py apply
python3 -I -B installer.py check
```

The existing target mode (0644 or 0664) is preserved. Staged PHP is checked using
a real PHP8.2 CLI before replacement. An already repaired target is verified
without a new replacement, backup or PHP probe. Unknown bytes, unsafe file
metadata, changed prerequisites or an unfinished journal stop the repair.

Original code and the transaction journal stay outside `public_html` under
`/home/bobsome1/kcmc-health-actions-backups`. The installer prints the exact
private session and rollback command. To roll back, download and verify this
same pinned installer and use its printed session name:

```sh
python3 -I -B installer.py rollback --session repair-TIMESTAMP-IDENTIFIER
```

The installer does not execute the application, change configuration, read or
replace private/editorial records, change accounts or roles, send email or push,
run payroll, or touch cron or the hosting Git checkout. Opening health guidance
and tool links does not activate those operations.

`derive_installer.py` checks the exact reviewed images and input hashes;
`test_installer.py --git-root ../..` additionally verifies the independently
reviewed one-file runtime Git delta and read-only prerequisites. CI runs isolated
transaction tests, the existing 72 engine/policy safety checks, real PHP8.2 syntax
and rollback checks, and actual Python3.6 compatibility.
