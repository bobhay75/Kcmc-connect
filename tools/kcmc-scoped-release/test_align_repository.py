#!/usr/bin/env python3
"""Temporary real-Git tests for repository-only cPanel alignment. No network."""
from __future__ import print_function
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE / 'align-repository.py'
if not DEFAULT_SOURCE.exists():
    DEFAULT_SOURCE = HERE / 'kcmc-repo-align-draft.py'


def load_helper():
    source = Path(os.environ.get('KCMC_ALIGN_SOURCE', str(DEFAULT_SOURCE)))
    spec = importlib.util.spec_from_file_location('kcmc_alignment_under_test', str(source))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_env():
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update({'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_SYSTEM': '/dev/null',
                'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0',
                'GIT_AUTHOR_NAME': 'Synthetic Alignment Test',
                'GIT_AUTHOR_EMAIL': 'alignment@example.invalid',
                'GIT_COMMITTER_NAME': 'Synthetic Alignment Test',
                'GIT_COMMITTER_EMAIL': 'alignment@example.invalid', 'LC_ALL': 'C'})
    return env


def run_git(directory, *args):
    return subprocess.check_output(['git', '-C', str(directory)] + list(args),
                                   cwd='/', env=fixture_env(), stderr=subprocess.PIPE)


def checked_out_snapshot(directory):
    result = {}
    for current, dirs, files in os.walk(str(directory), followlinks=False):
        if Path(current) == directory:
            dirs.remove('.git')
        for name in files:
            path = Path(current) / name
            info = os.lstat(str(path))
            data = ('link:' + os.readlink(str(path))).encode() if stat.S_ISLNK(info.st_mode) else path.read_bytes()
            result[str(path.relative_to(directory))] = (data, stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid)
    return result


def metadata_snapshot(directory):
    return {str(path.relative_to(directory)): (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            for path in (directory / '.git').rglob('*') if path.is_file() and not path.is_symlink()}


class AlignmentTests(unittest.TestCase):
    def setUp(self):
        old_umask = os.umask(0o022)
        self.addCleanup(os.umask, old_umask)
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-repo-align-test-')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.source = self.work / 'source'
        self.source.mkdir()
        run_git(self.source, 'init', '--initial-branch=main')
        (self.source / 'tracked.txt').write_text('Synthetic baseline\n')
        (self.source / '.gitignore').write_text('ignored.json\n')
        (self.source / 'bin').mkdir()
        (self.source / 'bin/review.sh').write_text('#!/bin/sh\nexit 0\n')
        (self.source / 'bin/review.sh').chmod(0o755)
        run_git(self.source, 'add', '.')
        run_git(self.source, 'commit', '-m', 'Synthetic baseline')
        self.base = run_git(self.source, 'rev-parse', 'HEAD').decode().strip()
        self.repo = self.work / 'checkout'
        run_git(self.work, 'clone', '--no-hardlinks', str(self.source), str(self.repo))
        self.module = load_helper()
        run_git(self.repo, 'remote', 'set-url', 'origin', self.module.URL)
        # The target does not exist in the checkout until the intercepted fetch.
        (self.source / 'tracked.txt').write_text('Synthetic repaired target\n')
        (self.source / 'new').mkdir()
        (self.source / 'new/repaired.txt').write_text('Synthetic added repair\n')
        run_git(self.source, 'add', '.')
        run_git(self.source, 'commit', '-m', 'Synthetic target')
        self.target = run_git(self.source, 'rev-parse', 'HEAD').decode().strip()
        self.module.REPO, self.module.BASE, self.module.TARGET = self.repo, self.base, self.target
        self.original_git = self.module.git
        self.fetch_calls = []
        self.fetch_failure = False
        self.after_fetch = None
        self.after_merge = None
        def intercepted_git(args, raw=False):
            if args and args[0] == 'fetch':
                self.assertFalse(raw)
                self.assertEqual(args, ['fetch', '--no-tags', '--no-recurse-submodules', '--no-write-fetch-head',
                                        '--no-auto-maintenance', self.module.URL, self.target])
                self.fetch_calls.append(list(args))
                if self.fetch_failure:
                    raise self.module.Refusal('Synthetic fetch failure')
                # The sole network operation is redirected to this fixture's
                # local source. File transport is enabled only in this test.
                command = ['git'] + self.module.OPTIONS + ['-c', 'protocol.file.allow=always', '-C', str(self.repo)]
                command += args[:-2] + [str(self.source), self.target]
                output = subprocess.check_output(command, cwd='/', env=self.module.environment(), stderr=subprocess.PIPE)
                if self.after_fetch:
                    self.after_fetch()
                return output
            output = self.original_git(args, raw=raw)
            if args and args[0] == 'merge' and self.after_merge:
                self.after_merge()
            return output
        self.module.git = intercepted_git

    def invoke(self, action):
        argv = sys.argv
        out, err = io.StringIO(), io.StringIO()
        try:
            sys.argv = ['kcmc-repo-align.py', action]
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = self.module.main()
        finally:
            sys.argv = argv
        return status, out.getvalue(), err.getvalue()

    def head(self):
        # Read the ordinary main ref directly so an unsafe config cannot affect
        # the preservation assertion or force the observer to load includes.
        return (self.repo / '.git/refs/heads/main').read_text().strip()

    def refuses_without_checkout_changes(self, label):
        before = checked_out_snapshot(self.repo)
        config = (self.repo / '.git/config').read_bytes()
        head = self.head()
        status, out, err = self.invoke('align')
        self.assertEqual(status, 1, label + ': ' + out + err)
        self.assertIn('REFUSED:', err)
        self.assertEqual(self.head(), head, label + ': HEAD preserved')
        self.assertEqual(checked_out_snapshot(self.repo), before, label + ': checkout preserved')
        self.assertEqual((self.repo / '.git/config').read_bytes(), config, label + ': config preserved')
        return out + err

    def test_clean_check_is_read_only(self):
        before = checked_out_snapshot(self.repo)
        metadata = metadata_snapshot(self.repo)
        status, out, err = self.invoke('check')
        self.assertEqual((status, err), (0, ''))
        self.assertIn('No files or refs changed', out)
        self.assertEqual(self.fetch_calls, [])
        self.assertEqual(self.head(), self.base)
        self.assertEqual(checked_out_snapshot(self.repo), before)
        self.assertEqual(metadata_snapshot(self.repo), metadata)

    def test_clean_align_is_pinned_fast_forward_without_deployment(self):
        marker = self.work / 'unexpected-hook'
        hook = self.repo / '.git/hooks/post-merge'
        hook.write_text('#!/bin/sh\nprintf "unexpected" > "' + str(marker) + '"\n')
        hook.chmod(0o755)
        config = (self.repo / '.git/config').read_bytes()
        status, out, err = self.invoke('align')
        self.assertEqual((status, err), (0, ''))
        self.assertIn('No live app deployment was invoked', out)
        self.assertEqual(len(self.fetch_calls), 1)
        self.assertEqual(self.head(), self.target)
        self.assertEqual((self.repo / 'tracked.txt').read_text(), 'Synthetic repaired target\n')
        self.assertEqual((self.repo / 'new/repaired.txt').read_text(), 'Synthetic added repair\n')
        self.assertFalse(marker.exists(), 'Git post-merge hook must not execute')
        self.assertEqual((self.repo / '.git/config').read_bytes(), config)
        self.assertFalse((self.repo / '.git/FETCH_HEAD').exists())
        self.module.clean(self.target)

    def test_tracked_edits_refuse_before_fetch(self):
        (self.repo / 'tracked.txt').write_text('Synthetic local edit\n')
        self.refuses_without_checkout_changes('tracked edit')
        self.assertEqual(self.fetch_calls, [])

    def test_staged_edits_refuse_before_fetch(self):
        (self.repo / 'tracked.txt').write_text('Synthetic staged edit\n')
        run_git(self.repo, 'add', 'tracked.txt')
        self.refuses_without_checkout_changes('staged edit')
        self.assertEqual(self.fetch_calls, [])

    def test_untracked_file_refuses_before_fetch(self):
        (self.repo / 'local-notes.txt').write_text('Synthetic local notes\n')
        self.refuses_without_checkout_changes('untracked file')
        self.assertEqual(self.fetch_calls, [])

    def test_ignored_file_refuses_before_fetch(self):
        (self.repo / 'ignored.json').write_text('{"synthetic": true}\n')
        self.refuses_without_checkout_changes('ignored file')
        self.assertEqual(self.fetch_calls, [])

    def test_unsafe_include_config_refuses_without_reading_include(self):
        external = self.work / 'unsafe-include'
        external.write_text('[this intentionally is not valid config\n')
        run_git(self.repo, 'config', 'include.path', str(external))
        self.refuses_without_checkout_changes('include configuration')
        self.assertEqual(self.fetch_calls, [])

    def test_unsafe_network_config_refuses(self):
        run_git(self.repo, 'config', 'http.sslVerify', 'false')
        self.refuses_without_checkout_changes('network override')
        self.assertEqual(self.fetch_calls, [])

    def test_unsafe_filter_config_refuses(self):
        run_git(self.repo, 'config', 'filter.synthetic.smudge', 'false')
        self.refuses_without_checkout_changes('conversion filter')
        self.assertEqual(self.fetch_calls, [])

    def test_unexpected_origin_refuses(self):
        run_git(self.repo, 'remote', 'set-url', 'origin', 'https://example.invalid/other.git')
        self.refuses_without_checkout_changes('unexpected origin')
        self.assertEqual(self.fetch_calls, [])

    def test_failed_fetch_preserves_checkout_and_head(self):
        self.fetch_failure = True
        self.refuses_without_checkout_changes('failed fetch')
        self.assertEqual(len(self.fetch_calls), 1)

    def test_edit_arriving_during_fetch_is_preserved(self):
        self.after_fetch = lambda: (self.repo / 'tracked.txt').write_text('Synthetic edit during fetch\n')
        status, _, err = self.invoke('align')
        self.assertEqual(status, 1)
        self.assertIn('REFUSED:', err)
        self.assertEqual(self.head(), self.base)
        self.assertEqual((self.repo / 'tracked.txt').read_text(), 'Synthetic edit during fetch\n')
        self.assertFalse((self.repo / 'new/repaired.txt').exists())

    def test_assume_unchanged_flag_refuses(self):
        run_git(self.repo, 'update-index', '--assume-unchanged', 'tracked.txt')
        self.refuses_without_checkout_changes('assume-unchanged index flag')
        self.assertEqual(self.fetch_calls, [])

    def test_nonstandard_tracked_mode_refuses(self):
        (self.repo / 'tracked.txt').chmod(0o600)
        self.refuses_without_checkout_changes('nonstandard tracked mode')
        self.assertEqual(self.fetch_calls, [])

    def test_tracked_symlink_refuses(self):
        original = self.repo / 'tracked.txt'
        replacement = self.work / 'synthetic-external'
        replacement.write_text(original.read_text())
        original.unlink()
        original.symlink_to(replacement)
        self.refuses_without_checkout_changes('tracked symlink')
        self.assertEqual(self.fetch_calls, [])

    def test_target_attributes_refuse_before_merge(self):
        (self.source / '.gitattributes').write_text('*.txt filter=synthetic\n')
        run_git(self.source, 'add', '.gitattributes')
        run_git(self.source, 'commit', '-m', 'Synthetic unsafe target attributes')
        self.target = run_git(self.source, 'rev-parse', 'HEAD').decode().strip()
        self.module.TARGET = self.target
        self.refuses_without_checkout_changes('target conversion attributes')
        self.assertEqual(len(self.fetch_calls), 1)

    def test_post_merge_verification_failure_reports_attempt_and_keeps_edits(self):
        self.after_merge = lambda: (self.repo / 'tracked.txt').write_text('Synthetic edit after merge\n')
        status, out, err = self.invoke('align')
        self.assertEqual(status, 1)
        self.assertIn('REVIEW REQUIRED: checkout update was attempted', err)
        self.assertNotIn('REFUSED:', err)
        self.assertEqual(self.head(), self.target)
        self.assertEqual((self.repo / 'tracked.txt').read_text(), 'Synthetic edit after merge\n')
        self.assertEqual((self.repo / 'new/repaired.txt').read_text(), 'Synthetic added repair\n')
        self.assertIn('no live app deployment was invoked', err)

    def test_restrictive_umask_still_produces_standard_target_modes(self):
        old = os.umask(0o027)
        try:
            status, out, err = self.invoke('align')
            restored = os.umask(old)
            os.umask(0o027)
            self.assertEqual(restored, 0o027, 'helper must restore caller umask')
        finally:
            os.umask(old)
        self.assertEqual((status, err), (0, ''), out + err)
        self.assertEqual(self.head(), self.target)
        self.assertEqual(stat.S_IMODE((self.repo / 'new/repaired.txt').stat().st_mode), 0o644)
        self.module.clean(self.target)


if __name__ == '__main__':
    unittest.main(verbosity=2)
