#!/usr/bin/env python3
"""Temporary-directory tests of the scoped installer; no host/network access.

Python 3.6-compatible. The installer is imported, its roots and fetch/lint/HTTP
dependencies are replaced, and every write is confined to an isolated fixture.
"""
from __future__ import print_function

import hashlib
import importlib.util
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest
from unittest import mock


INSTALLER = Path(__file__).resolve().with_name('installer.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-installer-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.live = self.root / 'app'
        self.backups = self.root / 'private-backups'
        self.live.mkdir()
        environment = mock.patch.dict(os.environ, {'KCMC_PRIVATE_DATA_DIR': ''})
        environment.start()
        self.addCleanup(environment.stop)
        spec = importlib.util.spec_from_file_location('synthetic_installer', str(INSTALLER))
        self.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.installer)
        self.before = {
            'index.php': b'<?php echo "Original page"; ?>\n',
            'public-presentation.js': b'window.fixture = "original";\n',
            'sw.js': b'// original service worker\n',
            'admin/publication-media.php': None,
        }
        self.after = {
            'index.php': b'<?php echo "Reviewed page"; ?>\n',
            'public-presentation.js': b'window.fixture = "reviewed";\n',
            'sw.js': b'// reviewed service worker\n',
            'admin/publication-media.php': b'<?php echo "Synthetic media endpoint"; ?>\n',
        }
        self.original_modes = {'index.php': 0o640, 'public-presentation.js': 0o644, 'sw.js': 0o600}
        for path, data in self.before.items():
            target = self.live / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if data is not None:
                target.write_bytes(data)
                target.chmod(self.original_modes[path])
        self.guards = {
            'admin/index.php': b'<?php /* unchanged Publishing Desk */ ?>\n',
            'data/content.json': b'{"synthetic":"editorial content stays private"}\n',
            'data/private/users.json': b'{"synthetic":"no real accounts"}\n',
        }
        for path, data in self.guards.items():
            target = self.live / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o600)
        self.publisher = self.live / 'data/private'
        self.publisher.mkdir(parents=True, exist_ok=True)
        for name in ('publications.json', 'publication-media.json'):
            lock = self.publisher / (name + '.lock')
            lock.write_bytes(b'')
            lock.chmod(0o640)
        self.installer.APP_ROOT = self.live
        self.installer.COMMIT = 'f' * 40
        self.installer.SOURCE_ROOT = 'https://raw.githubusercontent.com/bobhay75/Kcmc-connect/' + self.installer.COMMIT + '/KCMC-Connect-Phase6-Recreated/'
        self.installer.BACKUP_ROOT = self.backups
        self.installer.FILES = {
            path: {'sha256': digest(data), 'bytes': len(data),
                   'baseline_sha256': None if self.before[path] is None else digest(self.before[path])}
            for path, data in self.after.items()
        }
        self.installer.GUARDS = {path: digest(data) for path, data in self.guards.items()}
        self.installer.BASELINE_EXPECTATIONS = {
            path: {'bytes': len(data), 'mode': self.original_modes[path]}
            for path, data in self.before.items() if data is not None
        }
        self.installer.GIT_SHAS = {
            path: hashlib.sha1(('blob ' + str(len(data)) + '\0').encode('ascii') + data).hexdigest()
            for path, data in self.after.items()
        }
        old_id, previous_id = self.installer.BASELINE_IDS
        self.installer.BASELINES = {
            old_id: {path: None if data is None else {'sha256': digest(data), 'bytes': len(data),
                     'mode': self.original_modes[path]} for path, data in self.before.items()},
            previous_id: {path: {'sha256': digest(data), 'bytes': len(data), 'mode': 0o644}
                          for path, data in self.after.items()},
        }
        self.fetches, self.lints, self.http_calls = [], [], []

        def fetch(path):
            self.fetches.append(path)
            return self.after[path]

        def lint(records):
            self.lints.append(records)

        def verify_http():
            self.http_calls.append(True)
            self.assert_release_bytes()

        self.real_fetch = self.installer.fetch_bytes
        self.real_lint = self.installer.lint_staged
        self.real_http = self.installer.verify_http
        self.installer.fetch_bytes = fetch
        self.installer.lint_staged = lint
        self.installer.verify_http = verify_http
        self.atomic = self.installer.atomic_replace
        self.writes = []

        def observed_replace(src, dst, **kwargs):
            target = self.replace_target(dst, kwargs)
            if self.live in target.parents:
                self.writes.append(str(target.relative_to(self.live)))
            return self.atomic(src, dst, **kwargs)

        self.installer.atomic_replace = observed_replace

    def replace_target(self, dst, kwargs):
        target = Path(dst)
        directory_fd = kwargs.get('dst_dir_fd')
        if directory_fd is not None and not target.is_absolute():
            target = Path(os.readlink('/proc/self/fd/' + str(directory_fd))) / target
        return target

    def add_release_file(self, path, old, new):
        self.before[path], self.after[path] = old, new
        target = self.live / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if old is not None:
            target.write_bytes(old)
            target.chmod(0o644)
            self.original_modes[path] = 0o644
            self.installer.BASELINE_EXPECTATIONS[path] = {'bytes': len(old), 'mode': 0o644}
        self.installer.FILES[path] = {'sha256': digest(new), 'bytes': len(new),
                                      'baseline_sha256': None if old is None else digest(old)}
        self.installer.GIT_SHAS[path] = hashlib.sha1(('blob ' + str(len(new)) + '\0').encode('ascii') + new).hexdigest()
        old_id, previous_id = self.installer.BASELINE_IDS
        self.installer.BASELINES[old_id][path] = None if old is None else {'sha256': digest(old), 'bytes': len(old), 'mode': 0o644}
        self.installer.BASELINES[previous_id][path] = {'sha256': digest(new), 'bytes': len(new), 'mode': 0o644}

    def activate_previous_release(self):
        previous = dict(self.after)
        self.before = previous
        self.original_modes = {path: 0o644 for path in previous}
        for path, data in previous.items():
            target = self.live / path
            target.write_bytes(data)
            target.chmod(0o644)
            future = data + b'\n/* synthetic Oct 8 approved repair */\n'
            self.after[path] = future
            self.installer.FILES[path]['sha256'] = digest(future)
            self.installer.FILES[path]['bytes'] = len(future)
            self.installer.GIT_SHAS[path] = hashlib.sha1(('blob ' + str(len(future)) + '\0').encode('ascii') + future).hexdigest()

    def http_fixture(self, bad_static=None, bad_admin=None):
        seen = []
        module = self.installer
        markers = b'data-contemporary-feature kcmc-congregation-gathering.jpg kcmc-bridge-wordmark.png public-presentation.css public-presentation.js'

        class Response(object):
            status = 200

            def __init__(inner, url, body):
                inner.url, inner.body = url, body

            def __enter__(inner):
                return inner

            def __exit__(inner, *args):
                pass

            def geturl(inner):
                return inner.url

            def read(inner, limit):
                return inner.body[:limit]

        def opened(request, **kwargs):
            url = request.full_url
            self.assertTrue(url.startswith(module.PUBLIC_ROOT))
            path = url[len(module.PUBLIC_ROOT):]
            seen.append(path)
            if path == '':
                return Response(url, markers)
            if path.startswith('admin/'):
                destination = url if path == bad_admin else module.PUBLIC_ROOT + 'member/login.php?next=synthetic'
                return Response(destination, b'Staff Sign In')
            if path == 'member/login.php':
                return Response(url, b'Staff Sign In')
            body = self.after[path]
            if path == bad_static:
                body = b'X' * len(body)
            return Response(url, body)

        return opened, seen

    def live_snapshot(self):
        snapshot = {}
        for target in sorted(self.live.rglob('*')):
            if target.is_symlink():
                snapshot[str(target.relative_to(self.live))] = ('link', os.readlink(str(target)))
            elif target.is_file():
                info = target.stat()
                snapshot[str(target.relative_to(self.live))] = (
                    target.read_bytes(), stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid)
        return snapshot

    def assert_release_bytes(self):
        for path, data in self.after.items():
            self.assertEqual((self.live / path).read_bytes(), data, path)

    def assert_baseline(self):
        for path, data in self.before.items():
            target = self.live / path
            if data is None:
                self.assertFalse(target.exists(), 'previously absent target must remain absent: ' + path)
            else:
                self.assertEqual(target.read_bytes(), data, path)
                self.assertEqual(mode(target), self.original_modes[path], path)
        for path, data in self.guards.items():
            self.assertEqual((self.live / path).read_bytes(), data, path)

    def prepare(self):
        return Path(self.installer.prepare())

    def test_prepare_is_read_only_and_backups_are_exact_and_private(self):
        initial = self.live_snapshot()
        session = self.prepare()
        self.assertEqual(self.live_snapshot(), initial)
        self.assertEqual(set(self.fetches), set(self.after))
        self.assertTrue(self.lints, 'prepare must lint its staged code')
        self.assertEqual(mode(self.backups), 0o700)
        self.assertEqual(mode(session), 0o700)
        protected_backup = session / 'originals/data/content.json'
        self.assertEqual(protected_backup.read_bytes(), self.guards['data/content.json'])
        self.assertEqual(mode(protected_backup), 0o600)
        for path, data in self.after.items():
            stage = session / 'stage' / path
            self.assertEqual(stage.read_bytes(), data)
            self.assertEqual(digest(stage.read_bytes()), self.installer.FILES[path]['sha256'])
            self.assertEqual(mode(stage), 0o600)
            old = session / 'originals' / path
            if self.before[path] is None:
                self.assertFalse(old.exists(), 'missing baseline must not become an empty backup')
            else:
                self.assertEqual(old.read_bytes(), self.before[path])
                self.assertEqual(mode(old), 0o600)
        for path in session.rglob('*'):
            self.assertFalse(path.is_symlink())
            if path.is_dir():
                self.assertEqual(mode(path), 0o700, str(path))
            elif path.is_file():
                self.assertEqual(mode(path), 0o600, str(path))
        self.assertFalse(self.writes, 'prepare must not replace any live file')

    def test_apply_preserves_modes_and_ownership_and_installs_worker_last(self):
        original_owners = {path: ((self.live / path).stat().st_uid, (self.live / path).stat().st_gid)
                           for path, data in self.before.items() if data is not None}
        session = self.prepare()
        self.installer.apply(session=str(session))
        self.assert_release_bytes()
        self.assertEqual(self.writes[-1], 'sw.js', 'service worker must activate only after other files')
        self.assertEqual(set(self.writes), set(self.after))
        self.assertTrue(self.http_calls, 'installed release must receive read-only HTTP verification')
        for path, expected in self.original_modes.items():
            self.assertEqual(mode(self.live / path), expected, path)
            info = (self.live / path).stat()
            self.assertEqual((info.st_uid, info.st_gid), original_owners[path], path)
        self.assertEqual(mode(self.live / 'admin/publication-media.php'), 0o644)
        for path, data in self.guards.items():
            self.assertEqual((self.live / path).read_bytes(), data, path)

    def test_baseline_drift_refuses_before_live_writes(self):
        (self.live / 'public-presentation.js').write_bytes(b'// unreviewed host edit\n')
        drifted = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), drifted)
        self.assertFalse(self.writes)

    def test_guard_drift_refuses_before_live_writes(self):
        (self.live / 'data/content.json').write_bytes(b'{"changed":"staff edit"}\n')
        drifted = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), drifted)
        self.assertFalse(self.writes)

    def test_missing_expected_baseline_is_refused(self):
        (self.live / 'index.php').unlink()
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_unexpected_file_at_missing_baseline_is_refused(self):
        (self.live / 'admin/publication-media.php').write_bytes(b'<?php /* host-only endpoint */ ?>')
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_download_hash_mismatch_refuses_before_live_writes(self):
        before = self.live_snapshot()
        good_fetch = self.installer.fetch_bytes
        self.installer.fetch_bytes = lambda path: b'X' * len(self.after[path]) if path == 'index.php' else good_fetch(path)
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_missing_linter_refuses_before_live_writes(self):
        before = self.live_snapshot()

        def no_linter(records):
            raise RuntimeError('Synthetic PHP/Node lint unavailable')

        self.installer.lint_staged = no_linter
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_real_lint_discovery_requires_php82_and_checks_php_and_js(self):
        records = [{'path': 'index.php', 'staged': '/synthetic/stage/index.php'},
                   {'path': 'public-presentation.js', 'staged': '/synthetic/stage/public-presentation.js'}]
        calls = []

        def executable(name):
            return {'php8.2': '/synthetic/php82', 'node': '/synthetic/node'}.get(name)

        with mock.patch.object(self.installer.os.path, 'isfile', return_value=False), \
                mock.patch.object(self.installer.shutil, 'which', side_effect=executable), \
                mock.patch.object(self.installer.subprocess, 'check_output', return_value=b'80230'), \
                mock.patch.object(self.installer.subprocess, 'check_call', side_effect=lambda cmd, **kw: calls.append(cmd)), \
                mock.patch('builtins.print'):
            self.real_lint(records)
        self.assertIn(['/synthetic/php82', '-l', '/synthetic/stage/index.php'], calls)
        self.assertIn(['/synthetic/node', '--check', '/synthetic/stage/public-presentation.js'], calls)
        self.assertTrue(any(cmd[:2] == ['/synthetic/php82', '-r'] and
                            'finfo_open' in cmd[2] and 'getimagesize' in cmd[2] for cmd in calls))

    def test_real_lint_discovery_refuses_missing_or_wrong_php_engine(self):
        for version in [None, b'70333', b'80300']:
            with self.subTest(version=version):
                with mock.patch.object(self.installer.os.path, 'isfile', return_value=False), \
                        mock.patch.object(self.installer.shutil, 'which', return_value=None if version is None else '/synthetic/php'), \
                        mock.patch.object(self.installer.subprocess, 'check_output', return_value=version), \
                        mock.patch.object(self.installer.subprocess, 'check_call') as command:
                    with self.assertRaises(Exception):
                        self.real_lint([])
                    command.assert_not_called()

    def test_real_fetch_uses_immutable_source_and_verifies_exact_bytes(self):
        wanted_url = self.installer.SOURCE_ROOT + 'index.php'
        self.assertIn('/' + self.installer.COMMIT + '/', wanted_url)
        self.assertEqual(len(self.installer.COMMIT), 40)
        desired = self.after['index.php']
        requests = []

        class Response(object):
            status = 200

            def __enter__(inner):
                return inner

            def __exit__(inner, *args):
                pass

            def geturl(inner):
                return wanted_url

            def read(inner, limit):
                self.assertEqual(limit, len(desired) + 1)
                return desired

        def opened(request, **kwargs):
            requests.append(request.full_url)
            return Response()

        with mock.patch.object(self.installer.urllib.request, 'urlopen', side_effect=opened):
            self.assertEqual(self.real_fetch('index.php'), desired)
        self.assertEqual(requests, [wanted_url])

    def test_real_fetch_refuses_redirect_or_hash_mismatch(self):
        wanted_url = self.installer.SOURCE_ROOT + 'index.php'
        good = self.after['index.php']

        class Response(object):
            status = 200

            def __enter__(inner):
                return inner

            def __exit__(inner, *args):
                pass

            def geturl(inner):
                return inner.url

            def read(inner, limit):
                return inner.body

        for redirected in [True, False]:
            with self.subTest(redirected=redirected):
                response = Response()
                response.url = wanted_url + '?unreviewed' if redirected else wanted_url
                response.body = good if redirected else b'X' * len(good)
                with mock.patch.object(self.installer.urllib.request, 'urlopen', return_value=response):
                    with self.assertRaises(Exception):
                        self.real_fetch('index.php')

    def test_apply_rechecks_live_and_guard_hashes_after_prepare(self):
        session = self.prepare()
        (self.live / 'public-presentation.js').write_bytes(b'// new edit after preflight\n')
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_apply_rechecks_guard_hash_after_prepare(self):
        session = self.prepare()
        (self.live / 'data/private/users.json').write_bytes(b'{"changed":"synthetic account edit"}')
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_apply_rechecks_staged_hash_before_live_writes(self):
        session = self.prepare()
        staged = session / 'stage/index.php'
        staged.write_bytes(b'X' * len(self.after['index.php']))
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_apply_refuses_symlinked_stage_even_with_correct_bytes(self):
        session = self.prepare()
        external = self.root / 'outside-stage.php'
        external.write_bytes(self.after['index.php'])
        staged = session / 'stage/index.php'
        staged.unlink()
        os.symlink(str(external), str(staged))
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(external.read_bytes(), self.after['index.php'])
        self.assertFalse(self.writes)

    def test_apply_refuses_hardlinked_stage_even_with_correct_bytes(self):
        session = self.prepare()
        external = self.root / 'hardlinked-stage.php'
        os.link(str(session / 'stage/index.php'), str(external))
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(external.read_bytes(), self.after['index.php'])
        self.assertFalse(self.writes)

    def test_symlink_target_is_refused(self):
        external = self.root / 'outside.php'
        external.write_bytes(self.before['index.php'])
        (self.live / 'index.php').unlink()
        os.symlink(str(external), str(self.live / 'index.php'))
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(external.read_bytes(), self.before['index.php'])
        self.assertFalse(self.writes)

    def test_symlink_parent_is_refused(self):
        outside = self.root / 'outside-admin'
        (self.live / 'admin').rename(outside)
        os.symlink(str(outside), str(self.live / 'admin'))
        with self.assertRaises(Exception):
            self.prepare()
        self.assertFalse((outside / 'publication-media.php').exists())
        self.assertFalse(self.writes)

    def test_hardlinked_target_is_refused(self):
        external = self.root / 'hardlinked-outside.php'
        os.link(str(self.live / 'index.php'), str(external))
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(external.read_bytes(), self.before['index.php'])
        self.assertFalse(self.writes)

    def test_apply_rejects_new_symlink_without_following_it(self):
        session = self.prepare()
        external = self.root / 'late-outside.php'
        external.write_bytes(self.before['index.php'])
        (self.live / 'index.php').unlink()
        os.symlink(str(external), str(self.live / 'index.php'))
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(external.read_bytes(), self.before['index.php'])
        self.assertFalse(self.writes)

    def test_partial_replace_failure_restores_all_baselines(self):
        session = self.prepare()
        original_replace = self.installer.atomic_replace
        replacements = []
        failed = [False]

        def fail_after_write(src, dst, **kwargs):
            target = self.replace_target(dst, kwargs)
            result = original_replace(src, dst, **kwargs)
            if self.live in target.parents and not failed[0]:
                replacements.append(str(target.relative_to(self.live)))
                if len(replacements) == 2:
                    failed[0] = True
                    raise OSError('Synthetic failure after the second live replacement')
            return result

        self.installer.atomic_replace = fail_after_write
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertTrue(failed[0], 'failure injection must reach a partial install')
        self.assertNotIn('sw.js', replacements, 'worker must not advance before code finishes')
        self.assert_baseline()

    def test_http_failure_rolls_back_installed_release_and_missing_target(self):
        session = self.prepare()

        def fail_http():
            self.assert_release_bytes()
            raise RuntimeError('Synthetic read-only HTTP verification failure')

        self.installer.verify_http = fail_http
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assert_baseline()

    def test_explicit_rollback_restores_bytes_modes_and_absence(self):
        before = self.live_snapshot()
        session = self.prepare()
        self.installer.apply(session=str(session))
        self.installer.rollback(str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assert_baseline()

    def test_stale_rollback_refuses_all_changes_before_writing(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        newer = b'// a newer host change must never be rolled back\n'
        (self.live / 'public-presentation.js').write_bytes(newer)
        before = self.live_snapshot()
        previous_writes = list(self.writes)
        with self.assertRaises(Exception):
            self.installer.rollback(str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(self.writes, previous_writes, 'stale rollback must validate every target before any restore')
        self.assertEqual((self.live / 'public-presentation.js').read_bytes(), newer)

    def test_protected_content_drift_stays_untouched_during_safe_code_rollback(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        updated_content = b'{"synthetic":"new staff content after deployment"}\n'
        (self.live / 'data/content.json').write_bytes(updated_content)
        self.installer.rollback(str(session))
        self.assertEqual((self.live / 'data/content.json').read_bytes(), updated_content)
        self.assertNotIn('data/content.json', self.writes)
        for path, data in self.before.items():
            target = self.live / path
            if data is None:
                self.assertFalse(target.exists())
            else:
                self.assertEqual(target.read_bytes(), data, path)
                self.assertEqual(mode(target), self.original_modes[path], path)

    def test_corrupt_original_backup_refuses_rollback_before_writing(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        (session / 'originals/index.php').write_bytes(b'corrupt synthetic backup')
        before = self.live_snapshot()
        previous_writes = list(self.writes)
        with self.assertRaises(Exception):
            self.installer.rollback(str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(self.writes, previous_writes)

    def test_empty_inventory_and_nonallowlisted_paths_are_refused(self):
        self.installer.FILES = {}
        with self.assertRaises(Exception):
            self.prepare()
        self.installer.FILES = {'../outside.php': {'sha256': digest(b'escape'), 'bytes': 6, 'baseline_sha256': None}}
        with self.assertRaises(Exception):
            self.prepare()
        self.assertFalse((self.root / 'outside.php').exists())
        self.assertFalse(self.writes)

    def test_dependency_files_are_installed_before_their_consumers(self):
        self.add_release_file('admin/publication-designer.php', b'<?php /* old */ ?>', b'<?php /* new */ ?>')
        self.add_release_file('admin/publication-projects.php', b'<?php /* old projects */ ?>', b'<?php /* new projects */ ?>')
        self.add_release_file('public-presentation.css', b'/* old CSS */', b'/* reviewed CSS */')
        self.add_release_file('assets/visuals/kcmc-kids-safari.jpg', None, b'synthetic reviewed image')
        session = self.prepare()
        self.installer.apply(session=str(session))
        self.assertEqual(self.writes, ['assets/visuals/kcmc-kids-safari.jpg', 'public-presentation.css',
                                      'public-presentation.js', 'admin/publication-media.php',
                                      'admin/publication-projects.php', 'admin/publication-designer.php',
                                      'index.php', 'sw.js'])

    def test_rollback_resumes_after_partial_restoration(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        original_replace = self.installer.atomic_replace
        restored = []

        def interrupt(src, dst, **kwargs):
            target = self.replace_target(dst, kwargs)
            result = original_replace(src, dst, **kwargs)
            if self.live in target.parents:
                restored.append(str(target.relative_to(self.live)))
                if len(restored) == 2:
                    raise OSError('Synthetic interruption after partial restoration')
            return result

        self.installer.atomic_replace = interrupt
        with self.assertRaises(Exception):
            self.installer.rollback(str(session))
        self.assertEqual(json.loads((session / 'manifest.json').read_text())['phase'], 'rolling_back')
        self.installer.atomic_replace = original_replace
        self.installer.rollback(str(session))
        self.assert_baseline()

    def test_candidate_intent_journal_recovers_rename_before_installed_record(self):
        session = self.prepare()
        value = self.installer.read_session(session)
        path = 'public-presentation.js'
        value['phase'], value['intent'] = 'applying', path
        value['files'][path]['candidate'] = self.installer.installation_candidate(session, path, value['files'][path])
        self.installer.journal(session, value)
        self.installer.install_one(session, path, value['files'][path])
        durable = self.installer.read_session(session)
        self.assertIsNone(durable['files'][path]['installed'])
        self.assertEqual(durable['intent'], path)
        self.installer.rollback(str(session), automatic=True)
        self.assert_baseline()

    def test_failed_phase_journal_fault_still_restores_affected_code(self):
        session = self.prepare()
        original_journal = self.installer.journal
        failed_writes = []

        def faulty_journal(path, value):
            if value['phase'] == 'failed':
                failed_writes.append(True)
                raise OSError('Synthetic failed-state journal disk fault')
            return original_journal(path, value)

        def bad_http():
            raise RuntimeError('Synthetic HTTP failure after installation')

        self.installer.journal = faulty_journal
        self.installer.verify_http = bad_http
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertTrue(failed_writes)
        self.assert_baseline()

    def test_same_bytes_new_mode_blocks_rollback_before_restore(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        (self.live / 'public-presentation.js').chmod(0o640)
        before, writes = self.live_snapshot(), list(self.writes)
        with self.assertRaises(Exception):
            self.installer.rollback(str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(self.writes, writes)

    def test_same_bytes_new_inode_blocks_rollback_before_restore(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        target = self.live / 'public-presentation.js'
        old = target.stat()
        substitute = self.root / 'newer-same-bytes.js'
        substitute.write_bytes(target.read_bytes())
        substitute.chmod(stat.S_IMODE(old.st_mode))
        os.utime(str(substitute), ns=(old.st_atime_ns, old.st_mtime_ns))
        os.replace(str(substitute), str(target))
        self.assertNotEqual(target.stat().st_ino, old.st_ino)
        before, writes = self.live_snapshot(), list(self.writes)
        with self.assertRaises(Exception):
            self.installer.rollback(str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(self.writes, writes)

    def test_same_bytes_new_owner_metadata_blocks_rollback_before_restore(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        target = self.live / 'public-presentation.js'
        actual_read = self.installer.read_file

        def changed_owner(path, *args, **kwargs):
            data, info = actual_read(path, *args, **kwargs)
            if Path(path) == target:
                info = dict(info)
                info['uid'] += 1
            return data, info

        writes = list(self.writes)
        with mock.patch.object(self.installer, 'read_file', side_effect=changed_owner):
            with self.assertRaises(Exception):
                self.installer.rollback(str(session))
        self.assertEqual(self.writes, writes)
        self.assert_release_bytes()

    def test_fifo_read_is_refused_without_blocking(self):
        fifo = self.root / 'synthetic-fifo'
        os.mkfifo(str(fifo))
        started = time.monotonic()
        with self.assertRaises(Exception):
            self.installer.read_file(fifo)
        self.assertLess(time.monotonic() - started, 1)

    def test_cross_filesystem_stage_is_refused_during_prepare(self):
        actual_read = self.installer.read_private

        def foreign_device(path):
            data, info = actual_read(path)
            if '/stage/' in str(path):
                info = dict(info)
                info['dev'] += 1
            return data, info

        before = self.live_snapshot()
        with mock.patch.object(self.installer, 'read_private', side_effect=foreign_device):
            with self.assertRaises(Exception):
                self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_busy_installation_lock_fails_promptly(self):
        self.backups.mkdir(mode=0o700)
        lock = self.backups / '.install.lock'
        lock.write_bytes(b'')
        lock.chmod(0o600)
        with lock.open('r+b') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            started = time.monotonic()
            with self.assertRaises(Exception):
                self.prepare()
            self.assertLess(time.monotonic() - started, 1)
        self.assertFalse(self.writes)

    def test_missing_publisher_locks_create_only_coordination_metadata(self):
        for name in self.installer.PUBLISHER_STORES:
            (self.publisher / (name + '.lock')).unlink()
        before = self.live_snapshot()
        self.prepare()
        after = self.live_snapshot()
        added = set(after) - set(before)
        self.assertEqual(added, set('data/private/' + name + '.lock' for name in self.installer.PUBLISHER_STORES))
        for path, expected in before.items():
            self.assertEqual(after[path], expected)
        for name in self.installer.PUBLISHER_STORES:
            self.assertFalse((self.publisher / name).exists())
            self.assertIn(mode(self.publisher / (name + '.lock')), (0o600, 0o640))

    def test_publisher_new_store_blocks_manual_and_automatic_downgrade(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        store = self.publisher / 'publications.json'
        fresh = b'{"version":2,"synthetic":"new publication after deployment"}'
        store.write_bytes(fresh)
        before, writes = self.live_snapshot(), list(self.writes)
        for automatic in [False, True]:
            with self.subTest(automatic=automatic):
                with self.assertRaises(Exception):
                    self.installer.rollback(str(session), automatic=automatic)
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(self.writes, writes)
        self.assertEqual(store.read_bytes(), fresh)

    def test_publisher_edited_store_blocks_downgrade_without_copying_json(self):
        store = self.publisher / 'publications.json'
        secret_fixture = b'{"version":2,"synthetic":"NEVER-COPY-THIS-MARKER"}'
        store.write_bytes(secret_fixture)
        store.chmod(0o600)
        session = self.prepare()
        for path in session.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'NEVER-COPY-THIS-MARKER', path.read_bytes())
        self.installer.apply(session=str(session))
        changed = b'{"version":2,"synthetic":"newer publication"}'
        store.write_bytes(changed)
        writes = list(self.writes)
        with self.assertRaises(Exception):
            self.installer.rollback(str(session))
        self.assertEqual(self.writes, writes)
        self.assertEqual(store.read_bytes(), changed)
        self.assert_release_bytes()

    def test_unchanged_publisher_stores_survive_install_and_rollback(self):
        contents = {}
        for name in self.installer.PUBLISHER_STORES:
            path = self.publisher / name
            contents[name] = b'{"version":2,"synthetic":"unchanged ' + name.encode('ascii') + b'"}'
            path.write_bytes(contents[name])
            path.chmod(0o600)
        session = self.prepare()
        self.installer.apply(session=str(session))
        self.installer.rollback(str(session))
        self.assert_baseline()
        for name, data in contents.items():
            self.assertEqual((self.publisher / name).read_bytes(), data)
            self.assertFalse((session / 'originals/data/private' / name).exists())

    def test_busy_publisher_lock_fails_promptly(self):
        lock = self.publisher / 'publications.json.lock'
        with lock.open('r+b') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            started = time.monotonic()
            with self.assertRaises(Exception):
                self.prepare()
            self.assertLess(time.monotonic() - started, 1)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_missing_publisher_directory_fails_closed(self):
        self.installer.shutil.rmtree(str(self.publisher))
        with self.assertRaises(Exception):
            self.prepare()
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_real_http_checks_all_static_hashes_and_three_admin_redirects(self):
        self.add_release_file('assets/visuals/kcmc-kids-safari.jpg', None, b'synthetic reviewed image')
        opened, seen = self.http_fixture()
        with mock.patch.object(self.installer.urllib.request, 'urlopen', side_effect=opened):
            self.real_http()
        for path in self.after:
            if not path.endswith('.php'):
                self.assertIn(path, seen)
        for path in ['admin/publication-designer.php', 'admin/publication-projects.php', 'admin/publication-media.php']:
            self.assertIn(path, seen)

    def test_real_http_refuses_wrong_static_bytes_or_unprotected_admin(self):
        for bad_static, bad_admin in [('public-presentation.js', None),
                                      (None, 'admin/publication-designer.php'),
                                      (None, 'admin/publication-projects.php'),
                                      (None, 'admin/publication-media.php')]:
            with self.subTest(static=bad_static, admin=bad_admin):
                opened, _ = self.http_fixture(bad_static, bad_admin)
                with mock.patch.object(self.installer.urllib.request, 'urlopen', side_effect=opened):
                    with self.assertRaises(Exception):
                        self.real_http()


    def test_pending_runtime_pin_refuses_before_live_changes(self):
        self.installer.COMMIT = 'PENDING_APPROVED_OCT8_COMMIT'
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_complete_ae004_records_the_selected_bundle(self):
        session = self.prepare()
        self.assertEqual(self.installer.read_session(session)['baseline_id'], self.installer.BASELINE_IDS[0])

    def test_complete_previous_release_upgrades_and_restores_existing_media(self):
        self.activate_previous_release()
        before = self.live_snapshot()
        session = self.prepare()
        self.assertEqual(self.installer.read_session(session)['baseline_id'], self.installer.BASELINE_IDS[1])
        self.installer.apply(session=str(session))
        self.assert_release_bytes()
        self.installer.rollback(str(session))
        self.assert_baseline()
        self.assertEqual(self.live_snapshot(), before)
        self.assertTrue((self.live / 'admin/publication-media.php').exists())

    def test_mixed_old_and_previous_files_refuse_before_download(self):
        path = 'index.php'
        (self.live / path).write_bytes(self.after[path])
        (self.live / path).chmod(0o644)
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_previous_release_missing_one_file_is_not_an_old_bundle(self):
        self.activate_previous_release()
        (self.live / 'admin/publication-media.php').unlink()
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_unknown_session_baseline_is_refused(self):
        session = self.prepare()
        value = self.installer.read_session(session)
        value['baseline_id'] = 'e' * 40
        self.installer.journal(session, value)
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertFalse(self.writes)
        self.assert_baseline()

    def test_allowed_baseline_label_cannot_relabel_original_preimages(self):
        session = self.prepare()
        value = self.installer.read_session(session)
        value['baseline_id'] = self.installer.BASELINE_IDS[1]
        self.installer.journal(session, value)
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertFalse(self.writes)
        self.assert_baseline()

    def test_automatic_rollback_preserves_complete_previous_release(self):
        self.activate_previous_release()
        before = self.live_snapshot()
        session = self.prepare()
        def bad_http():
            raise RuntimeError('synthetic failed repair verification')
        self.installer.verify_http = bad_http
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assert_baseline()
        self.assertTrue((self.live / 'admin/publication-media.php').exists())

    def test_incomplete_baseline_definition_is_refused(self):
        self.installer.BASELINES[self.installer.BASELINE_IDS[1]].pop('sw.js')
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)


if __name__ == '__main__':
    unittest.main(verbosity=2)
