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
import struct
import subprocess
import tempfile
import time
import unittest
from unittest import mock
import zlib


INSTALLER = Path(__file__).resolve().with_name('installer.py')
BASELINE_COMMIT = '268bebca444bd4970bb4ecaa0d6eceb6a11988fd'
TARGET_COMMIT = '4225fce8968747ad4f828a9a36087b04fd020484'
NEW_IMAGE = 'assets/visuals/kcmc-building-retouched-20261009.jpg'
NEW_SVG = 'assets/visuals/trunk-or-treat-2026.svg'
ICON = 'assets/icons/icon-512.png'
RELEASE_PATHS = set(['admin/publication-designer.php', NEW_IMAGE,
                     'index.php', 'public-presentation.css',
                     'public-presentation.js', 'sw.js', 'lib/bootstrap.php',
                     'manifest.webmanifest', ICON, NEW_SVG])
SAFE_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" viewBox="0 0 100 80"><defs><linearGradient id="paint"><stop offset="0" stop-color="#abcdef"/></linearGradient></defs><rect width="100" height="80" fill="url(#paint)"/><text x="10" y="40">Synthetic church artwork</text></svg>'''


def png_fixture(width=512, height=512):
    def chunk(kind, body):
        return (struct.pack('!I', len(body)) + kind + body +
                struct.pack('!I', zlib.crc32(kind + body) & 0xffffffff))
    scanlines = (b'\x00' + b'\x20\x70\xa0\xff' * width) * height
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))


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
        self.production = {'commit': self.installer.COMMIT,
                           'baselines': self.installer.BASELINE_IDS,
                           'files': set(self.installer.FILES),
                           'allowed': set(self.installer.ALLOWED),
                           'blobs': set(self.installer.GIT_SHAS),
                           'guards': set(self.installer.GUARDS)}
        self.before = {
            'index.php': b'<?php echo "Original page"; ?>\n',
            'public-presentation.css': b'/* original presentation */\n',
            'public-presentation.js': b'window.fixture = "original";\n',
            'sw.js': b'// original service worker\n',
            'admin/publication-designer.php': b'<?php /* original designer */ ?>\n',
            'lib/bootstrap.php': b'<?php /* original bootstrap */ ?>\n',
            'manifest.webmanifest': b'{"icons":[{"src":"assets/icons/icon-512.png"}]}\n',
            # Approved historical PNG was corrupt; its baseline hash, not a
            # decoder, establishes provenance before replacing it safely.
            ICON: b'APPROVED CORRUPT HISTORICAL PNG FIXTURE',
            NEW_IMAGE: None,
            NEW_SVG: None,
        }
        self.after = {
            'index.php': b'<?php echo "Reviewed page"; ?>\n',
            'public-presentation.css': b'/* reviewed presentation */\n',
            'public-presentation.js': b'window.fixture = "reviewed";\n',
            'sw.js': b'// kcmc-connect-v3.0.3-public-only-trunk-art-20261011\n',
            'admin/publication-designer.php': b'<?php /* reviewed designer */ ?>\n',
            'lib/bootstrap.php': b'<?php /* reviewed bootstrap */ ?>\n',
            'manifest.webmanifest': b'{"icons":[{"src":"assets/icons/icon-512.png?v=3.0.3","sizes":"512x512","type":"image/png"}]}\n',
            ICON: png_fixture(),
            NEW_IMAGE: b'\xff\xd8Synthetic approved retouched-image bytes\xff\xd9',
            NEW_SVG: SAFE_SVG,
        }
        self.original_modes = {'index.php': 0o640, 'public-presentation.css': 0o620,
                               'public-presentation.js': 0o644, 'sw.js': 0o600,
                               'admin/publication-designer.php': 0o640,
                               'lib/bootstrap.php': 0o640,
                               'manifest.webmanifest': 0o644, ICON: 0o644}
        for path, data in self.before.items():
            target = self.live / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if data is not None:
                target.write_bytes(data)
                target.chmod(self.original_modes[path])
        self.guards = {
            'admin/index.php': b'<?php /* unchanged Publishing Desk */ ?>\n',
            'admin/publication-projects.php': b'<?php /* unchanged projects validator */ ?>\n',
            'admin/publication-media.php': b'<?php /* unchanged shared media endpoint */ ?>\n',
            'assets/visuals/kcmc-building-2024.webp': b'UNCHANGED ORIGINAL CHURCH PHOTOGRAPH',
        }
        # Editorial/accounts are preserved sentinels, not frozen source guards.
        # Production captures current content dynamically; it never compares it
        # to a repository content hash or touches these other private stores.
        self.sentinels = {
            'data/content.json': b'{"synthetic":"editorial content stays private"}\n',
            'data/private/users.json': b'{"synthetic":"no real accounts"}\n',
            'data/private/prayer-requests.json': b'{"synthetic":"no real prayer requests"}\n',
            'data/private/timecards.json': b'{"synthetic":"no real timecards"}\n',
            'config.php': b'<?php /* synthetic live configuration */ ?>\n',
            'backups/editorial-sentinel.json': b'{"synthetic":"preserve existing backup"}\n',
        }
        for path, data in list(self.guards.items()) + list(self.sentinels.items()):
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
        baseline_id, = self.installer.BASELINE_IDS
        self.installer.BASELINES = {
            baseline_id: {path: None if data is None else {'sha256': digest(data), 'bytes': len(data),
                     'mode': self.original_modes[path]} for path, data in self.before.items()},
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

    def http_fixture(self, bad_static=None, bad_admin=None, omit_home=None):
        seen = []
        module = self.installer
        markers = ['data-hero-photo', NEW_IMAGE.rsplit('/', 1)[1],
                   'public-presentation.css?v=blue-fish-menu-20261009',
                   'public-presentation.js?v=blue-fish-menu-20261009',
                   'manifest.webmanifest?v=3.0.1']
        if omit_home:
            markers = [value.replace(omit_home, '') for value in markers]

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
                return Response(url, ' '.join(markers).encode('ascii'))
            if path.startswith('admin/'):
                destination = url if path == bad_admin else module.PUBLIC_ROOT + 'member/login.php?next=synthetic'
                return Response(destination, b'Staff Sign In')
            if path == 'member/login.php':
                return Response(url, b'Staff Sign In')
            bare_path = path.split('?', 1)[0]
            body = self.after[bare_path]
            if path == bad_static or bare_path == bad_static:
                body = b'X' * len(body)
            return Response(url, body)

        return opened, seen

    def install_target_fixture(self):
        for path, data in self.after.items():
            (self.live / path).write_bytes(data)
            (self.live / path).chmod(0o644)

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
        for path, data in list(self.guards.items()) + list(self.sentinels.items()):
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
        self.assertEqual(protected_backup.read_bytes(), self.sentinels['data/content.json'])
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
        self.assertEqual(mode(self.live / NEW_IMAGE), 0o644)
        self.assertEqual(mode(self.live / NEW_SVG), 0o644)
        for path, data in list(self.guards.items()) + list(self.sentinels.items()):
            self.assertEqual((self.live / path).read_bytes(), data, path)

    def test_baseline_drift_refuses_before_live_writes(self):
        (self.live / 'public-presentation.js').write_bytes(b'// unreviewed host edit\n')
        drifted = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), drifted)
        self.assertFalse(self.writes)

    def test_guard_drift_refuses_before_live_writes(self):
        (self.live / 'admin/publication-projects.php').write_bytes(b'<?php /* newer projects validator */ ?>\n')
        drifted = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), drifted)
        self.assertFalse(self.writes)

    def test_current_editorial_bytes_are_accepted_and_backed_up_without_source_hash(self):
        current = b'{"synthetic":"staff events and fields differ from repository"}\n'
        self.sentinels['data/content.json'] = current
        (self.live / 'data/content.json').write_bytes(current)
        before = self.live_snapshot()
        session = self.prepare()
        self.assertEqual((session / 'originals/data/content.json').read_bytes(), current)
        self.installer.apply(session=str(session))
        self.installer.rollback(str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertNotIn('data/content.json', self.writes)

    def test_editorial_change_after_prepare_refuses_apply_without_restoring_content(self):
        session = self.prepare()
        changed = b'{"synthetic":"pending editorial save after preflight"}\n'
        (self.live / 'data/content.json').write_bytes(changed)
        before = self.live_snapshot()
        with self.assertRaisesRegex(self.installer.Refusal, 'Live hash drift'):
            self.installer.apply(session=str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_private_account_changes_remain_outside_code_transaction(self):
        session = self.prepare()
        changed = b'{"synthetic":"newer private account data"}\n'
        self.sentinels['data/private/users.json'] = changed
        (self.live / 'data/private/users.json').write_bytes(changed)
        self.installer.apply(session=str(session))
        self.installer.rollback(str(session))
        self.assert_baseline()
        self.assertNotIn('data/private/users.json', self.writes)
        self.assertFalse((session / 'originals/data/private/users.json').exists())

    def test_missing_expected_baseline_is_refused(self):
        (self.live / 'index.php').unlink()
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_unexpected_file_at_missing_baseline_is_refused(self):
        (self.live / NEW_IMAGE).write_bytes(b'unreviewed host-only photograph')
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
        (self.live / 'admin/publication-media.php').write_bytes(b'<?php /* newer media endpoint */ ?>')
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
        self.assertEqual((outside / 'publication-media.php').read_bytes(), self.guards['admin/publication-media.php'])
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

    def test_empty_inventory_is_refused(self):
        self.installer.FILES = {}
        with self.assertRaises(self.installer.Refusal):
            self.prepare()
        self.assertFalse(self.writes)
        self.assertFalse(self.fetches)

    def test_nonallowlisted_paths_refuse_after_complete_baseline_definition(self):
        # Supply internally complete records so these failures exercise scope
        # validation rather than an unrelated incomplete-baseline check.
        paths = ['../outside.php', '/absolute.php', 'data/content.json',
                 'config.php', 'admin/publication-projects.php',
                 'admin/publication-media.php', 'assets/visuals/kcmc-building-2024.webp']
        for path in paths:
            with self.subTest(path=path):
                item = {'sha256': digest(b'escape'), 'bytes': 6, 'baseline_sha256': None}
                self.installer.FILES[path] = item
                self.installer.BASELINES[BASELINE_COMMIT][path] = None
                self.installer.GIT_SHAS[path] = hashlib.sha1(b'blob 6\0escape').hexdigest()
                before = self.live_snapshot()
                with self.assertRaisesRegex(self.installer.Refusal, 'out-of-scope inventory'):
                    self.prepare()
                self.assertEqual(self.live_snapshot(), before)
                self.assertFalse(self.fetches)
                self.assertFalse(self.writes)
                del self.installer.FILES[path]
                del self.installer.BASELINES[BASELINE_COMMIT][path]
                del self.installer.GIT_SHAS[path]

    def test_dependency_files_are_installed_before_their_consumers(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        self.assertEqual(self.writes, [ICON, NEW_IMAGE, NEW_SVG, 'lib/bootstrap.php',
                                      'public-presentation.css', 'public-presentation.js',
                                      'manifest.webmanifest', 'admin/publication-designer.php',
                                      'index.php', 'sw.js'])
        self.assertTrue(set(self.writes).isdisjoint(self.guards))
        self.assertTrue(set(self.writes).isdisjoint(self.sentinels))

    def test_bootstrap_references_are_present_on_apply_and_removed_only_after_restore(self):
        session = self.prepare()
        real_replace, real_unlink = self.installer.atomic_replace, self.installer.os.unlink
        observations = []
        def observed_replace(src, dst, **kwargs):
            target = self.replace_target(dst, kwargs)
            source = self.replace_target(src, {'dst_dir_fd': kwargs.get('src_dir_fd')})
            if target == self.live / 'lib/bootstrap.php':
                if source.read_bytes() == self.after['lib/bootstrap.php']:
                    self.assertEqual((self.live / NEW_SVG).read_bytes(), self.after[NEW_SVG])
                    observations.append('art before new bootstrap')
                elif source.read_bytes() == self.before['lib/bootstrap.php']:
                    observations.append('old bootstrap restored')
            return real_replace(src, dst, **kwargs)
        def observed_unlink(path, *args, **kwargs):
            target = self.replace_target(path, {'dst_dir_fd': kwargs.get('dir_fd')})
            if target == self.live / NEW_SVG:
                self.assertEqual((self.live / 'lib/bootstrap.php').read_bytes(), self.before['lib/bootstrap.php'])
                self.assertIn('old bootstrap restored', observations)
                observations.append('new art removed')
            return real_unlink(path, *args, **kwargs)
        with mock.patch.object(self.installer, 'atomic_replace', side_effect=observed_replace), \
                mock.patch.object(self.installer.os, 'unlink', side_effect=observed_unlink):
            self.installer.apply(session=str(session))
            self.installer.rollback(str(session))
        self.assertEqual(observations, ['art before new bootstrap', 'old bootstrap restored', 'new art removed'])
        self.assert_baseline()

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

    def test_new_image_intent_window_recovers_prior_absence(self):
        session = self.prepare()
        value = self.installer.read_session(session)
        value['phase'], value['intent'] = 'applying', NEW_IMAGE
        record = value['files'][NEW_IMAGE]
        self.assertIsNone(record['original'])
        record['candidate'] = self.installer.installation_candidate(session, NEW_IMAGE, record)
        self.installer.journal(session, value)
        self.installer.install_one(session, NEW_IMAGE, record)
        self.assertTrue((self.live / NEW_IMAGE).exists())
        self.assertIsNone(self.installer.read_session(session)['files'][NEW_IMAGE]['installed'])
        self.installer.rollback(str(session), automatic=True)
        self.assert_baseline()
        self.assertFalse((self.live / NEW_IMAGE).exists())

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

    def assert_rollback_refused_without_live_mutation(self, session):
        before, writes = self.live_snapshot(), list(self.writes)
        with self.assertRaises(self.installer.Refusal):
            self.installer.rollback(str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertEqual(self.writes, writes)

    def test_newer_retouched_image_bytes_prevent_rollback_deletion(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        image = self.live / NEW_IMAGE
        image.write_bytes(b'NEWER OWNER APPROVED IMAGE MUST STAY')
        self.assert_rollback_refused_without_live_mutation(session)
        self.assertEqual(image.read_bytes(), b'NEWER OWNER APPROVED IMAGE MUST STAY')

    def test_same_image_bytes_new_mode_prevent_rollback_deletion(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        image = self.live / NEW_IMAGE
        image.chmod(0o640)
        self.assert_rollback_refused_without_live_mutation(session)
        self.assertTrue(image.exists())

    def test_same_image_bytes_new_inode_prevent_rollback_deletion(self):
        session = self.prepare()
        self.installer.apply(session=str(session))
        image = self.live / NEW_IMAGE
        old = image.stat()
        replacement = self.root / 'newer-retouched.jpg'
        replacement.write_bytes(image.read_bytes())
        replacement.chmod(stat.S_IMODE(old.st_mode))
        os.utime(str(replacement), ns=(old.st_atime_ns, old.st_mtime_ns))
        os.replace(str(replacement), str(image))
        self.assertNotEqual(image.stat().st_ino, old.st_ino)
        self.assert_rollback_refused_without_live_mutation(session)
        self.assertTrue(image.exists())

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
        opened, seen = self.http_fixture()
        with mock.patch.object(self.installer.urllib.request, 'urlopen', side_effect=opened):
            self.real_http()
        for path in self.after:
            if not path.endswith('.php'):
                self.assertIn(path, seen)
        for path in ['admin/publication-designer.php', 'admin/publication-projects.php', 'admin/publication-media.php']:
            self.assertIn(path, seen)
        expected_static = set([ICON, NEW_IMAGE, NEW_SVG, 'manifest.webmanifest',
                               'public-presentation.css', 'public-presentation.js', 'sw.js'])
        static = [path for path in seen if path.split('?', 1)[0] in expected_static]
        self.assertEqual(set(static), expected_static | set(['manifest.webmanifest?v=3.0.1', ICON + '?v=3.0.3']))
        self.assertEqual(len(static), 9)

    def test_real_http_refuses_wrong_static_bytes_or_unprotected_admin(self):
        for bad_static, bad_admin in [('public-presentation.js', None),
                                      (NEW_IMAGE, None),
                                      (NEW_SVG, None),
                                      (ICON, None),
                                      ('manifest.webmanifest', None),
                                      (ICON + '?v=3.0.3', None),
                                      ('manifest.webmanifest?v=3.0.1', None),
                                      ('public-presentation.css', None),
                                      ('sw.js', None),
                                      (None, 'admin/publication-designer.php'),
                                      (None, 'admin/publication-projects.php'),
                                      (None, 'admin/publication-media.php')]:
            with self.subTest(static=bad_static, admin=bad_admin):
                opened, _ = self.http_fixture(bad_static, bad_admin)
                with mock.patch.object(self.installer.urllib.request, 'urlopen', side_effect=opened):
                    with self.assertRaises(Exception):
                        self.real_http()

    def test_real_http_refuses_missing_current_home_markers(self):
        for marker in ['data-hero-photo', NEW_IMAGE.rsplit('/', 1)[1],
                       'public-presentation.css', 'public-presentation.js',
                       'blue-fish-menu-20261009', 'manifest.webmanifest?v=3.0.1']:
            with self.subTest(marker=marker):
                opened, _ = self.http_fixture(omit_home=marker)
                with mock.patch.object(self.installer.urllib.request, 'urlopen', side_effect=opened):
                    with self.assertRaisesRegex(self.installer.Refusal, 'Public marker check failed'):
                        self.real_http()


    def test_pending_runtime_pin_refuses_before_live_changes(self):
        self.installer.COMMIT = 'PENDING_APPROVED_OCT13_COMMIT'
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_production_pins_and_exact_ten_file_scope(self):
        self.assertEqual(self.production['commit'], TARGET_COMMIT)
        self.assertEqual(self.production['baselines'], (BASELINE_COMMIT,))
        self.assertEqual(self.production['files'], RELEASE_PATHS)
        self.assertEqual(self.production['allowed'], RELEASE_PATHS)
        self.assertEqual(self.production['blobs'], RELEASE_PATHS)
        self.assertTrue(set(['admin/publication-projects.php', 'admin/publication-media.php',
                             'assets/visuals/kcmc-building-2024.webp', 'admin/index.php']).issubset(self.production['guards']))
        self.assertNotIn('lib/bootstrap.php', self.production['guards'])
        self.assertEqual(len(self.production['guards']), 14)
        self.assertEqual(sum(value is None for value in self.before.values()), 2)

    def test_complete_268beb_records_the_only_selected_bundle(self):
        session = self.prepare()
        self.assertEqual(self.installer.read_session(session)['baseline_id'], BASELINE_COMMIT)

    def test_single_bundle_upgrade_and_rollback_preserve_unaffected_records(self):
        before = self.live_snapshot()
        session = self.prepare()
        self.installer.apply(session=str(session))
        self.assert_release_bytes()
        self.assertTrue((self.live / NEW_IMAGE).exists())
        self.installer.rollback(str(session))
        self.assert_baseline()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse((self.live / NEW_IMAGE).exists())
        self.assertTrue((self.live / 'admin/publication-media.php').exists())

    def test_mixed_baseline_and_target_files_refuse_before_download(self):
        path = 'index.php'
        (self.live / path).write_bytes(self.after[path])
        (self.live / path).chmod(0o644)
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_already_installed_target_is_verified_without_download_or_session(self):
        self.install_target_fixture()
        before = self.live_snapshot()
        result = self.installer.apply()
        self.assertIsInstance(result, self.installer.AlreadyCurrent)
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)
        self.assertFalse(self.lints)
        self.assertTrue(self.http_calls)
        self.assertEqual([path.name for path in self.backups.iterdir()], ['.install.lock'])

    def test_unknown_session_baseline_is_refused(self):
        session = self.prepare()
        value = self.installer.read_session(session)
        value['baseline_id'] = 'e' * 40
        self.installer.journal(session, value)
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertFalse(self.writes)
        self.assert_baseline()

    def test_session_original_preimage_tampering_is_refused(self):
        session = self.prepare()
        value = self.installer.read_session(session)
        value['files']['index.php']['original']['sha256'] = digest(b'unreviewed baseline')
        self.installer.journal(session, value)
        with self.assertRaises(Exception):
            self.installer.apply(session=str(session))
        self.assertFalse(self.writes)
        self.assert_baseline()

    def test_automatic_rollback_preserves_complete_baseline_and_sentinels(self):
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
        self.installer.BASELINES[BASELINE_COMMIT].pop('sw.js')
        before = self.live_snapshot()
        with self.assertRaises(Exception):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_omitted_approved_file_refuses_even_with_consistent_remaining_metadata(self):
        del self.installer.FILES[NEW_IMAGE]
        del self.installer.GIT_SHAS[NEW_IMAGE]
        del self.installer.BASELINES[BASELINE_COMMIT][NEW_IMAGE]
        before = self.live_snapshot()
        with self.assertRaisesRegex(self.installer.Refusal, 'out-of-scope inventory'):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_incomplete_git_blob_inventory_refuses_before_download(self):
        del self.installer.GIT_SHAS[NEW_IMAGE]
        before = self.live_snapshot()
        with self.assertRaisesRegex(self.installer.Refusal, 'Incomplete approved Git blob inventory'):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_wrong_git_blob_hash_refuses_despite_matching_sha256(self):
        self.installer.GIT_SHAS[NEW_IMAGE] = '0' * 40
        before = self.live_snapshot()
        with self.assertRaisesRegex(self.installer.Refusal, 'Approved Git blob mismatch'):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_extra_legacy_baseline_bundle_is_refused(self):
        self.installer.BASELINES['61c70f590735522adbfd6be02dab6888924a54fd'] = dict(self.installer.BASELINES[BASELINE_COMMIT])
        before = self.live_snapshot()
        with self.assertRaisesRegex(self.installer.Refusal, 'Unknown baseline bundle'):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_target_image_alone_is_not_an_approved_partial_release(self):
        (self.live / NEW_IMAGE).write_bytes(self.after[NEW_IMAGE])
        (self.live / NEW_IMAGE).chmod(0o644)
        before = self.live_snapshot()
        with self.assertRaisesRegex(self.installer.Refusal, 'complete approved baseline'):
            self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.fetches)
        self.assertFalse(self.writes)

    def test_svg_accepts_static_namespaced_shapes_and_internal_references(self):
        root = self.installer.validate_svg(SAFE_SVG)
        self.assertEqual(root.tag, '{http://www.w3.org/2000/svg}svg')
        internal = b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><defs><path id="mark" d="M0 0L10 10"/></defs><use xlink:href="#mark"/></svg>'
        self.installer.validate_svg(internal)

    def test_svg_refuses_declarations_entities_and_processing_instructions(self):
        examples = {
            'external doctype': b'<!DOCTYPE svg SYSTEM "https://invalid.example/remote.dtd"><svg xmlns="http://www.w3.org/2000/svg"/>',
            'internal entity': b'<!DOCTYPE svg [<!ENTITY note "secret">]><svg xmlns="http://www.w3.org/2000/svg"><text>&note;</text></svg>',
            'external entity': b'<!DOCTYPE svg [<!ENTITY note SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg"><text>&note;</text></svg>',
            'stylesheet pi': b'<?xml-stylesheet href="https://invalid.example/style.css"?><svg xmlns="http://www.w3.org/2000/svg"/>',
            'utf16 internal entity': '<!DOCTYPE svg [<!ENTITY note "hidden declaration">]><svg xmlns="http://www.w3.org/2000/svg"><text>&note;</text></svg>'.encode('utf-16'),
        }
        for name, data in examples.items():
            with self.subTest(example=name):
                with self.assertRaises(self.installer.Refusal):
                    self.installer.validate_svg(data)

    def test_svg_refuses_active_foreign_and_external_content(self):
        snippets = [
            '<script>alert(1)</script>',
            '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">foreign</div></foreignObject>',
            '<rect onclick="alert(1)"/>',
            '<rect style="fill:red"/>',
            '<style>@import "https://invalid.example/style.css";</style>',
            '<set attributeName="href" to="https://invalid.example/image.png"/>',
            '<animate attributeName="href" values="https://invalid.example/image.png"/>',
            '<g xmlns="urn:foreign"><rect/></g>',
            '<image href="https://invalid.example/photo.png"/>',
            '<image href="//invalid.example/photo.png"/>',
            '<image href="data:image/png;base64,AAAA"/>',
            '<image href="javascript:alert(1)"/>',
            '<image src="https://invalid.example/photo.png"/>',
            '<image xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://invalid.example/photo.png"/>',
            '<rect fill="url(https://invalid.example/fill.svg#paint)"/>',
            '<rect fill="u\\72l(https://invalid.example/fill.svg#paint)"/>',
            '<rect clip-path="url(\\68ttps://invalid.example/clip.svg#mark)"/>',
            '<g xml:base="https://invalid.example/"><use href="#mark"/></g>',
        ]
        for snippet in snippets:
            with self.subTest(snippet=snippet):
                data = ('<svg xmlns="http://www.w3.org/2000/svg">' + snippet + '</svg>').encode('utf-8')
                with self.assertRaises(self.installer.Refusal):
                    self.installer.validate_svg(data)

    def test_svg_refuses_missing_namespace_malformed_or_nonbyte_input(self):
        for data in [b'<svg/>', b'<html/>', b'<svg xmlns="http://www.w3.org/2000/svg">', b'', '<svg/>']:
            with self.subTest(data=data):
                with self.assertRaises(self.installer.Refusal):
                    self.installer.validate_svg(data)

    def test_staged_svg_requires_safe_xml_and_svg_mime(self):
        session = self.prepare()
        staged = str(session / 'stage' / NEW_SVG)
        with mock.patch.object(self.installer.subprocess, 'check_output', return_value=b'image/svg+xml') as checked:
            self.installer.validate_staged_media('/synthetic/php82', NEW_SVG, staged)
        command = checked.call_args[0][0]
        self.assertEqual(command[-2:], ['--', staged])
        self.assertIn('finfo_file', command[2])
        for mime in [b'text/plain', b'image/png', b'text/html']:
            with self.subTest(mime=mime):
                with mock.patch.object(self.installer.subprocess, 'check_output', return_value=mime):
                    with self.assertRaisesRegex(self.installer.Refusal, 'SVG MIME'):
                        self.installer.validate_staged_media('/synthetic/php82', NEW_SVG, staged)
        Path(staged).write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>')
        with mock.patch.object(self.installer.subprocess, 'check_output') as checked:
            with self.assertRaises(self.installer.Refusal):
                self.installer.validate_staged_media('/synthetic/php82', NEW_SVG, staged)
            checked.assert_not_called()

    def test_staged_icon_accepts_php_png_type_mime_and_exact_dimensions(self):
        session = self.prepare()
        staged = str(session / 'stage' / ICON)
        info = {'width': 512, 'height': 512, 'type': 3, 'mime': 'image/png'}
        with mock.patch.object(self.installer.subprocess, 'check_output', return_value=json.dumps(info).encode('ascii')) as checked:
            self.installer.validate_staged_media('/synthetic/php82', ICON, staged)
        command = checked.call_args[0][0]
        self.assertEqual(command[-2:], ['--', staged])
        self.assertIn('getimagesize', command[2])
        self.assertIn('finfo_file', command[2])

    def test_staged_icon_refuses_decode_failure_and_wrong_type_mime_or_size(self):
        session = self.prepare()
        staged = str(session / 'stage' / ICON)
        good = {'width': 512, 'height': 512, 'type': 3, 'mime': 'image/png'}
        for fields in [{'type': 2}, {'type': '3'}, {'mime': 'image/jpeg'},
                       {'width': 256}, {'height': 513}, {'width': 0},
                       {'height': -1}, {'width': '512'}]:
            with self.subTest(fields=fields):
                info = dict(good)
                info.update(fields)
                with mock.patch.object(self.installer.subprocess, 'check_output', return_value=json.dumps(info).encode('ascii')):
                    with self.assertRaises(self.installer.Refusal):
                        self.installer.validate_staged_media('/synthetic/php82', ICON, staged)
        failure = subprocess.CalledProcessError(1, ['/synthetic/php82', 'getimagesize'])
        with mock.patch.object(self.installer.subprocess, 'check_output', side_effect=failure):
            with self.assertRaises(subprocess.CalledProcessError):
                self.installer.validate_staged_media('/synthetic/php82', ICON, staged)
        with mock.patch.object(self.installer.subprocess, 'check_output', return_value=b'not JSON'):
            with self.assertRaises(ValueError):
                self.installer.validate_staged_media('/synthetic/php82', ICON, staged)

    def test_staged_jpeg_requires_jpeg_header_mime_and_positive_dimensions(self):
        session = self.prepare()
        staged = str(session / 'stage' / NEW_IMAGE)
        good = {'width': 1500, 'height': 900, 'type': 2, 'mime': 'image/jpeg'}
        with mock.patch.object(self.installer.subprocess, 'check_output', return_value=json.dumps(good).encode('ascii')):
            self.installer.validate_staged_media('/synthetic/php82', NEW_IMAGE, staged)
        for fields in [{'type': 3}, {'mime': 'image/png'}, {'width': 0}, {'height': -1}]:
            with self.subTest(fields=fields):
                info = dict(good)
                info.update(fields)
                with mock.patch.object(self.installer.subprocess, 'check_output', return_value=json.dumps(info).encode('ascii')):
                    with self.assertRaises(self.installer.Refusal):
                        self.installer.validate_staged_media('/synthetic/php82', NEW_IMAGE, staged)

    def test_lint_runs_media_validators_for_all_staged_media_before_apply(self):
        records = [{'path': path, 'staged': '/synthetic/stage/' + path}
                   for path in [ICON, NEW_IMAGE, NEW_SVG]]
        with mock.patch.object(self.installer.os.path, 'isfile', return_value=False), \
                mock.patch.object(self.installer.shutil, 'which', return_value='/synthetic/php82'), \
                mock.patch.object(self.installer.subprocess, 'check_output', return_value=b'80230'), \
                mock.patch.object(self.installer.subprocess, 'check_call'), \
                mock.patch.object(self.installer, 'validate_staged_media') as validate, \
                mock.patch('builtins.print'):
            self.real_lint(records)
        self.assertEqual(validate.call_args_list,
                         [mock.call('/synthetic/php82', record['path'], record['staged']) for record in records])

    def test_unsafe_staged_svg_blocks_prepare_before_any_live_replacement(self):
        self.after[NEW_SVG] = b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>'
        data = self.after[NEW_SVG]
        self.installer.FILES[NEW_SVG].update({'sha256': digest(data), 'bytes': len(data)})
        self.installer.GIT_SHAS[NEW_SVG] = hashlib.sha1(('blob ' + str(len(data)) + '\0').encode('ascii') + data).hexdigest()
        self.installer.lint_staged = lambda records: [self.installer.validate_staged_media('/synthetic/php82', record['path'], record['staged'])
                                                     for record in records if record['path'] == NEW_SVG]
        before = self.live_snapshot()
        with mock.patch.object(self.installer.subprocess, 'check_output') as checked:
            with self.assertRaises(self.installer.Refusal):
                self.prepare()
            checked.assert_not_called()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def test_approved_corrupt_baseline_icon_is_replaced_without_baseline_decode(self):
        self.assertFalse(self.before[ICON].startswith(b'\x89PNG'))
        checked_paths = []
        def media_lint(records):
            record = next(record for record in records if record['path'] == ICON)
            checked_paths.append(record['staged'])
            self.installer.validate_staged_media('/synthetic/php82', ICON, record['staged'])
        self.installer.lint_staged = media_lint
        good = {'width': 512, 'height': 512, 'type': 3, 'mime': 'image/png'}
        with mock.patch.object(self.installer.subprocess, 'check_output', return_value=json.dumps(good).encode('ascii')):
            session = self.prepare()
        self.assertEqual(checked_paths, [str(session / 'stage' / ICON)])
        self.assertEqual((session / 'originals' / ICON).read_bytes(), self.before[ICON])
        self.installer.apply(session=str(session))
        self.assertEqual((self.live / ICON).read_bytes(), self.after[ICON])
        self.installer.rollback(str(session))
        self.assertEqual((self.live / ICON).read_bytes(), self.before[ICON])
        self.assertFalse((self.live / NEW_IMAGE).exists())
        self.assertFalse((self.live / NEW_SVG).exists())

    def test_invalid_staged_icon_metadata_blocks_prepare_before_any_live_replacement(self):
        def media_lint(records):
            record = next(record for record in records if record['path'] == ICON)
            self.installer.validate_staged_media('/synthetic/php82', ICON, record['staged'])
        self.installer.lint_staged = media_lint
        before = self.live_snapshot()
        info = {'width': 192, 'height': 192, 'type': 3, 'mime': 'image/png'}
        with mock.patch.object(self.installer.subprocess, 'check_output', return_value=json.dumps(info).encode('ascii')):
            with self.assertRaisesRegex(self.installer.Refusal, '512 by 512'):
                self.prepare()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)

    def assert_no_generated_backup_session(self):
        if self.backups.exists():
            self.assertEqual(set(path.name for path in self.backups.iterdir()), set(['.install.lock']))
        self.assertFalse(self.fetches)
        self.assertFalse(self.lints)
        self.assertFalse(self.writes)

    def assert_current_failure_has_no_repair_or_rollback(self):
        with mock.patch.object(self.installer, 'prepare_unlocked') as prepared, \
                mock.patch.object(self.installer, 'rollback_unlocked') as rolled_back:
            with self.assertRaises(self.installer.Refusal):
                self.installer.apply()
            prepared.assert_not_called()
            rolled_back.assert_not_called()
        self.assert_no_generated_backup_session()

    def test_current_runtime_noop_runs_actual_anonymous_http_proof(self):
        self.install_target_fixture()
        self.installer.verify_http = self.real_http
        opened, seen = self.http_fixture()
        before = self.live_snapshot()
        with mock.patch.object(self.installer.urllib.request, 'urlopen', side_effect=opened):
            result = self.installer.apply()
        self.assertIsInstance(result, self.installer.AlreadyCurrent)
        self.assertIn('manifest.webmanifest?v=3.0.1', seen)
        self.assertIn(ICON + '?v=3.0.3', seen)
        self.assertIn('admin/publication-media.php', seen)
        self.assertEqual(self.live_snapshot(), before)
        self.assert_no_generated_backup_session()

    def test_current_runtime_noop_preserves_existing_stores_without_copying_records(self):
        self.install_target_fixture()
        for name in self.installer.PUBLISHER_STORES:
            store = self.publisher / name
            store.write_bytes(b'{"synthetic":"NEVER-COPY-CURRENT-RECORD-' + name.encode('ascii') + b'"}')
            store.chmod(0o600)
        content = self.live / 'data/content.json'
        content.write_bytes(b'{"synthetic":"current editorial events differ from source"}')
        before = self.live_snapshot()
        self.assertIsInstance(self.installer.apply(), self.installer.AlreadyCurrent)
        self.assertEqual(self.live_snapshot(), before)
        self.assert_no_generated_backup_session()
        for path in self.backups.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'NEVER-COPY-CURRENT-RECORD', path.read_bytes())

    def test_current_runtime_wrong_mode_refuses_without_repair(self):
        self.install_target_fixture()
        (self.live / 'public-presentation.js').chmod(0o640)
        before = self.live_snapshot()
        self.assert_current_failure_has_no_repair_or_rollback()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.http_calls)

    def test_current_runtime_wrong_owner_or_group_refuses_without_repair(self):
        self.install_target_fixture()
        real_read = self.installer.read_file
        for key in ['uid', 'gid']:
            with self.subTest(key=key):
                def altered(path, *args, **kwargs):
                    data, info = real_read(path, *args, **kwargs)
                    if Path(path) == self.live / 'index.php':
                        info = dict(info)
                        info[key] += 1
                    return data, info
                before = self.live_snapshot()
                with mock.patch.object(self.installer, 'read_file', side_effect=altered):
                    self.assert_current_failure_has_no_repair_or_rollback()
                self.assertEqual(self.live_snapshot(), before)

    def test_current_runtime_bad_guard_refuses_without_repair(self):
        self.install_target_fixture()
        target = self.live / 'admin/publication-projects.php'
        target.write_bytes(b'<?php /* newer guarded projects source */ ?>')
        before = self.live_snapshot()
        self.assert_current_failure_has_no_repair_or_rollback()
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.http_calls)

    def test_current_runtime_bad_http_refuses_without_repair(self):
        self.install_target_fixture()
        self.installer.verify_http = mock.Mock(side_effect=self.installer.Refusal('Synthetic HTTP proof refused'))
        before = self.live_snapshot()
        self.assert_current_failure_has_no_repair_or_rollback()
        self.installer.verify_http.assert_called_once_with()
        self.assertEqual(self.live_snapshot(), before)

    def test_current_runtime_file_replacement_during_http_refuses_without_repair(self):
        self.install_target_fixture()
        target = self.live / ICON
        old = target.stat()
        def changed_during_http():
            newer = self.root / 'newer-current-icon.png'
            newer.write_bytes(target.read_bytes())
            newer.chmod(0o644)
            os.utime(str(newer), ns=(old.st_atime_ns, old.st_mtime_ns))
            os.replace(str(newer), str(target))
        self.installer.verify_http = changed_during_http
        self.assert_current_failure_has_no_repair_or_rollback()
        self.assertNotEqual(target.stat().st_ino, old.st_ino)
        self.assert_release_bytes()

    def test_current_runtime_publisher_creation_during_http_refuses_and_preserves_new_store(self):
        self.install_target_fixture()
        store = self.publisher / 'publications.json'
        fresh = b'{"synthetic":"publisher save completed during current-proof"}'
        self.installer.verify_http = lambda: store.write_bytes(fresh)
        self.assert_current_failure_has_no_repair_or_rollback()
        self.assertEqual(store.read_bytes(), fresh)
        self.assert_release_bytes()

    def test_current_runtime_publisher_edit_during_http_refuses_and_preserves_edit(self):
        self.install_target_fixture()
        store = self.publisher / 'publication-media.json'
        store.write_bytes(b'{"synthetic":"old media library"}')
        changed = b'{"synthetic":"new media library"}'
        self.installer.verify_http = lambda: store.write_bytes(changed)
        self.assert_current_failure_has_no_repair_or_rollback()
        self.assertEqual(store.read_bytes(), changed)
        self.assert_release_bytes()

    def test_current_runtime_guard_edit_during_http_refuses_and_preserves_edit(self):
        self.install_target_fixture()
        target = self.live / 'admin/publication-media.php'
        changed = b'<?php /* newer media source during HTTP proof */ ?>'
        self.installer.verify_http = lambda: target.write_bytes(changed)
        self.assert_current_failure_has_no_repair_or_rollback()
        self.assertEqual(target.read_bytes(), changed)
        self.assert_release_bytes()

    def test_current_runtime_editorial_edit_during_http_refuses_and_preserves_edit(self):
        self.install_target_fixture()
        target = self.live / 'data/content.json'
        changed = b'{"synthetic":"newer editorial content during HTTP proof"}'
        self.installer.verify_http = lambda: target.write_bytes(changed)
        self.assert_current_failure_has_no_repair_or_rollback()
        self.assertEqual(target.read_bytes(), changed)
        self.assert_release_bytes()

    def test_current_runtime_missing_publisher_directory_refuses_without_repair(self):
        self.install_target_fixture()
        self.installer.shutil.rmtree(str(self.publisher))
        before = self.live_snapshot()
        self.assert_current_failure_has_no_repair_or_rollback()
        self.assertEqual(self.live_snapshot(), before)

    def test_current_runtime_busy_publisher_lock_refuses_promptly_without_repair(self):
        self.install_target_fixture()
        with (self.publisher / 'publications.json.lock').open('r+b') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            started = time.monotonic()
            self.assert_current_failure_has_no_repair_or_rollback()
            self.assertLess(time.monotonic() - started, 1)
        self.assert_release_bytes()

    def test_missing_current_asset_is_partial_and_refuses_before_download(self):
        self.install_target_fixture()
        (self.live / NEW_SVG).unlink()
        before = self.live_snapshot()
        with mock.patch.object(self.installer, 'rollback_unlocked') as rolled_back:
            with self.assertRaises(self.installer.Refusal):
                self.installer.apply()
            rolled_back.assert_not_called()
        self.assertEqual(self.live_snapshot(), before)
        self.assert_no_generated_backup_session()

    def test_explicit_prepared_session_cannot_bypass_its_baseline_for_current_runtime(self):
        session = self.prepare()
        self.install_target_fixture()
        before = self.live_snapshot()
        with self.assertRaises(self.installer.Refusal):
            self.installer.apply(session=str(session))
        self.assertEqual(self.live_snapshot(), before)
        self.assertFalse(self.writes)
        self.assertFalse(self.http_calls)

    def test_current_runtime_cli_reports_noop_without_a_fake_session(self):
        self.install_target_fixture()
        with mock.patch.object(self.installer.sys, 'argv', [str(INSTALLER), 'apply']), \
                mock.patch('builtins.print') as printed:
            self.assertEqual(self.installer.main(), 0)
        messages = [str(call[0][0]) for call in printed.call_args_list]
        self.assertTrue(any('already present' in message for message in messages))
        self.assertTrue(any('No backup session' in message for message in messages))
        self.assertFalse(any('Private session:' in message for message in messages))
        self.assert_no_generated_backup_session()


if __name__ == '__main__':
    unittest.main(verbosity=2)
