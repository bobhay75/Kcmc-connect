#!/usr/bin/env python3
"""Read-only interlock for four observed source/hosting divergence points."""
from __future__ import print_function

import os
from pathlib import Path
import stat
import sys

SOURCE = Path(__file__).absolute().parents[1] / 'KCMC-Connect-Phase6-Recreated'
LIVE = Path('/home/bobsome1/public_html/kcmc-connect')
FILES = ('index.php', 'public-presentation.css', 'sw.js', '.htaccess')
LIMIT = 2 * 1024 * 1024


class Refusal(Exception):
    pass


def require(ok):
    if not ok:
        raise Refusal()


def directory_chain(root):
    require(root.is_absolute() and all(part not in ('.', '..') for part in root.parts))
    root_owner = os.lstat('/').st_uid
    result = []
    current = Path('/')
    for part in ('',) + root.parts[1:]:
        if part:
            current = current / part
        info = os.lstat(str(current))
        require(stat.S_ISDIR(info.st_mode))
        require(info.st_uid in (root_owner, os.getuid()))
        # Permit the root-owned sticky /tmp parent used by isolated fixtures;
        # an ordinary group/world-writable ancestor is not trusted.
        require(stat.S_IMODE(info.st_mode) & 0o022 == 0 or
                (info.st_uid == root_owner and info.st_mode & stat.S_ISVTX))
        result.append((info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid))
    require(info.st_uid == os.getuid() and info.st_gid == os.getgid() and
            stat.S_IMODE(info.st_mode) & 0o022 == 0)
    return tuple(result)


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_uid, info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def safe_regular(info):
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
            info.st_uid == os.getuid() and info.st_gid == os.getgid() and
            stat.S_IMODE(info.st_mode) & 0o7022 == 0 and info.st_size <= LIMIT)


def read_regular(path):
    before = os.lstat(str(path))
    safe_regular(before)
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        safe_regular(opened)
        require(fingerprint(opened) == fingerprint(before))
        data = bytearray()
        while len(data) <= LIMIT:
            chunk = os.read(fd, min(65536, LIMIT + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        require(len(data) <= LIMIT and len(data) == opened.st_size)
        require(fingerprint(os.fstat(fd)) == fingerprint(opened))
    finally:
        os.close(fd)
    require(fingerprint(os.lstat(str(path))) == fingerprint(opened))
    return bytes(data), fingerprint(opened)


def check():
    roots = ((SOURCE, directory_chain(SOURCE)), (LIVE, directory_chain(LIVE)))
    require(SOURCE != LIVE)
    leases = []
    for name in FILES:
        source, source_lease = read_regular(SOURCE / name)
        live, live_lease = read_regular(LIVE / name)
        require(source == live)
        leases.extend(((SOURCE / name, source_lease), (LIVE / name, live_lease)))
    for root, identity in roots:
        require(directory_chain(root) == identity)
    for path, identity in leases:
        require(fingerprint(os.lstat(str(path))) == identity)


def main():
    try:
        require(len(sys.argv) == 1)
        check()
    except (Refusal, OSError, ValueError):
        print('REFUSED: protected deployment files differ, are missing, or are unsafe. '
              'Use a reviewed scoped release. No files changed.', file=sys.stderr)
        return 1
    print('PASS: four protected files match exactly. Read-only preflight; '
          'full application parity is not established.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
