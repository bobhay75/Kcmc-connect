#!/usr/bin/env python3
"""Exact workflow source membership and reversible historical test preimages.

Current behavior is exercised by the member-account, timeclock and push route
suites. This module lets older proofs keep their original assertions against
the exact reviewed preimage instead of silently rewriting or skipping them.
It never edits the application, Git objects, a hosting checkout or private data.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from phase_two_source_layer import BASE as PHASE_ONE, PhaseTwoLayer

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = '00fdd469482564a3511a29a27a99502c24a32845'
BASE_TREE = '1514ea50168666853cb9f92e74a569a79f43eb24'
FIXTURE = 'tests/fixtures/workflow-journeys-reviewed.json'
FIXTURE_SHA256 = 'ff2f8054a00563bd96c9cf754e4c6cf1d8809eae9aa5b42c88317776dc6dae62'
HISTORICAL_PASSWORD_CONTRACT_SHA256 = '0008d242a8da3a80a7bf0a54f2e42c9a5c77ce77de7068c36fa88cffdabcc59d'
HISTORICAL_TIMECLOCK_CONTRACTS = {
    'timeclock-adjustment-contract.php': '70c126137f92a3b98f6390f1e7710a59bde3530c0c2ffe3096cf3e8624065ebb',
    'timeclock-mvp-contract.php': 'f11c9ef2e723a7996788f5feb15f8665cd546fcc26f6e138e94c67cc4b964400',
    'timeclock-correction-contract.php': 'ae46a392540c334dfe3ae7453c34db0c9035dad049a1f257f17c59e1bc7a9aff',
}
MODIFIED = frozenset([
    'admin/index.php', 'admin/prayers.php', 'admin/push.php', 'admin/timecards.php',
    'lib/push-subscriptions.php', 'lib/timeclock.php', 'member/index.php',
    'member/notifications.php', 'member/prayer-care.php', 'member/prayer-team.php',
    'member/push-settings.js', 'member/submit-prayer.php', 'member/timeclock.php',
])
NEW_FILES = frozenset([
    'admin/home.php', 'admin/prayer-care.php', 'admin/prayer-inbox.php',
    'admin/timeclock-period-close.php', 'member/prayers.php',
])


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


class Layer:
    def __init__(self, root=ROOT, git_source=None):
        self.root = Path(root).resolve()
        self.app = self.root / PREFIX
        self.git_source = Path(git_source or self.root).resolve()
        raw = (self.root / FIXTURE).read_bytes()
        require(sha256(raw) == FIXTURE_SHA256, 'Exact immutable workflow fixture required')
        fixture = json.loads(raw)
        require(set(fixture) == {'source_commit', 'source_tree', 'modified', 'new_files'},
                'Workflow fixture schema must remain bounded')
        require(fixture['source_commit'] == BASE and fixture['source_tree'] == BASE_TREE,
                'Workflow baseline commit and full source tree must remain pinned')
        require(set(fixture['modified']) == MODIFIED and set(fixture['new_files']) == NEW_FILES,
                'Workflow fixture must enumerate exactly thirteen modified and five new runtime files')
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
                'Modified and new workflow files must have exact baseline membership')
        # First recover the strictly pinned collaboration/payroll layer. Its
        # complete current-file membership and every runtime byte are checked;
        # the original workflow proof then sees exactly its phase-one target.
        self.phase_two = PhaseTwoLayer(self.root, self.git_source)
        actual_paths = set(self.phase_two.baseline_tree)
        require(actual_paths == set(tree) | NEW_FILES,
                'Current application membership must be the exact baseline plus five reviewed files')

        self.preimages = {}
        for name, record in fixture['modified'].items():
            require(set(record) == {'before_sha256', 'after_sha256', 'replacements'},
                    name + ': exact workflow byte-pin schema required')
            before = self.git('show', BASE + ':' + PREFIX + name)
            require(sha256(before) == record['before_sha256'], name + ': exact canonical workflow preimage required')
            expected = before
            for old, new in record['replacements']:
                old, new = old.encode('utf-8'), new.encode('utf-8')
                require(old and new and expected.count(old) == 1, name + ': one exact forward workflow anchor required')
                expected = expected.replace(old, new, 1)
            actual = self.phase_two.before(name)
            require(actual == expected and sha256(actual) == record['after_sha256'],
                    name + ': only exact reviewed workflow target bytes permitted')
            recovered = actual
            for old, new in reversed(record['replacements']):
                old, new = old.encode('utf-8'), new.encode('utf-8')
                require(recovered.count(new) == 1, name + ': one exact reverse workflow anchor required')
                recovered = recovered.replace(new, old, 1)
            require(recovered == before, name + ': exact reversible canonical workflow preimage required')
            self.preimages[name] = recovered
        for name, record in fixture['new_files'].items():
            require(set(record) == {'sha256', 'bytes'}, name + ': exact new-file byte-pin schema required')
            actual = self.phase_two.before(name)
            require(len(actual) == record['bytes'] and sha256(actual) == record['sha256'],
                    name + ': exact reviewed new workflow file required')
        for name, (_, oid) in tree.items():
            if name not in MODIFIED:
                require(blob(self.phase_two.before(name)) == oid,
                        name + ': all runtime bytes outside the reviewed workflow delta must remain canonical')
        self.paths = frozenset(PREFIX + name for name in MODIFIED | NEW_FILES)
        self.baseline_tree = tree

    def git(self, *args):
        return subprocess.check_output(['git', '--no-replace-objects', '-C', str(self.git_source)] + list(args))

    def before(self, name):
        require(name not in NEW_FILES, name + ': a new workflow file has no historical preimage')
        return self.preimages[name] if name in self.preimages else self.phase_two.before(name)

    def copy_baseline(self, destination):
        """Write a new isolated historical test application; never overwrite a path."""
        destination = Path(destination)
        require(not destination.exists(), 'Historical fixture destination must not already exist')
        self.phase_two.copy_phase_one(destination)
        for name, data in self.preimages.items():
            (destination / name).write_bytes(data)
        for name in NEW_FILES:
            (destination / name).unlink()
        recovered = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
        require(recovered == set(self.baseline_tree), 'Historical route fixture must recover exact baseline membership')
        for name, (_, oid) in self.baseline_tree.items():
            require(blob((destination / name).read_bytes()) == oid, name + ': historical route fixture must recover exact bytes')
        return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--git-source', type=Path)
    parser.add_argument('--baseline-output', type=Path)
    parser.add_argument('--phase-one-output', type=Path)
    parser.add_argument('--historical-password-contract', action='store_true')
    parser.add_argument('--historical-timeclock-contracts', action='store_true')
    args = parser.parse_args()
    layer = Layer(args.root, args.git_source)
    print('PASS: exact visual, phase-two and workflow fixtures, canonical tree memberships and reversible runtime bytes')
    if args.phase_one_output:
        layer.phase_two.copy_phase_one(args.phase_one_output)
        print('PASS: exact phase-one application reconstructed; current source unchanged')
    if args.baseline_output:
        layer.copy_baseline(args.baseline_output)
        print('PASS: isolated exact historical application reconstructed; production source unchanged')
    if args.historical_password_contract:
        raw = layer.git('show', BASE + ':tests/password-lifecycle-contract.php')
        require(sha256(raw) == HISTORICAL_PASSWORD_CONTRACT_SHA256,
                'Historical password contract must remain byte-identical to its signed source')
        with tempfile.TemporaryDirectory(prefix='kcmc-workflow-password-history-') as directory:
            root = Path(directory)
            layer.copy_baseline(root / PREFIX)
            tests = root / 'tests'
            tests.mkdir()
            contract = tests / 'password-lifecycle-contract.php'
            contract.write_bytes(raw)
            php = os.environ.get('KCMC_TEST_PHP', 'php')
            env = {key: value for key, value in os.environ.items() if not key.startswith('KCMC_')}
            print('Historical password lifecycle: exact original contract and workflow preimage', flush=True)
            subprocess.check_call([php, str(contract)], env=env)
    if args.historical_timeclock_contracts:
        with tempfile.TemporaryDirectory(prefix='kcmc-phase-one-clock-history-') as directory:
            root = Path(directory)
            layer.phase_two.copy_phase_one(root / PREFIX)
            tests = root / 'tests'
            tests.mkdir()
            php = os.environ.get('KCMC_TEST_PHP', 'php')
            env = {key: value for key, value in os.environ.items() if not key.startswith('KCMC_')}
            for name, expected_sha in sorted(HISTORICAL_TIMECLOCK_CONTRACTS.items()):
                raw = layer.git('show', PHASE_ONE + ':tests/' + name)
                require(sha256(raw) == expected_sha, name + ': historical phase-one timeclock contract must remain exact')
                contract = tests / name
                contract.write_bytes(raw)
                print('Historical phase-one timeclock contract: ' + name, flush=True)
                subprocess.check_call([php, str(contract)], env=env)


if __name__ == '__main__':
    main()
