#!/usr/bin/env python3
"""Reverse the exact reviewed workflow follow-up before historical proofs.

Only the six existing public/navigation/push files are projected in memory.
ManualClockLayer composes these preimages with the immutable health, manual
clock and visual fixtures and verifies the complete original application.
No Git object beyond the already-required historical bases is introduced.
"""
from __future__ import print_function

import argparse
import hashlib
import json
from pathlib import Path
import stat
from welcome_home_source_layer import WelcomeLayer

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = '4b108316a3865dba8583b30ec0dd8e2eeae6968e'
BASE_TREE = 'd70ff1613567cbb5704124de5c64f302257c6c4a'
FIXTURE = 'tests/fixtures/workflow-followup-reviewed.json'
FIXTURE_SHA256 = 'd2dbdbeac5084842c98c37a5b3313ec5ce2ee42b3814a4972e1a0f40d4525807'
BEFORE_SHA256 = {
    'index.php': '6e6070b6bc2faeda02c64cf0bf225a37110aba38287b5be0c0c2e0f45b7eab1c',
    'admin/operations.php': '7528f1248d510df17a28449805a310234d48e7dbd89caf2d684792bd99f16ccc',
    'admin/push.php': 'f4e73fc165a37417f54dc1e072a2f95955f7813da1618a7cf4c0d1a87c1fbd84',
    'member/notifications.php': 'f0a86dbe7ec5c5994b14d657791dc35fe55e75bc420f7d5b2e8b6703f17e5ffc',
    'member/push-settings.js': 'f92ede20083b580ddce13f16c2ce0d3b17238774a5cd56b82d2690766a1a4c99',
    'sw.js': '547e555f9e9bd85bf290e6887eccfbeaceacb37c9b8905f3c74113e876f643a4',
}
MODIFIED = frozenset(BEFORE_SHA256)


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def bounded(name):
    return (isinstance(name, str) and
            all(part and part not in ('.', '..') for part in name.split('/')))


class WorkflowFollowupLayer:
    def __init__(self, root=ROOT, git_source=None):
        self.root = Path(root).resolve()
        self.app = self.root / PREFIX
        self.welcome = WelcomeLayer(self.root, git_source)
        require(self.app.is_dir() and not self.app.is_symlink(),
                'Workflow-followup application mount must be an ordinary source directory')
        raw = (self.root / FIXTURE).read_bytes()
        require(sha256(raw) == FIXTURE_SHA256,
                'Exact immutable workflow-followup fixture required')
        fixture = json.loads(raw)
        require(set(fixture) == {'source_commit', 'source_tree', 'modified'} and
                fixture['source_commit'] == BASE and fixture['source_tree'] == BASE_TREE,
                'Workflow-followup source context must remain pinned')
        require(set(fixture['modified']) == MODIFIED,
                'Workflow-followup fixture must enumerate exactly six reviewed existing files')
        self.preimages = {}
        for name, record in fixture['modified'].items():
            require(set(record) == {'before_sha256', 'after_sha256', 'replacements'} and
                    record['before_sha256'] == BEFORE_SHA256[name],
                    name + ': exact installed workflow-followup byte-pin schema required')
            path = self.app / name
            parent = self.app
            for part in name.split('/')[:-1]:
                parent = parent / part
                require(parent.is_dir() and not parent.is_symlink(),
                        name + ': workflow-followup parent must be an ordinary source directory')
            require(path.is_file() and not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode),
                    name + ': workflow-followup target must be an ordinary source file')
            require(not path.stat().st_mode & 0o111,
                    name + ': canonical workflow-followup executable mode required')
            actual = self.welcome.before(name)
            require(sha256(actual) == record['after_sha256'],
                    name + ': only exact reviewed workflow-followup target bytes permitted')
            require(isinstance(record['replacements'], list) and record['replacements'],
                    name + ': nonempty reviewed workflow-followup replacements required')
            recovered = actual
            for pair in reversed(record['replacements']):
                require(isinstance(pair, list) and len(pair) == 2 and
                        all(isinstance(value, str) for value in pair),
                        name + ': exact workflow-followup replacement pair required')
                old, new = [value.encode('utf-8') for value in pair]
                require(old and new and old != new and recovered.count(new) == 1,
                        name + ': one exact reverse workflow-followup anchor required')
                recovered = recovered.replace(new, old, 1)
            require(sha256(recovered) == BEFORE_SHA256[name],
                    name + ': exact reversible installed workflow-followup preimage required')
            expected = recovered
            for old, new in record['replacements']:
                old, new = old.encode('utf-8'), new.encode('utf-8')
                require(expected.count(old) == 1,
                        name + ': one exact forward workflow-followup anchor required')
                expected = expected.replace(old, new, 1)
            require(expected == actual,
                    name + ': exact forward reviewed workflow-followup bytes required')
            self.preimages[name] = recovered
        self.paths = frozenset(PREFIX + name for name in MODIFIED)

    def before(self, name):
        require(bounded(name), 'Workflow-followup source paths must be bounded')
        return self.preimages[name] if name in self.preimages else self.welcome.before(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    WorkflowFollowupLayer(args.root)
    print('PASS: six exact workflow-followup targets and reversible installed preimages; source unchanged')


if __name__ == '__main__':
    main()
