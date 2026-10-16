#!/usr/bin/env python3
"""Exact collaboration/payroll runtime layer over the signed phase-one release.

After the separately pinned visual/navigation layer is reversed, the complete
installed application must equal the exact reviewed delta over 9cf. Recovering
this layer preserves the first workflow fixture and every older source/route
proof. Current collaboration and payroll tests run separately.
No hosting, Git mutation, production delivery or private-record access occurs.
"""
from __future__ import print_function

import hashlib
import json
from pathlib import Path
import subprocess

from visual_source_layer import VisualLayer

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = '9cf2087ebc1608ea4fbf2f2a7cd68553de004964'
BASE_TREE = 'cf39c613b8c7f39c5cf8ce8da003a15f357ba292'
FIXTURE = 'tests/fixtures/phase-two-workflows-reviewed.json'
FIXTURE_SHA256 = '923654a8747ea42705e6b36365c7f54f05b59f365bc8cbf40b4fff38faa3af8e'
MODIFIED = frozenset(['admin/event-descriptions.js', 'admin/home.php', 'admin/index.php', 'admin/publication-designer.php', 'admin/publication-projects.php', 'admin/save.php', 'admin/timecards-export.php', 'admin/timecards-print.php', 'admin/timecards.php', 'admin/timeclock-period-close.php', 'config.example.php', 'lib/bootstrap.php', 'lib/operations-owner.php', 'member/index.php', 'member/prayer-care.php'])
NEW_FILES = frozenset(['admin/payroll-setup.php', 'admin/publishing-desk.js', 'api/team-workspace.php', 'lib/payroll.php', 'lib/publication-drafts.php', 'lib/team-workspace.php', 'member/work.php', 'member/workspace.css', 'member/workspace.js'])


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


class PhaseTwoLayer:
    def __init__(self, root=ROOT, git_source=None):
        self.root = Path(root).resolve()
        self.app = self.root / PREFIX
        self.git_source = Path(git_source or self.root).resolve()
        raw = (self.root / FIXTURE).read_bytes()
        require(sha256(raw) == FIXTURE_SHA256, 'Exact immutable phase-two fixture required')
        fixture = json.loads(raw)
        require(set(fixture) == {'source_commit', 'source_tree', 'modified', 'new_files'},
                'Phase-two fixture schema must remain bounded')
        require(fixture['source_commit'] == BASE and fixture['source_tree'] == BASE_TREE,
                'Phase-two baseline commit and full source tree must remain pinned')
        require(set(fixture['modified']) == MODIFIED and set(fixture['new_files']) == NEW_FILES,
                'Phase-two fixture must enumerate exactly the reviewed collaboration and payroll runtime files')
        require(self.git('rev-parse', BASE + '^{tree}').strip().decode('ascii') == BASE_TREE,
                'Canonical signed baseline commit must resolve to its reviewed source tree')
        tree = {}
        for entry in self.git('ls-tree', '-rz', '--full-tree', BASE, '--', PREFIX).split(b'\0'):
            if not entry:
                continue
            header, name = entry.split(b'\t', 1)
            mode, kind, oid = header.split()
            path = name.decode('utf-8')
            require(path.startswith(PREFIX) and kind == b'blob' and mode in (b'100644', b'100755'),
                    'Canonical application tree may contain only ordinary reviewed files')
            tree[path[len(PREFIX):]] = (mode.decode('ascii'), oid.decode('ascii'))
        require(MODIFIED <= set(tree) and not (NEW_FILES & set(tree)),
                'Modified and new phase-two files must have exact baseline membership')
        # Validate and reverse only the separately pinned visual/navigation
        # layer before applying the unchanged collaboration/payroll fixture.
        self.visual = VisualLayer(self.root, self.git_source)
        actual_paths = set(self.visual.baseline_tree)
        require(actual_paths == set(tree) | NEW_FILES,
                'Current application membership must be the exact phase-one baseline plus reviewed phase-two files')

        self.preimages = {}
        for name, record in fixture['modified'].items():
            require(set(record) == {'before_sha256', 'after_sha256', 'replacements'},
                    name + ': exact phase-two byte-pin schema required')
            before = self.git('show', BASE + ':' + PREFIX + name)
            require(sha256(before) == record['before_sha256'], name + ': exact phase-one canonical phase-two preimage required')
            expected = before
            for old, new in record['replacements']:
                old, new = old.encode('utf-8'), new.encode('utf-8')
                require(old and new and expected.count(old) == 1, name + ': one exact forward phase-two anchor required')
                expected = expected.replace(old, new, 1)
            actual = self.visual.before(name)
            require(actual == expected and sha256(actual) == record['after_sha256'],
                    name + ': only exact reviewed phase-two target bytes permitted')
            recovered = actual
            for old, new in reversed(record['replacements']):
                old, new = old.encode('utf-8'), new.encode('utf-8')
                require(recovered.count(new) == 1, name + ': one exact reverse phase-two anchor required')
                recovered = recovered.replace(new, old, 1)
            require(recovered == before, name + ': exact reversible phase-one canonical phase-two preimage required')
            self.preimages[name] = recovered
        for name, record in fixture['new_files'].items():
            require(set(record) == {'sha256', 'bytes'}, name + ': exact new-file byte-pin schema required')
            actual = self.visual.before(name)
            require(len(actual) == record['bytes'] and sha256(actual) == record['sha256'],
                    name + ': exact reviewed new phase-two file required')
        for name, (_, oid) in tree.items():
            if name not in MODIFIED:
                require(blob(self.visual.before(name)) == oid,
                        name + ': all runtime bytes outside the reviewed phase-two delta must remain phase-one canonical')
        self.paths = frozenset(PREFIX + name for name in MODIFIED | NEW_FILES)
        self.baseline_tree = tree

    def git(self, *args):
        return subprocess.check_output(['git', '--no-replace-objects', '-C', str(self.git_source)] + list(args))

    def before(self, name):
        require(name not in NEW_FILES, name + ': a new phase-two file has no historical preimage')
        return self.preimages[name] if name in self.preimages else self.visual.before(name)

    def copy_phase_one(self, destination):
        """Write a new isolated historical test application; never overwrite a path."""
        destination = Path(destination)
        require(not destination.exists(), 'Historical fixture destination must not already exist')
        self.visual.copy_baseline(destination)
        for name, data in self.preimages.items():
            (destination / name).write_bytes(data)
        for name in NEW_FILES:
            (destination / name).unlink()
        recovered = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
        require(recovered == set(self.baseline_tree), 'Phase-one route fixture must recover exact baseline membership')
        for name, (_, oid) in self.baseline_tree.items():
            require(blob((destination / name).read_bytes()) == oid, name + ': phase-one route fixture must recover exact bytes')
        return destination
