# Fish menu homepage repair — October 14, 2026

The owner requested that homepage navigation and announcements live inside the fish dropdown. This offline installer changes exactly `index.php`, `public-presentation.css`, and `sw.js`. It removes the full-width announcement bar and duplicate navigation, keeps the complete approved announcements under Church updates, adds office/social/youth/invitation actions to the fish, and refreshes the public service-worker cache.

Two complete, exact source bundles are accepted: the previously installed public release `154b779a0ea3d27a11300bfe0454f8a7c4aca355`, and application source from `1af697ac828724a74ba15f9c7167f09b45e35f89`. Each variant retains its existing homepage styling and calendar code. The installer transforms local bytes; it never downloads or copies a newer application wholesale. No application execution, repository update, editorial/private record change, owner configuration change, or account change occurs.

`check` is read-only. `apply` first checks both private backup roots for unfinished operations, identifies exactly one coherent before/after bundle, stages and hashes all three files, and uses the fixed PHP 8.2 CLI only for version and syntax checks. Unknown bytes, mixed versions, changed file identities, symlinks, foreign owners, unsafe metadata, or interrupted sessions stop the operation. Modes 0644 and 0664 are preserved. Reapplying an entirely repaired bundle does nothing.

Successful application prints the private rollback directory and an exact rollback command using both `--variant` and `--session`. Original files are stored outside the web root in owner-only directories. Rollback restores only files whose current identities still match this transaction; uncertain or concurrent edits remain available for manual review.

Production commands after verifying the published installer checksum:

```sh
python3 -I -B installer.py check
python3 -I -B installer.py apply
python3 -I -B installer.py check
```

Reproduce and validate source artifacts from this directory:

```sh
python3 -B derive_installer.py
python3 -B test_installer.py --runtime-root ../../KCMC-Connect-Phase6-Recreated
python3 -B test_inherited_safety.py
python3 -B verify-stage.py --php /path/to/php8.2
```

`derive_installer.py --from-source --runtime-root /path/to/reviewed/app` refreshes source-review deltas only; it is not a hosting option. The frozen transaction engine is checksum-pinned. Only the explicit scope, inventory, release/backup names, private filename suffix, and staged file verifier differ. The safety tests exercise lease races, locks, journals, signals, staged-byte tampering, failures before/after rename, concurrent edits, and recoverable rollback. Additional tests check variant selection, exact outputs, untouched editorial/configuration sentinels, and complete no-op behavior. Physical-device and authenticated staff acceptance remain separate.
