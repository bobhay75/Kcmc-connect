#!/usr/bin/env python3
"""Reverse the exact reviewed manual time-clock change before historical proofs.

After reversing the separately pinned workflow follow-up and health actions, the complete application
must equal the themed release plus five reviewed functional edits and the exact
owner-confirmed editorial occurrence. Recovered bytes are provided in memory;
historical source layers never read an unchecked current functional file.
No host, private records, Git mutation or application operation is performed.
"""
from __future__ import print_function

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess

from health_actions_source_layer import HealthActionsLayer
from workflow_followup_source_layer import WorkflowFollowupLayer

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = 'b0321c38d9750314c7d56896d3a818b6d7680228'
BASE_TREE = '1459efa57ff58ccd91d558e9141db10511c0e818'
BASE_APP_TREE = '3db33684b4eb70db5daaaf285facf9d83a54e8fe'
CANONICAL_BASE = 'b0c257edb8a42fc89fd6371c1bce7ee3efbd5ed9'
CANONICAL_TREE = '01decb86c93cf48862c6de7c0dbff4ba514f32cf'
VISUAL_FIXTURE = 'tests/fixtures/app-theme-navigation-reviewed.json'
VISUAL_FIXTURE_SHA256 = '2793614adc95f4b0119d0b1fd0a85872aca5a7bcdd9bf54ba66c3617e13d93f8'
FIXTURE = 'tests/fixtures/manual-clock-no-approvals-reviewed.json'
FIXTURE_SHA256 = '338f41cfb75e30fdda47bd01b1051d0be1c37785bd240a946cf0dbaed61bef52'
MODIFIED = frozenset([
    'admin/timecards-export.php',
    'admin/timecards-print.php',
    'admin/timecards.php',
    'lib/timeclock.php',
    'member/timeclock.php',
])


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


def app_tree_oid(files):
    """Compute Git's exact application subtree ID without creating objects."""
    root = {}
    for path, (mode, oid) in files.items():
        parts = path.split('/')
        require(all(part and part not in ('.', '..') for part in parts),
                'Canonical manual-clock application paths must be bounded')
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            require(isinstance(node, dict), 'Canonical manual-clock paths may not overlap')
        require(parts[-1] not in node, 'Canonical manual-clock paths must be unique')
        node[parts[-1]] = (mode, oid)

    def digest(node):
        raw = b''
        entries = sorted(node.items(), key=lambda item: item[0].encode('utf-8') +
                         (b'/' if isinstance(item[1], dict) else b''))
        for name, value in entries:
            mode, oid = ('40000', digest(value)) if isinstance(value, dict) else value
            raw += mode.encode('ascii') + b' ' + name.encode('utf-8') + b'\0' + bytes.fromhex(oid)
        return hashlib.sha1(b'tree ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()

    return digest(root)


class ManualClockLayer:
    def __init__(self, root=ROOT, git_source=None):
        self.root = Path(root).resolve()
        self.app = self.root / PREFIX
        self.git_source = Path(git_source or self.root).resolve()
        require(self.app.is_dir() and not self.app.is_symlink(),
                'Manual-clock application mount must be an ordinary source directory')
        self.workflow_followup = WorkflowFollowupLayer(self.root, self.git_source)
        self.health_actions = HealthActionsLayer(self.root)
        raw = (self.root / FIXTURE).read_bytes()
        require(sha256(raw) == FIXTURE_SHA256, 'Exact immutable manual-clock fixture required')
        fixture = json.loads(raw)
        require(set(fixture) == {'source_commit', 'source_tree', 'source_app_tree', 'modified'},
                'Manual-clock fixture schema must remain bounded')
        require(fixture['source_commit'] == BASE and fixture['source_tree'] == BASE_TREE and
                fixture['source_app_tree'] == BASE_APP_TREE,
                'Manual-clock baseline commit and complete source tree must remain pinned')
        require(set(fixture['modified']) == MODIFIED,
                'Manual-clock fixture must enumerate exactly the five reviewed functional files')
        # Existing historical jobs already fetch this canonical commit. Recover
        # the themed release from its immutable visual fixture instead of adding
        # an unrelated shallow-checkout Git dependency to every older workflow.
        require(self.git('rev-parse', CANONICAL_BASE + '^{tree}').strip().decode('ascii') == CANONICAL_TREE,
                'Canonical installed baseline must resolve to its exact reviewed source tree')
        tree = {}
        for entry in self.git('ls-tree', '-rz', '--full-tree', CANONICAL_BASE, '--', PREFIX).split(b'\0'):
            if not entry:
                continue
            header, name = entry.split(b'\t', 1)
            mode, kind, oid = header.split()
            path = name.decode('utf-8')
            require(path.startswith(PREFIX) and kind == b'blob' and mode in (b'100644', b'100755'),
                    'Canonical manual-clock application tree may contain only ordinary reviewed files')
            tree[path[len(PREFIX):]] = (mode.decode('ascii'), oid.decode('ascii'))
        visual_raw = (self.root / VISUAL_FIXTURE).read_bytes()
        require(sha256(visual_raw) == VISUAL_FIXTURE_SHA256,
                'Exact immutable visual/navigation fixture required before manual-clock projection')
        visual = json.loads(visual_raw)
        require(set(visual) == {'source_commit', 'source_tree', 'modified', 'new_files'} and
                visual['source_commit'] == CANONICAL_BASE and visual['source_tree'] == CANONICAL_TREE,
                'Manual-clock projection requires the exact canonical visual/navigation baseline')
        actual_paths = set()
        for path in self.app.rglob('*'):
            info = path.lstat()
            require(not stat.S_ISLNK(info.st_mode), 'Manual-clock application source may not add symbolic links')
            if stat.S_ISDIR(info.st_mode):
                continue
            require(stat.S_ISREG(info.st_mode), 'Manual-clock application source must contain ordinary files')
            actual_paths.add(path.relative_to(self.app).as_posix())
        from welcome_home_source_layer import ADDED
        actual_paths -= ADDED  # Each exact new asset was already hash-checked by WelcomeLayer.
        require(actual_paths == set(tree) | set(visual['new_files']),
                'Manual-clock application membership must equal the exact themed baseline')
        themed_bytes = {}
        for name, record in visual['modified'].items():
            require(name in tree, 'Reviewed visual/navigation modification must exist in canonical source')
            before = self.git('show', CANONICAL_BASE + ':' + PREFIX + name)
            require(sha256(before) == record['before_sha256'],
                    name + ': exact canonical visual/navigation preimage required')
            expected = before
            for old, new in record['replacements']:
                old, new = old.encode('utf-8'), new.encode('utf-8')
                require(old and new and old != new and expected.count(old) == 1,
                        name + ': one exact canonical visual/navigation forward anchor required')
                expected = expected.replace(old, new, 1)
            require(sha256(expected) == record['after_sha256'],
                    name + ': exact reconstructed visual/navigation target required')
            tree[name] = (tree[name][0], blob(expected))
            themed_bytes[name] = expected
        for name, record in visual['new_files'].items():
            require(name not in tree and record['mode'] in ('100644', '100755'),
                    name + ': exact new canonical visual/navigation file membership required')
            path = self.app / name
            require(path.is_file() and not path.is_symlink(),
                    'Manual-clock application source may not add symbolic links or omit reviewed providers')
            expected = path.read_bytes()
            require(len(expected) == record['bytes'] and sha256(expected) == record['sha256'],
                    name + ': exact reviewed new visual/navigation file required')
            tree[name] = (record['mode'], blob(expected))
        require(app_tree_oid(tree) == BASE_APP_TREE,
                'Reconstructed themed application must equal the pinned manual-clock baseline subtree')
        require(MODIFIED <= set(tree), 'All manual-clock changes must be existing canonical files')
        require(actual_paths == set(tree),
                'Manual-clock application membership must equal the exact themed baseline')

        self.preimages = {}
        for name, record in fixture['modified'].items():
            require(set(record) == {'before_sha256', 'after_sha256', 'replacements'},
                    name + ': exact manual-clock byte-pin schema required')
            before = themed_bytes[name] if name in themed_bytes else self.git('show', CANONICAL_BASE + ':' + PREFIX + name)
            require(sha256(before) == record['before_sha256'],
                    name + ': exact canonical manual-clock preimage required')
            expected = before
            require(isinstance(record['replacements'], list) and record['replacements'],
                    name + ': nonempty reviewed manual-clock replacements required')
            for pair in record['replacements']:
                require(isinstance(pair, list) and len(pair) == 2 and all(isinstance(s, str) for s in pair),
                        name + ': exact manual-clock replacement pair required')
                old, new = [value.encode('utf-8') for value in pair]
                require(old and new and old != new and expected.count(old) == 1,
                        name + ': one exact forward manual-clock anchor required')
                expected = expected.replace(old, new, 1)
            actual = self.post_clock_before(name)
            require(actual == expected and sha256(actual) == record['after_sha256'],
                    name + ': only exact reviewed manual-clock target bytes permitted')
            recovered = actual
            for old, new in reversed(record['replacements']):
                old, new = old.encode('utf-8'), new.encode('utf-8')
                require(recovered.count(new) == 1, name + ': one exact reverse manual-clock anchor required')
                recovered = recovered.replace(new, old, 1)
            require(recovered == before,
                    name + ': exact reversible themed manual-clock preimage required')
            self.preimages[name] = recovered
        for name, (mode, oid) in tree.items():
            require(bool((self.app / name).stat().st_mode & 0o111) == (mode == '100755'),
                    name + ': canonical manual-clock application executable mode required')
            if name == 'data/content.json':
                # Separate reviewed October 18 newsletter overlay; retain the exact clock baseline.
                require(oid == '141cff3397171c08e79e7e11c1b18e47633f1e4f', 'reviewed pre-study editorial baseline')
                actual = (self.app / name).read_bytes()
                require(blob(actual) == 'efee40e1152857a391491df7c4db2c1e11cc3228', 'only the exact reviewed October 18 newsletter content is permitted')
                self.editorial_preimage = self.git('show', CANONICAL_BASE + ':' + PREFIX + name)
                continue
            if name not in MODIFIED:
                require(blob(self.post_clock_before(name)) == oid,
                        name + ': all runtime bytes outside the reviewed manual-clock delta must remain themed canonical')
        self.paths = frozenset(PREFIX + name for name in MODIFIED)
        self.baseline_tree = tree

    def git(self, *args):
        return subprocess.check_output(['git', '--no-replace-objects', '-C', str(self.git_source)] + list(args))

    def post_clock_before(self, name):
        if name in self.health_actions.preimages:
            return self.health_actions.preimages[name]
        return self.workflow_followup.before(name)

    def before(self, name):
        require(name in self.baseline_tree, name + ': unknown manual-clock source path')
        if name == 'data/content.json':
            return self.editorial_preimage
        return self.preimages[name] if name in self.preimages else self.post_clock_before(name)

    def copy_baseline(self, destination):
        """Write a separate exact themed baseline; never overwrite a path."""
        destination = Path(destination)
        require(not destination.exists() and not destination.is_symlink(),
                'Manual-clock historical fixture destination must not already exist')
        shutil.copytree(str(self.app), str(destination))
        self.workflow_followup.welcome.restore_copy(destination)
        for name, data in self.workflow_followup.preimages.items():
            (destination / name).write_bytes(data)
        for name, data in self.health_actions.preimages.items():
            (destination / name).write_bytes(data)
        for name, data in self.preimages.items():
            (destination / name).write_bytes(data)
        (destination / 'data/content.json').write_bytes(self.editorial_preimage)
        recovered = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
        require(recovered == set(self.baseline_tree),
                'Manual-clock historical fixture must recover exact themed baseline membership')
        for name, (mode, oid) in self.baseline_tree.items():
            path = destination / name
            require(blob(path.read_bytes()) == oid,
                    name + ': manual-clock historical fixture must recover exact themed baseline bytes')
            require(bool(path.stat().st_mode & 0o111) == (mode == '100755'),
                    name + ': manual-clock historical fixture must recover exact themed executable mode')
        return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--git-source', type=Path)
    parser.add_argument('--baseline-output', type=Path)
    args = parser.parse_args()
    layer = ManualClockLayer(args.root, args.git_source)
    print('PASS: exact manual-clock fixture, complete themed membership and reversible functional bytes')
    if args.baseline_output:
        layer.copy_baseline(args.baseline_output)
        print('PASS: exact themed application reconstructed; current source unchanged')


if __name__ == '__main__':
    main()

