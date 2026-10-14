#!/usr/bin/env python3
"""Independent local real-Git metadata repair tests; no host/network calls."""
import sys
sys.dont_write_bytecode = True
import ast
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'repair.py'
SIDECAR = HERE / 'align-repository.py'
ENV = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
ENV.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
           GIT_AUTHOR_NAME='Synthetic', GIT_AUTHOR_EMAIL='synthetic@example.invalid',
           GIT_COMMITTER_NAME='Synthetic', GIT_COMMITTER_EMAIL='synthetic@example.invalid')

def module_at(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Fixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-mode-independent-')
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.repair = module_at(SOURCE, 'repair_test_instance')
        self.helper = module_at(SIDECAR, 'pinned_align_test_instance')
        self.paths = tuple(self.repair.PATHS)
        self.git('init', '--initial-branch=main')
        for name in self.paths:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('Synthetic public fixture for ' + name + '\n').encode())
            path.chmod(0o644)
        for number in range(255 - len(self.paths)):
            path = self.repo / ('unchanged-{:03d}.txt'.format(number))
            path.write_bytes(('unchanged fixture {}\n'.format(number)).encode())
            path.chmod(0o644)
        self.git('add', '.')
        self.git('commit', '-m', 'Synthetic baseline')
        self.head = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('remote', 'add', 'origin', self.helper.URL)
        self.helper.REPO = self.repo
        self.helper.BASELINE_IDS = (self.head,)
        self.helper.TARGET = 'f' * 40
        self.repair.REPO = self.repo
        self.repair.BASELINE = self.head
        self.repair.TARGET = self.helper.TARGET
        self.repair.UID, self.repair.GID = os.getuid(), os.getgid()
        self.repair.TRACKED_COUNT = 255
        self.repair.PRIVATE_ROOT = self.root / 'private'
        self.before = {name: (self.repo / name).read_bytes() for name in self.paths}
        self.index = (self.repo / '.git/index').read_bytes()
        self.config = (self.repo / '.git/config').read_bytes()
        for name in self.paths:
            (self.repo / name).chmod(0o664)

    def git(self, *arguments):
        return subprocess.check_output(['git', '-C', str(self.repo)] + list(arguments),
                                       env=ENV, stderr=subprocess.PIPE)

    def modes(self):
        return [stat.S_IMODE(os.lstat(str(self.repo / name)).st_mode) for name in self.paths]

    def call(self):
        output = io.StringIO()
        failure = None
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                value = self.repair.run('repair', helper=self.helper)
            except Exception as error:
                failure, value = error, None
        return value, failure, output.getvalue()

    def close(self):
        self.temp.cleanup()

class IndependentTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.addCleanup(self.f.close)

    def refused_unchanged(self):
        original = self.f.modes()
        value, failure, output = self.f.call()
        self.assertEqual(self.f.modes(), original)
        self.assertFalse(self.f.repair.PRIVATE_ROOT.exists())
        self.assertTrue(failure is not None or 'REFUSED' in output.upper(), (value, output))

    def test_clean_mode_only_repair(self):
        value, failure, output = self.f.call()
        self.assertIsNone(failure, (failure, output))
        self.assertEqual(self.f.modes(), [0o644] * 13)
        self.assertEqual(self.f.git('rev-parse', 'HEAD').decode().strip(), self.f.head)
        self.assertEqual((self.f.repo / '.git/index').read_bytes(), self.f.index)
        self.assertEqual((self.f.repo / '.git/config').read_bytes(), self.f.config)
        for name in self.f.paths:
            self.assertEqual((self.f.repo / name).read_bytes(), self.f.before[name])
        self.f.helper.clean(self.f.head)

    def test_tracked_content_edit(self):
        (self.f.repo / 'unchanged-000.txt').write_text('authored newer data\n')
        self.refused_unchanged()

    def test_staged_content_edit(self):
        (self.f.repo / 'unchanged-000.txt').write_text('staged newer data\n')
        self.f.git('add', 'unchanged-000.txt')
        self.refused_unchanged()

    def test_extra_file_mode(self):
        (self.f.repo / 'unchanged-000.txt').chmod(0o664)
        self.refused_unchanged()

    def test_mixed_allowlist_modes(self):
        (self.f.repo / self.f.paths[0]).chmod(0o644)
        self.refused_unchanged()

    def test_ignored_or_untracked_file(self):
        (self.f.repo / 'private-extra.json').write_text('PRIVATE_VALUE_MUST_NOT_PRINT\n')
        self.refused_unchanged()

    def test_ignored_file_refused(self):
        (self.f.repo / '.git/info/exclude').write_text('ignored-private.json\n')
        (self.f.repo / 'ignored-private.json').write_text('PRIVATE_IGNORED_VALUE\n')
        self.refused_unchanged()

    def test_skip_worktree_refused(self):
        self.f.git('update-index', '--skip-worktree', 'unchanged-000.txt')
        self.refused_unchanged()

    def test_symlink(self):
        path = self.f.repo / self.f.paths[0]
        path.unlink()
        path.symlink_to(self.f.root / 'private-target')
        value, failure, output = self.f.call()
        self.assertTrue(path.is_symlink())
        self.assertTrue(failure is not None or 'REFUSED' in output.upper(), (value, output))
        self.assertFalse(self.f.repair.PRIVATE_ROOT.exists())

    def test_secret_config_withheld(self):
        secret = 'PRIVATE_CREDENTIAL_VALUE_MUST_NOT_PRINT'
        self.f.git('remote', 'set-url', 'origin', 'https://' + secret + '@github.com/bobhay75/Kcmc-connect.git')
        original = self.f.modes()
        value, failure, output = self.f.call()
        self.assertEqual(self.f.modes(), original)
        self.assertNotIn(secret, output)
        self.assertFalse(self.f.repair.PRIVATE_ROOT.exists())

    def test_owned_failure_rolls_back(self):
        original_change = self.f.repair.change_mode
        calls = []
        def fail_second(fd, mode):
            calls.append(mode)
            if mode == 0o644 and calls.count(0o644) == 2:
                raise OSError(5, 'synthetic mode fault')
            return original_change(fd, mode)
        self.f.repair.change_mode = fail_second
        value, failure, output = self.f.call()
        self.assertEqual(self.f.modes(), [0o664] * 13, (failure, output))
        self.assertTrue(failure is not None or 'REFUSED' in output.upper(), (value, output))
        for name in self.f.paths:
            self.assertEqual((self.f.repo / name).read_bytes(), self.f.before[name])

    def test_concurrent_head_change_preserved(self):
        original_change = self.f.repair.change_mode
        changed = [False]
        def race(fd, mode):
            result = original_change(fd, mode)
            if mode == 0o644 and not changed[0]:
                changed[0] = True
                self.f.git('commit', '--allow-empty', '-m', 'Concurrent ref update')
            return result
        self.f.repair.change_mode = race
        value, failure, output = self.f.call()
        self.assertNotEqual(self.f.git('rev-parse', 'HEAD').decode().strip(), self.f.head)
        self.assertEqual(self.f.modes().count(0o644), 1, (failure, output))
        self.assertEqual(self.f.modes().count(0o664), 12, (failure, output))
        self.assertTrue(failure is not None or 'REVIEW' in output.upper(), (value, output))
        self.assertIn('manual review required', str(failure))

    def test_concurrent_config_change_preserved(self):
        original_change = self.f.repair.change_mode
        changed = [False]
        def race(fd, mode):
            result = original_change(fd, mode)
            if mode == 0o644 and not changed[0]:
                changed[0] = True
                self.f.git('config', 'user.name', 'Concurrent safe setting')
            return result
        self.f.repair.change_mode = race
        value, failure, output = self.f.call()
        self.assertEqual(self.f.git('config', 'user.name').decode().strip(), 'Concurrent safe setting')
        self.assertEqual(self.f.modes().count(0o644), 1, (failure, output))
        self.assertIn('manual review required', str(failure))

    def test_newer_file_bytes_preserved(self):
        original_change = self.f.repair.change_mode
        changed = [False]
        first = self.f.repo / self.f.paths[0]
        newer = b'Newer authored bytes must survive\n'
        def race(fd, mode):
            result = original_change(fd, mode)
            if mode == 0o644 and not changed[0]:
                changed[0] = True
                first.write_bytes(newer)
            return result
        self.f.repair.change_mode = race
        value, failure, output = self.f.call()
        self.assertEqual(first.read_bytes(), newer)
        self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o644)
        self.assertTrue(failure is not None or 'REVIEW' in output.upper(), (value, output))
        self.assertIn('manual review required', str(failure))
        self.assertNotIn('leased prior modes restored', str(failure))

    def test_rollback_failure_is_truthful(self):
        original_change = self.f.repair.change_mode
        calls = [0]
        def fail(fd, mode):
            if mode == 0o644:
                calls[0] += 1
                if calls[0] == 2:
                    raise OSError(5, 'synthetic apply fault')
            else:
                raise OSError(5, 'synthetic rollback fault')
            return original_change(fd, mode)
        self.f.repair.change_mode = fail
        value, failure, output = self.f.call()
        self.assertEqual(self.f.modes().count(0o644), 1)
        self.assertIn('manual review required', str(failure))
        self.assertNotIn('leased prior modes restored', str(failure))

    def test_already_repaired_has_no_journal_or_chmod(self):
        for name in self.f.paths:
            (self.f.repo / name).chmod(0o644)
        def forbidden(*arguments):
            raise AssertionError('Already-repaired state attempted chmod')
        self.f.repair.change_mode = forbidden
        value, failure, output = self.f.call()
        self.assertIsNone(failure, (failure, output))
        self.assertEqual(value['status'], 'already_repaired')
        self.assertFalse(self.f.repair.PRIVATE_ROOT.exists())

    def test_target_branch_read_only(self):
        for name in self.f.paths:
            (self.f.repo / name).chmod(0o644)
        self.f.repair.TARGET = self.f.head
        self.f.repair.BASELINE = 'e' * 40
        self.f.helper.TARGET = self.f.head
        def forbidden(*arguments):
            raise AssertionError('Target state attempted chmod')
        self.f.repair.change_mode = forbidden
        value, failure, output = self.f.call()
        self.assertIsNone(failure, (failure, output))
        self.assertEqual(value['status'], 'already_target')
        self.assertFalse(self.f.repair.PRIVATE_ROOT.exists())

    def test_git_control_group_preserved(self):
        target = str(self.f.repo / '.git/config')
        original_lstat, original_open, original_fstat = os.lstat, os.open, os.fstat
        control_fds = set()
        def different_group(info):
            values = {key: getattr(info, key) for key in dir(info) if key.startswith('st_')}
            values['st_gid'] = os.getgid() + 1
            return types.SimpleNamespace(**values)
        def fake_lstat(path, *arguments, **options):
            info = original_lstat(path, *arguments, **options)
            return different_group(info) if str(path) == target else info
        def wrapped_open(path, *arguments, **options):
            fd = original_open(path, *arguments, **options)
            if str(path) == target:
                control_fds.add(fd)
            return fd
        def fake_fstat(fd):
            info = original_fstat(fd)
            return different_group(info) if fd in control_fds else info
        with mock.patch.object(os, 'lstat', fake_lstat), mock.patch.object(os, 'open', wrapped_open), \
                mock.patch.object(os, 'fstat', fake_fstat):
            value, failure, output = self.f.call()
        self.assertIsNone(failure, (failure, output))
        self.assertEqual(self.f.modes(), [0o644] * 13)
        self.assertEqual((self.f.repo / '.git/config').read_bytes(), self.f.config)

if __name__ == '__main__':
    if sys.version_info >= (3, 8):
        ast.parse(SOURCE.read_text(), feature_version=(3, 6))
    else:
        ast.parse(SOURCE.read_text())
    unittest.main(verbosity=2)
