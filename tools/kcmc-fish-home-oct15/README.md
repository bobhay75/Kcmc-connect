# Fish menu homepage repair for the installed calendar — October 15, 2026

This local candidate adds PHP CLI discovery in the wrapper. Publication awaits the hosting account's read-only PHP diagnostic. All three embedded transaction engines, their source hashes, backup roots, journal handling, and rollback behavior remain byte-for-byte identical to installer `f716ab7b1b99f01738de84d4eff37107a5057043c4d6c38be13c1e78f03ac288`.

The owner requested that homepage navigation and announcements live inside the fish dropdown. This offline installer changes exactly `index.php`, `public-presentation.css`, and `sw.js`. It removes the full-width announcement bar and duplicate navigation, keeps the complete approved announcements under Church updates, adds office/social/youth/invitation actions to the fish, and refreshes the public service-worker cache.

Three complete, exact source bundles are accepted: the previously installed public release `154b779a0ea3d27a11300bfe0454f8a7c4aca355`, application source from `1af697ac828724a74ba15f9c7167f09b45e35f89`, and the observed installed public release with its approved weekly calendar already applied (`livecalendar`). Each variant retains its existing homepage styling and calendar code. The installer transforms local bytes; it never downloads or copies a newer application wholesale. No application execution, repository update, editorial/private record change, owner configuration change, or account change occurs.

The earlier October 14 installer correctly refused the installed calendar combination. Its index is 33,550 bytes with SHA256 `745bdc1f31824b8962ef49440a83e313dbdea70e4a8e0620ff746049f656df3d`; the CSS and worker still match the approved public release. This preimage is reconstructed exactly by applying the three reviewed calendar replacements to the Git-pinned public-release index. The original calendar fixture, derivation metadata, and original refused installer are frozen in `provenance/`. The two previous transaction engines and backup roots remain unchanged. The new engine adds its own private root, `/home/bobsome1/kcmc-fish-home-livecalendar-backups`.

`check` is read-only. For an unrepaired source bundle, both `check` and `apply` verify an available PHP 8.2 CLI before any backup creation. The wrapper tries known cPanel and CloudLinux paths, then the hosting account's ordinary `php` command. Only a successful `-n -v` result starting with `PHP 8.2.x (cli)` is accepted. `check` reports the selected absolute path and version before reporting readiness. There is no user-supplied PHP path argument. Fully repaired no-ops and rollback require no PHP runtime discovery.

`apply` checks all three private backup roots for unfinished operations, identifies exactly one coherent before/after bundle, stages and hashes all three files, and runs the unchanged engine's PHP version and syntax checks using the verified CLI path. Unknown bytes, unreviewed combinations, changed file identities, symlinks, foreign owners, unsafe metadata, or interrupted sessions stop the operation. Modes 0644 and 0664 are preserved. Reapplying an entirely repaired bundle does nothing. Refusals include vetted per-variant guard reasons without printing file contents or arbitrary exception text.

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

`derive_installer.py --from-source --runtime-root /path/to/reviewed/app` refreshes source-review deltas only; it is not a hosting option. The frozen transaction engine is checksum-pinned. Only the explicit scope, inventory, release/backup names, private filename suffix, and staged file verifier differ. The safety tests exercise lease races, locks, journals, signals, staged-byte tampering, failures before/after rename, concurrent edits, and recoverable rollback. Additional tests check the exact installed-calendar reconstruction, the original installer's refusal, all twelve combinations of known index/CSS/worker preimages, existing-engine identity, safe diagnostic filtering, untouched editorial/configuration sentinels, and complete no-op behavior. Physical-device and authenticated staff acceptance remain separate.
