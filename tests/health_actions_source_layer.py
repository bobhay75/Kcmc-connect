#!/usr/bin/env python3
"""Reverse only the exact reviewed health actions before historical proofs.

The one existing health route is byte-pinned and reversibly projected to its
installed preimage. ManualClockLayer still checks the complete application
membership, modes and every other runtime byte against the existing fixtures.
No application, private store, Git mutation or host operation is performed.
"""
from __future__ import print_function

import argparse
import hashlib
import json
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = '8f25cf66b86d9bada85077867bc52436cdaced4f'
BASE_TREE = 'a6989b63c5b0aaf6d95659574e0020ad98645b22'
FIXTURE = 'tests/fixtures/health-actions-reviewed.json'
FIXTURE_SHA256 = 'c0e3b7913b7e6938cd20704bdc283c886bb419ce17fa1813b51bf6012524e2ee'
MODIFIED = frozenset(['admin/health.php'])
BEFORE_SHA256 = '600c22ea31fc8cd340d819e3356ca5eef42e3d8bd64897500a92aa988364e5a9'


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


class HealthActionsLayer:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.app = self.root / PREFIX
        require(self.app.is_dir() and not self.app.is_symlink(),
                'Health-actions application mount must be an ordinary source directory')
        raw = (self.root / FIXTURE).read_bytes()
        require(sha256(raw) == FIXTURE_SHA256, 'Exact immutable health-actions fixture required')
        fixture = json.loads(raw)
        require(set(fixture) == {'source_commit', 'source_tree', 'modified'} and
                fixture['source_commit'] == BASE and fixture['source_tree'] == BASE_TREE,
                'Health-actions installed source context must remain pinned')
        require(set(fixture['modified']) == MODIFIED,
                'Health-actions fixture must enumerate only the existing health route')
        self.preimages = {}
        for name, record in fixture['modified'].items():
            require(set(record) == {'before_sha256', 'after_sha256', 'replacements'} and
                    record['before_sha256'] == BEFORE_SHA256,
                    name + ': exact installed health-actions byte-pin schema required')
            path = self.app / name
            require(not path.parent.is_symlink() and path.parent.is_dir(),
                    name + ': health-actions parent must be an ordinary source directory')
            require(path.is_file() and not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode),
                    name + ': health-actions target must be an ordinary source file')
            require(not path.stat().st_mode & 0o111,
                    name + ': canonical health-actions executable mode required')
            actual = path.read_bytes()
            require(sha256(actual) == record['after_sha256'],
                    name + ': only exact reviewed health-actions target bytes permitted')
            require(isinstance(record['replacements'], list) and record['replacements'],
                    name + ': nonempty reviewed health-actions replacements required')
            recovered = actual
            for pair in reversed(record['replacements']):
                require(isinstance(pair, list) and len(pair) == 2 and
                        all(isinstance(value, str) for value in pair),
                        name + ': exact health-actions replacement pair required')
                old, new = [value.encode('utf-8') for value in pair]
                require(old and new and old != new and recovered.count(new) == 1,
                        name + ': one exact reverse health-actions anchor required')
                recovered = recovered.replace(new, old, 1)
            require(sha256(recovered) == BEFORE_SHA256,
                    name + ': exact reversible installed health-actions preimage required')
            expected = recovered
            for old, new in record['replacements']:
                old, new = old.encode('utf-8'), new.encode('utf-8')
                require(expected.count(old) == 1,
                        name + ': one exact forward health-actions anchor required')
                expected = expected.replace(old, new, 1)
            require(expected == actual,
                    name + ': exact forward reviewed health-actions bytes required')
            self.preimages[name] = recovered
        self.paths = frozenset(PREFIX + name for name in MODIFIED)

    def before(self, name):
        require(isinstance(name, str) and all(part and part not in ('.', '..') for part in name.split('/')),
                'Health-actions source paths must be bounded')
        return self.preimages[name] if name in self.preimages else (self.app / name).read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    HealthActionsLayer(args.root)
    print('PASS: exact health-actions target and reversible installed preimage; current source unchanged')


if __name__ == '__main__':
    main()
