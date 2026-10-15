# Protect the observed hosting differences before broad deployment

The mandatory first `.cpanel.yml` task runs a read-only comparison of `index.php`, `public-presentation.css`, `sw.js`, and `.htaccess` between this repository's application directory and `/home/bobsome1/public_html/kcmc-connect`. Every file must exist, be a regular single-link file owned by the caller and group, have safe metadata, and contain exactly the same bytes on both sides. Parent symlinks, file replacement or mutation during reads, unknown metadata, missing files and any difference cause a nonzero exit. No private configuration values, file contents or hashes are printed. There are no CLI or environment bypasses.

The task uses `python3 -I -B` and an explicit `|| exit 1`. It precedes directory creation, the existing `rsync --delete`, and every other deployment task. The original eight tasks and their exclusions remain unchanged. In a Bash task stream, a refusal exits before any later command even without shell errexit. The test fixtures check both refusal and successful continuation without executing a real deployment. No cPanel deployment was invoked to test the guard.

This deliberately blocks a standard deployment while the installed calendar-preserving homepage differs from canonical source or the live `.htaccess` contains a private owner setting absent from source. Use a reviewed scoped release for an intended change. Do not copy live files into Git, remove private configuration, or weaken the comparison to get past a refusal.

These four comparisons protect the observed divergence points. A passing check does not establish complete application parity, validate all other runtime changes, authorize broad deployment, or replace staff/device acceptance. The guard writes no application, editorial, private, account, or configuration files and performs no network operation.

The fish-source alignment helper is separate. Its target remains pinned to merge `fc04d1593d60470e35bf92572baca5b38c185e67`. That commit predates this guard: aligning to it does not install this new `.cpanel.yml` protection. Adopting the guard on hosting requires a separately reviewed repository update to a commit that includes it. Future main merges never silently advance the older alignment pin.

The historical exact-source proof reverses one explicitly pinned `.cpanel.yml` task insertion, then checks the original deployment tasks against their original Git object. The fish, editorial, configuration-example, owner, privacy and other runtime provenance fixtures remain unchanged.
