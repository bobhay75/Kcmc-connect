# KCMC repository metadata repair

This helper repairs only the thirteen reported tracked files in `/home/bobsome1/repositories/Kcmc-connect-live`, changing mode 0664 to 0644 without changing bytes or ownership. Actual host caller UID 2162/GID 2147 and exact repository HEAD `4225fce8968747ad4f828a9a36087b04fd020484` are required for writes. The canonical baseline has 255 tracked files; the fixed thirteen targets are all Git mode 100644.

Before any chmod, the unchanged checksum-pinned alignment verifier checks the whole checkout: structure, configuration, branch/HEAD, source blobs, index, flags, ignored/untracked files, ownership and every other tracked mode. Only the thirteen independently leased 0664 modes receive a temporary expected 0644 stat view during verification. Actual file metadata remains separate, and held no-follow/nonblocking descriptors bind identity, ownership and bytes through every change.

All thirteen must be 0664, or all thirteen must already be 0644. Mixtures refuse. An already repaired baseline or already aligned `154b779a0ea3d27a11300bfe0454f8a7c4aca355` takes a strict read-only verification path without journal or chmod. Git-control file group IDs are preserved from their captured metadata; only the worktree targets require primary GID 2147.

Standalone commands are `python3 repair.py check` and `python3 repair.py repair`. The separately supplied launcher verifies immutable checksums before running either. Place the unchanged `align-repository.py` sidecar next to this script; it must be exactly 14,570 bytes with SHA-256 `1ed8ce0980638f8ff1488a6fda785f6aa6a12c8db03bfe8e75cc13c81955e0a6`. Source defaults are fixed; no CLI/environment path, identity or commit overrides exist.

A repair records private metadata under `/home/bobsome1/kcmc-repository-metadata-repairs`, outside Git and public_html. Journal directories are 0700, files 0600. Records contain the baseline HEAD, paths, dev/inode, prior modes, UID/GID and opaque blob hashes, including original Git config/HEAD/index fingerprints. No file contents or raw configuration values are copied.

Before each fchmod, the full verifier and raw leases run again. Failure restores prior modes only while original global checkout/config/index/HEAD and each affected file lease still match. Newer checkout state, bytes, inodes or modes are preserved. Uncertain intent or incomplete recovery reports manual review with the journal location. This helper has no manual rollback command; mixed or newer state is never bypassed on retry.

No chown, content rewrite, stash, reset, Git fetch/merge, configuration edit or application deployment is performed. Repository alignment remains the separate existing reviewed step after successful repair. CI should run the actual Git fixtures on Python 3.6 and current Python; local grammar checks alone do not establish Python 3.6 execution.
