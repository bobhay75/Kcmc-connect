#!/usr/bin/env python3
"""Exact reversible navy/gold and navigation layer over the installed release.

The complete current application is checked against the reviewed b0c tree.
Historical proofs consume its recovered preimage; current browser acceptance
exercises the themed application separately. No host or private data is read.
"""
from __future__ import print_function

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = 'b0c257edb8a42fc89fd6371c1bce7ee3efbd5ed9'
BASE_TREE = '01decb86c93cf48862c6de7c0dbff4ba514f32cf'
FIXTURE = 'tests/fixtures/app-theme-navigation-reviewed.json'
FIXTURE_SHA256 = 'a4f71af8bc7b35b27a172f243ec255674d5c551de9175433679ee077053a1fb9'
MODIFIED = frozenset(['admin/audit.php', 'admin/connections.php', 'admin/event-create.php', 'admin/health.php', 'admin/home.php', 'admin/index.php', 'admin/operations.php', 'admin/password-resets.php', 'admin/payroll-setup.php', 'admin/posts.php', 'admin/prayer-inbox.php', 'admin/prayers.php', 'admin/publication-designer.php', 'admin/push.php', 'admin/restore.php', 'admin/rsvps.php', 'admin/save.php', 'admin/setup.php', 'admin/timecards-print.php', 'admin/timecards.php', 'admin/users.php', 'backpack-blessing.php', 'bulletin.php', 'care.php', 'connect.php', 'events.php', 'index.php', 'lib/bootstrap.php', 'lib/payroll.php', 'member/activate.php', 'member/first-login.php', 'member/index.php', 'member/login.php', 'member/logout.php', 'member/notifications.php', 'member/password.php', 'member/prayer-care.php', 'member/prayer-team.php', 'member/prayers.php', 'member/reset-password.php', 'member/submit-prayer.php', 'member/timeclock.php', 'member/work.php'])
NEW_FILES = frozenset(['app-navigation.js', 'app-theme.css', 'lib/screen-navigation.php'])


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


class VisualLayer:
    def __init__(self, root=ROOT, git_source=None):
        self.root = Path(root).resolve()
        self.app = self.root / PREFIX
        self.git_source = Path(git_source or self.root).resolve()
        raw = (self.root / FIXTURE).read_bytes()
        require(sha256(raw) == FIXTURE_SHA256, 'Exact immutable visual/navigation fixture required')
        fixture = json.loads(raw)
        require(set(fixture) == {'source_commit', 'source_tree', 'modified', 'new_files'},
                'Visual/navigation fixture schema must remain bounded')
        require(fixture['source_commit'] == BASE and fixture['source_tree'] == BASE_TREE,
                'Visual/navigation baseline commit and complete source tree must remain pinned')
        require(set(fixture['modified']) == MODIFIED and set(fixture['new_files']) == NEW_FILES,
                'Visual/navigation fixture must enumerate exactly the reviewed runtime files')
        require(self.git('rev-parse', BASE + '^{tree}').strip().decode('ascii') == BASE_TREE,
                'Canonical installed baseline must resolve to its exact reviewed source tree')
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
                'Visual/navigation modified and new files must have exact baseline membership')
        actual_paths = set()
        for path in self.app.rglob('*'):
            info = path.lstat()
            require(not stat.S_ISLNK(info.st_mode), 'Application source may not add symbolic links')
            if stat.S_ISDIR(info.st_mode):
                continue
            require(stat.S_ISREG(info.st_mode), 'Application source must contain ordinary files')
            actual_paths.add(path.relative_to(self.app).as_posix())
        require(actual_paths == set(tree) | NEW_FILES,
                'Current application membership must be the exact installed baseline plus reviewed visual/navigation files')

        self.preimages = {}
        for name, record in fixture['modified'].items():
            require(set(record) == {'before_sha256', 'after_sha256', 'replacements'},
                    name + ': exact visual/navigation byte-pin schema required')
            before = self.git('show', BASE + ':' + PREFIX + name)
            require(sha256(before) == record['before_sha256'],
                    name + ': exact canonical visual/navigation preimage required')
            expected = before
            for pair in record['replacements']:
                require(isinstance(pair, list) and len(pair) == 2 and all(isinstance(s, str) for s in pair),
                        name + ': exact visual/navigation replacement pair required')
                old, new = [value.encode('utf-8') for value in pair]
                require(old and new and old != new and expected.count(old) == 1,
                        name + ': one exact forward visual/navigation anchor required')
                expected = expected.replace(old, new, 1)
            actual = (self.app / name).read_bytes()
            require(actual == expected and sha256(actual) == record['after_sha256'],
                    name + ': only exact reviewed visual/navigation target bytes permitted')
            recovered = actual
            for old, new in reversed(record['replacements']):
                old, new = old.encode('utf-8'), new.encode('utf-8')
                require(recovered.count(new) == 1, name + ': one exact reverse visual/navigation anchor required')
                recovered = recovered.replace(new, old, 1)
            require(recovered == before, name + ': exact reversible installed visual/navigation preimage required')
            self.preimages[name] = recovered
        for name, record in fixture['new_files'].items():
            require(set(record) == {'sha256', 'bytes', 'mode'}, name + ': exact new visual/navigation file schema required')
            actual = (self.app / name).read_bytes()
            require(record['mode'] in ('100644', '100755') and len(actual) == record['bytes'] and sha256(actual) == record['sha256'],
                    name + ': exact reviewed new visual/navigation file required')
        for name, (mode, oid) in tree.items():
            require(bool((self.app / name).stat().st_mode & 0o111) == (mode == '100755'),
                    name + ': canonical application executable mode required')
            if name not in MODIFIED:
                require(blob((self.app / name).read_bytes()) == oid,
                        name + ': all runtime bytes outside the reviewed visual/navigation delta must remain installed canonical')
        for name, record in fixture['new_files'].items():
            require(bool((self.app / name).stat().st_mode & 0o111) == (record['mode'] == '100755'),
                    name + ': reviewed new visual/navigation executable mode required')
        self.paths = frozenset(PREFIX + name for name in MODIFIED | NEW_FILES)
        self.baseline_tree = tree

    def git(self, *args):
        return subprocess.check_output(['git', '--no-replace-objects', '-C', str(self.git_source)] + list(args))

    def before(self, name):
        require(name not in NEW_FILES, name + ': a new visual/navigation file has no installed preimage')
        return self.preimages[name] if name in self.preimages else (self.app / name).read_bytes()

    def copy_baseline(self, destination):
        """Write a new exact historical application; never overwrite a path."""
        destination = Path(destination)
        require(not destination.exists(), 'Historical fixture destination must not already exist')
        shutil.copytree(str(self.app), str(destination))
        for name, data in self.preimages.items():
            (destination / name).write_bytes(data)
        for name in NEW_FILES:
            (destination / name).unlink()
        recovered = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
        require(recovered == set(self.baseline_tree), 'Installed route fixture must recover exact baseline membership')
        for name, (_, oid) in self.baseline_tree.items():
            require(blob((destination / name).read_bytes()) == oid,
                    name + ': installed route fixture must recover exact bytes')
        return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--git-source', type=Path)
    parser.add_argument('--baseline-output', type=Path)
    args = parser.parse_args()
    layer = VisualLayer(args.root, args.git_source)
    print('PASS: exact visual/navigation fixture, complete installed membership and reversible runtime bytes')
    if args.baseline_output:
        layer.copy_baseline(args.baseline_output)
        print('PASS: exact installed application reconstructed; current source unchanged')


if __name__ == '__main__':
    main()
