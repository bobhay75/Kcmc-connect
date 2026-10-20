#!/usr/bin/env python3
"""Temporary-file acceptance for the mandatory, read-only deployment interlock."""
from __future__ import print_function

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from visual_source_layer import FIXTURE as VISUAL_FIXTURE, FIXTURE_SHA256 as VISUAL_FIXTURE_SHA256
from welcome_home_source_layer import WelcomeLayer

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools/check-deployment-divergence.py'
TASK = '    - python3 -I -B tools/check-deployment-divergence.py || exit 1\n'


def module():
    spec = importlib.util.spec_from_file_location('deployment_guard_under_test', str(HELPER))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def snapshot(root):
    result = {}
    for current, dirs, files in os.walk(str(root), followlinks=False):
        for name in dirs + files:
            path = Path(current) / name
            info = os.lstat(str(path))
            content = path.read_bytes() if stat.S_ISREG(info.st_mode) else None
            result[str(path.relative_to(root))] = (content, info.st_mode, info.st_uid,
                info.st_gid, info.st_nlink, info.st_ino, info.st_mtime_ns, info.st_ctime_ns)
    return result


class DeploymentGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kcmc-deployment-guard-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.live = self.root / 'live'
        self.source.mkdir(mode=0o700)
        self.live.mkdir(mode=0o700)
        self.m = module()
        self.m.SOURCE, self.m.LIVE = self.source, self.live
        for root in (self.source, self.live):
            for name in self.m.FILES:
                (root / name).write_bytes(('synthetic identical ' + name + '\n').encode())
                (root / name).chmod(0o644)

    def invoke(self, argv=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, 'argv', argv or ['check-deployment-divergence.py']), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = self.m.main()
        return result, out.getvalue(), err.getvalue()

    def refused_unchanged(self):
        before = snapshot(self.root)
        result, out, err = self.invoke()
        self.assertEqual(result, 1, out + err)
        self.assertIn('REFUSED:', err)
        self.assertEqual(snapshot(self.root), before)
        return out + err

    def test_production_paths_scope_and_no_override(self):
        m = module()
        self.assertEqual(m.SOURCE, ROOT / 'KCMC-Connect-Phase6-Recreated')
        self.assertEqual(str(m.LIVE), '/home/bobsome1/public_html/kcmc-connect')
        self.assertEqual(m.FILES, ('index.php', 'public-presentation.css', 'sw.js', '.htaccess'))
        text = HELPER.read_text()
        self.assertNotIn('getenv', text)
        self.assertNotIn('environ', text)
        self.assertNotIn('argparse', text)

    def test_identical_files_pass_without_writes(self):
        before = snapshot(self.root)
        result, out, err = self.invoke()
        self.assertEqual((result, err), (0, ''))
        self.assertIn('full application parity is not established', out)
        self.assertEqual(snapshot(self.root), before)

    def test_each_protected_difference_refuses_and_never_prints_contents(self):
        for name in self.m.FILES:
            with self.subTest(name=name):
                p = self.live / name
                original = p.read_bytes()
                p.write_bytes(b'SYNTHETIC_PRIVATE_SETTING_DO_NOT_PRINT\n')
                text = self.refused_unchanged()
                self.assertNotIn('SYNTHETIC_PRIVATE_SETTING_DO_NOT_PRINT', text)
                self.assertNotIn(hashlib.sha256(p.read_bytes()).hexdigest(), text)
                p.write_bytes(original)

    def reviewed_fish_bundle(self, variant):
        raw = (ROOT / 'tools/kcmc-fish-home-oct15/runtime-reviewed.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '5746e5f5c97cee32c0380ddae1de763c4b5bcd6f20da7c18c4e13325d6bfec3c')
        reviewed = json.loads(raw)
        bundle = {}
        for name in ('index.php', 'public-presentation.css', 'sw.js'):
            content = (ROOT / 'tools/kcmc-fish-home-oct15/evidence' / variant / name).read_bytes()
            record = reviewed[variant][name]
            self.assertEqual(hashlib.sha256(content).hexdigest(), record['before_sha256'])
            for old, new in record['replacements']:
                self.assertEqual(content.count(old.encode()), 1)
                content = content.replace(old.encode(), new.encode(), 1)
            self.assertEqual(hashlib.sha256(content).hexdigest(), record['after_sha256'])
            bundle[name] = content
        return bundle

    def test_known_installed_calendar_fish_bundle_refuses_against_historical_canonical_source(self):
        canonical_bundle = self.reviewed_fish_bundle('main130')
        installed_bundle = self.reviewed_fish_bundle('livecalendar')
        for name, canonical in canonical_bundle.items():
            (self.source / name).write_bytes(canonical)
            (self.live / name).write_bytes(installed_bundle[name])
        self.refused_unchanged()

    def test_known_installed_calendar_fish_bundle_refuses_against_reviewed_welcome_source(self):
        raw = (ROOT / VISUAL_FIXTURE).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), VISUAL_FIXTURE_SHA256)
        visual = json.loads(raw)
        canonical_bundle = self.reviewed_fish_bundle('main130')
        installed_bundle = self.reviewed_fish_bundle('livecalendar')
        welcome = WelcomeLayer()
        # The reviewed follow-up changes the administration destination and
        # notification worker. Keep the installed historical tuple unchanged:
        # broad deployment must still refuse it against this exact new source.
        followup_sha = {
            'index.php': 'ce49b8c05e602175223dfcf0e6f7c64e29c9b8c9930aaf2c172121340874f330',
            'sw.js': '459c6c13be36bf9f9189267f6038513a803c931a06eef542c7a48a652165d754',
        }
        for name, historical in canonical_bundle.items():
            # Keep this exact October 19 proof when a separately reviewed
            # branding layer changes current bytes. WelcomeLayer verifies the
            # new bytes before exposing their immutable welcome preimage.
            canonical = welcome.brand_before.get(name,
                (ROOT / 'KCMC-Connect-Phase6-Recreated' / name).read_bytes())
            expected_sha = followup_sha[name] if name in followup_sha else (
                visual['modified'][name]['after_sha256'] if name in visual['modified']
                else hashlib.sha256(historical).hexdigest())
            self.assertEqual(hashlib.sha256(canonical).hexdigest(), expected_sha)
            (self.source / name).write_bytes(canonical)
            (self.live / name).write_bytes(installed_bundle[name])
        self.refused_unchanged()

    def test_known_installed_calendar_fish_bundle_refuses_against_current_brand_source(self):
        welcome = WelcomeLayer()
        installed_bundle = self.reviewed_fish_bundle('livecalendar')
        for name, installed in installed_bundle.items():
            canonical = (ROOT / 'KCMC-Connect-Phase6-Recreated' / name).read_bytes()
            if name in welcome.brand['modified']:
                self.assertEqual(hashlib.sha256(canonical).hexdigest(),
                    welcome.brand['modified'][name]['after_sha256'])
            (self.source / name).write_bytes(canonical)
            (self.live / name).write_bytes(installed)
        self.refused_unchanged()

    def test_private_owner_setting_alone_blocks_broad_deployment(self):
        name = '.htaccess'
        original = (self.live / name).read_bytes()
        (self.live / name).write_bytes(original + b'SetEnv KCMC_OPERATIONS_OWNER_USER_ID synthetic-owner-private\n')
        text = self.refused_unchanged()
        self.assertNotIn('synthetic-owner-private', text)
        self.assertNotIn('SetEnv', text)

    def test_missing_files_refuse(self):
        for root in (self.source, self.live):
            for name in self.m.FILES:
                p = root / name
                data = p.read_bytes()
                p.unlink()
                self.refused_unchanged()
                p.write_bytes(data)

    def test_missing_root_refuses_without_creation(self):
        self.m.LIVE = self.root / 'absent'
        self.refused_unchanged()
        self.assertFalse(self.m.LIVE.exists())

    def test_symlink_leaf_or_ancestor_refuses(self):
        for root in (self.source, self.live):
            p = root / 'index.php'
            saved = self.root / 'saved'
            p.rename(saved)
            p.symlink_to(saved)
            self.refused_unchanged()
            p.unlink()
            saved.rename(p)
        actual = self.root / 'actual-live'
        self.live.rename(actual)
        self.live.symlink_to(actual, target_is_directory=True)
        self.refused_unchanged()

    def test_hardlink_refuses(self):
        for root in (self.source, self.live):
            link = self.root / 'extra-link'
            os.link(str(root / '.htaccess'), str(link))
            self.refused_unchanged()
            link.unlink()

    def test_directory_and_fifo_refuse_without_blocking(self):
        for root in (self.source, self.live):
            p = root / 'sw.js'
            data = p.read_bytes()
            p.unlink()
            p.mkdir()
            self.refused_unchanged()
            p.rmdir()
            os.mkfifo(str(p), 0o600)
            self.refused_unchanged()
            p.unlink()
            p.write_bytes(data)

    def test_unsafe_file_and_root_modes_refuse(self):
        for root in (self.source, self.live):
            for mode in (0o664, 0o666, 0o4644):
                (root / 'index.php').chmod(mode)
                self.refused_unchanged()
                (root / 'index.php').chmod(0o644)
            root.chmod(0o770)
            self.refused_unchanged()
            root.chmod(0o700)

    def test_group_or_world_writable_nonsticky_ancestor_refuses(self):
        for mode in (0o770, 0o777):
            self.root.chmod(mode)
            self.refused_unchanged()
        self.root.chmod(0o700)

    def test_foreign_uid_or_gid_refuses(self):
        for name in ('getuid', 'getgid'):
            with mock.patch.object(self.m.os, name, return_value=getattr(os, name)() + 1):
                self.refused_unchanged()

    def test_oversized_file_refuses(self):
        self.m.LIMIT = 3
        self.refused_unchanged()

    def test_concurrent_inplace_edit_is_preserved_and_refused(self):
        original = self.m.os.read
        changed = [False]
        target = self.live / 'index.php'
        def mutate(fd, size):
            data = original(fd, size)
            if not changed[0]:
                changed[0] = True
                target.write_bytes(b'NEWER_SYNTHETIC_EDIT_PRESERVED\n')
            return data
        with mock.patch.object(self.m.os, 'read', side_effect=mutate):
            result, out, err = self.invoke()
        self.assertEqual(result, 1)
        self.assertEqual(target.read_bytes(), b'NEWER_SYNTHETIC_EDIT_PRESERVED\n')
        self.assertNotIn('NEWER_SYNTHETIC_EDIT_PRESERVED', out + err)

    def test_replacement_after_read_is_preserved_and_refused(self):
        original = self.m.read_regular
        target = self.source / 'index.php'
        changed = [False]
        def replace(path):
            result = original(path)
            if path == self.live / '.htaccess' and not changed[0]:
                changed[0] = True
                fresh = self.root / 'fresh'
                fresh.write_bytes(target.read_bytes())
                os.replace(str(fresh), str(target))
            return result
        with mock.patch.object(self.m, 'read_regular', side_effect=replace):
            result, out, err = self.invoke()
        self.assertEqual(result, 1, out + err)
        self.assertTrue(changed[0])

    def test_fifo_race_uses_nonblocking_open_and_refuses(self):
        original = self.m.os.open
        target = self.live / 'sw.js'
        changed = [False]
        def replace(path, flags):
            self.assertTrue(flags & os.O_NOFOLLOW)
            self.assertTrue(flags & os.O_NONBLOCK)
            if path == str(target) and not changed[0]:
                changed[0] = True
                target.unlink()
                os.mkfifo(str(target), 0o600)
            return original(path, flags)
        with mock.patch.object(self.m.os, 'open', side_effect=replace):
            result, out, err = self.invoke()
        self.assertEqual(result, 1, out + err)
        self.assertTrue(stat.S_ISFIFO(os.lstat(str(target)).st_mode))

    def test_extra_arguments_refuse_and_do_not_print_secrets(self):
        before = snapshot(self.root)
        result, out, err = self.invoke(['guard', '--allow', 'SYNTHETIC_SECRET'])
        self.assertEqual(result, 1)
        self.assertNotIn('SYNTHETIC_SECRET', out + err)
        self.assertEqual(snapshot(self.root), before)

    def test_oserror_never_prints_exception_path_or_contents(self):
        with mock.patch.object(self.m, 'check', side_effect=OSError('SYNTHETIC_SECRET')):
            result, out, err = self.invoke()
        self.assertEqual(result, 1)
        self.assertNotIn('SYNTHETIC_SECRET', out + err)

    def test_cpanel_adds_only_first_isolated_python_task(self):
        fixture_path = ROOT / 'tests/fixtures/deployment-preflight-reviewed.json'
        fixture = json.loads(fixture_path.read_text())
        self.assertEqual(set(fixture), {'source_commit', 'files'})
        self.assertEqual(set(fixture['files']), {'.cpanel.yml'})
        f = fixture['files']['.cpanel.yml']
        current = (ROOT / '.cpanel.yml').read_bytes()
        self.assertEqual(hashlib.sha256(current).hexdigest(), f['after_sha256'])
        self.assertEqual(f['replacements'], [['deployment:\n  tasks:\n', 'deployment:\n  tasks:\n' + TASK]])
        self.assertEqual(current.count(TASK.encode()), 1)
        previous = current.replace(TASK.encode(), b'', 1)
        self.assertEqual(hashlib.sha256(previous).hexdigest(), f['before_sha256'])
        tasks = [line for line in current.decode().splitlines() if line.startswith('    - ')]
        self.assertEqual(tasks[0], TASK.rstrip('\n'))
        self.assertEqual(len(tasks), 9)
        self.assertEqual([line for line in previous.decode().splitlines() if line.startswith('    - ')], tasks[1:])

    def test_explicit_task_exit_stops_following_commands_without_shell_errexit(self):
        # Only this test driver overrides fixed roots through the module API.
        # No production CLI or environment path override exists.
        driver = self.root / 'fixture-driver.py'
        driver.write_text('import importlib.util, sys\nfrom pathlib import Path\n'
            + 'spec = importlib.util.spec_from_file_location("fixture_guard", ' + repr(str(HELPER)) + ')\n'
            + 'm = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n'
            + 'm.SOURCE = Path(' + repr(str(self.source)) + ')\n'
            + 'm.LIVE = Path(' + repr(str(self.live)) + ')\n'
            + 'sys.exit(m.main())\n')
        marker = self.root / 'following-task'
        command = shlex.quote(sys.executable) + ' -I -B ' + shlex.quote(str(driver)) + ' || exit 1\n'
        following = shlex.quote(sys.executable) + ' -c ' + shlex.quote(
            'from pathlib import Path; Path(' + repr(str(marker)) + ').write_text("followed")')
        original = (self.live / '.htaccess').read_bytes()
        (self.live / '.htaccess').write_bytes(b'SYNTHETIC_PRIVATE_OWNER_SETTING\n')
        before = snapshot(self.source), snapshot(self.live)
        result = subprocess.run(['bash', '-c', command + following], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(marker.exists())
        self.assertNotIn('SYNTHETIC_PRIVATE_OWNER_SETTING', result.stdout + result.stderr)
        self.assertEqual((snapshot(self.source), snapshot(self.live)), before)
        (self.live / '.htaccess').write_bytes(original)
        before = snapshot(self.source), snapshot(self.live)
        result = subprocess.run(['bash', '-c', command + following], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(marker.read_text(), 'followed')
        self.assertEqual((snapshot(self.source), snapshot(self.live)), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
