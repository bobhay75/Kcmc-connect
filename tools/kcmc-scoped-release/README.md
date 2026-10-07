# KCMC scoped host repair

This helper installs exactly 16 reviewed application files from runtime commit `61c70f590735522adbfd6be02dab6888924a54fd`: six existing code files, the Publisher media endpoint, and nine supplied images. Its six existing-file preimages match host revision `ae004a659a7c2fb334296fa41f54dd5263f4d5c0`. The independent inventory records the immutable source, byte counts, SHA-256 hashes, Git blob hashes, preimages, and 13 preserved source guards.

Before applying or rolling back, close Publisher tabs and let all saves/uploads finish. Keep Publisher idle until the command completes. Its coordination locks cannot drain PHP requests that started earlier. Web PHP and this command must use the same `KCMC_PRIVATE_DATA_DIR`; the approved bootstrap uses that environment variable or the default existing `data/private` directory. A CLI/default path check does not establish an externally configured PHP-FPM environment.

The installer checks preimages and guarded files, stages and hashes each immutable download, runs PHP 8.2 syntax/image checks, makes private backups outside the web root, and replaces dependencies before consumers, with the service worker last. Anonymous HTTP checks verify the public pages, protected Publisher routes, and exact static bytes. Failure attempts a scoped code rollback. Rollback refuses newer code or Publisher-store edits. Private publication/media JSON is fingerprinted under its two application locks but is never copied, printed, restored, or replaced. The two coordination lock files may be created.

`data/content.json` is backed up privately and checked for concurrent edits, but is never replaced or restored. Accounts, prayer, timecards, configuration, and other private stores are outside the replacement scope. The helper performs no Git operations or broad deployment sync.

Run the SHA-256-verified, commit-pinned launcher supplied with the release. The standalone entry points are `python3 installer.py preflight`, `python3 installer.py apply`, and `python3 installer.py rollback --session BACKUP_DIRECTORY`. Save the backup directory printed by the installer. Before a later rollback after staff use, establish the web runtime's actual storage selection; the CLI/default guard alone cannot prove a hidden PHP-FPM override. Keep Publisher closed and drained during any rollback.

The host repository remains at `ae004a659a7c2fb334296fa41f54dd5263f4d5c0` after this scoped installation. Do not click cPanel **Deploy HEAD** until its repository has been separately aligned to the reviewed runtime; it could overwrite this repair with old code.

`content-review.py` is a separate read-only comparison of the approved October 13 Hope Keepers event with the unfiltered host content. It reports hashes and a conservative verdict without printing other host records or changing content. It refuses an expired candidate.

The fixtures cover interrupted replacements and journals, resumed rollback, permission/inode changes, symlinks, hardlinks, Publisher-store drift, locks, immutable downloads, lint discovery, and anonymous HTTP checks. CI verifies the independent source inventory and runs the fixtures on both current Python and Python 3.6. Signed-in staff workflows and physical-device offline/update/push acceptance remain separate checks.
