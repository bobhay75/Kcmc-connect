This standalone installer changes only the reviewed nine-line skip-link insertion in `/home/bobsome1/public_html/kcmc-connect/app.js`. It makes no application requests and performs no configuration, record, repository, network or JavaScript execution.

Run as the hosting account, UID 2162 / GID 2147. Keep this installer outside `public_html`. Keep other code uploads and editors idle during the repair; the retained file-descriptor checks catch observed changes, but the final `os.replace` call is not a kernel compare-and-swap and cannot exclude an uncooperative writer in its last syscall gap.

The default action is read-only:

```sh
python3 installer.py
```

Apply only after `CHECK READY` and after the release operator has checked the exact candidate with `node --check` off-host:

```sh
python3 installer.py apply
```

The host stage gate verifies the pinned JavaScript hash, size and private mode. It does not check JavaScript syntax. Node is not required on the host, PHP lint is not used for JavaScript, and staged JavaScript is never executed.

The fixed before hash is `2a3e82a72ad689cec36984541c8c5a4c1b740fa2de7e38b2e1cd7b5aee373348` (18,999 bytes). The fixed after hash is `d2d349264224e119482187e0fdbfcee6cd6ed29c16b1874c65c88cf29dd93963` (19,463 bytes). The repair comes from merged PR 128, with supplied reviewed head `dd2af94b8fd84e055f13f86fb77d86959b46d0d1`; the older fixture identifies its source commit separately. Unknown live bytes, unsafe paths, ownership or mode, changed leases, and unfinished prior sessions are refused. Already repaired bytes are a no-op and create no new backup.

Successful application prints the exact private session and rollback command. Backups and the durable journal stay under `/home/bobsome1/kcmc-skip-repair-backups`, with directories mode 0700 and original backups/journal mode 0600. Live mode 0644 or 0664 is preserved. Private stage and restore files use `.js` names. For explicit rollback, copy the printed session basename exactly:

```sh
python3 installer.py rollback --session repair-YYYYMMDDTHHMMSSZ-UUID32
```

Rollback verifies the installed identity and original backup before restoring. An uncertain rename or concurrent edit requires manual review; intent or matching bytes alone never authorizes restoration. Retain private sessions for review and rollback. No backup or live-file cleanup command is included.

The transaction engine is mechanically derived from the frozen three-PHP installer SHA-256 `4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7`. Only the module description, fixed backup/release/path/inventory constants, three scope/stage messages, six private `.php` suffixes, and stage verification body differ. UID/GID, application root, complete leases, no-follow held descriptors, durable intent, conservative recovery and explicit rollback remain unchanged. The inert `subprocess` import and exception class remain to minimize engine changes; the installer contains no subprocess call.

Local verification uses temporary synthetic files, prohibits subprocesses, and checks byte-for-byte derivation and normalized AST equivalence. It also reconstructs the exact supplied candidate when its runtime root is provided:

```sh
python3 test_installer.py --runtime-root /path/to/reviewed/KCMC-Connect-Phase6-Recreated -v
```

The package author ran these checks on Python 3.12. The release operator performs the required actual Python 3.6 runtime and Node syntax checks before publication. Test fixtures, provenance and derivation scripts are development evidence and are not needed to run the standalone host installer.
