#!/usr/bin/env python3
"""Verify the immutable prior release and its historical workflow separately.

The current workflow projects themed runtime back to that release. Its own old
checksum belongs to the exact historical workflow; every package artifact is
still checked from the current checkout, without rewriting the old inventory.
Python 3.6 compatible; no application or host operation.
"""
from __future__ import print_function

import hashlib
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = 'b0c257edb8a42fc89fd6371c1bce7ee3efbd5ed9'
MANIFEST = 'tools/kcmc-team-payroll-host-oct15-CHECKSUMS.sha256'
WORKFLOW = '.github/workflows/team-payroll-host-repair.yml'
PATHS = frozenset([
    WORKFLOW,
    'tools/kcmc-team-payroll-host-coordinator-oct15.py',
    'tools/test-team-payroll-host-coordinator-oct15.py',
    'tools/verify-team-payroll-host-coordinator-oct15.py',
    'tools/kcmc-team-payroll-host-oct15-README.md',
    'tools/kcmc-team-payroll-repair-oct15/installer.py',
    'tools/kcmc-workflows-repair-v2-oct15/installer.py',
])


def verify():
    raw = (ROOT / MANIFEST).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '987156cfe9556127627cdc8e1e7b311384fe4f62909504e8c6d30413c8e17e8c', 'Historical release checksum inventory changed'
    rows = [line.split('  ', 1) for line in raw.decode('ascii').splitlines()]
    assert len(rows) == len(PATHS) and {row[1] for row in rows} == PATHS, 'Historical inventory membership changed'
    for expected, name in rows:
        assert re.match(r'\A[0-9a-f]{64}\Z', expected), 'Invalid checksum'
        if name == WORKFLOW:
            data = subprocess.check_output(['git', '--no-replace-objects', '-C', str(ROOT), 'show', BASE + ':' + name])
        else:
            path = ROOT / name
            info = path.lstat()
            assert stat.S_ISREG(info.st_mode) and not path.is_symlink(), 'Ordinary current release file required: ' + name
            data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, 'Historical checksum mismatch: ' + name
        print('PASS: ' + name + (' (exact historical workflow)' if name == WORKFLOW else ' (current artifact)'))


if __name__ == '__main__':
    verify()
