#!/usr/bin/env python3
"""Exact six-file provenance and isolated host transaction acceptance."""
from __future__ import print_function
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import derive_installer as derive

HERE = Path(__file__).resolve().parent
CANDIDATE = '--candidate' in sys.argv
if CANDIDATE: sys.argv.remove('--candidate')
PREFIX = 'candidate-' if CANDIDATE else ''
GIT_ROOT = None
if '--git-root' in sys.argv:
    i = sys.argv.index('--git-root'); GIT_ROOT = Path(sys.argv[i + 1]); del sys.argv[i:i + 2]


def sha(content): return hashlib.sha256(content).hexdigest()


def identity(path):
    info = path.lstat()
    return tuple(getattr(info, key) for key in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
                                             'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def loaded(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


class Fixture:
    def __init__(self, image='before', mode=0o644, variant='main'):
        self.temp = tempfile.TemporaryDirectory(prefix='kcmc-follow-up-'); self.root = Path(self.temp.name)
        self.app = self.root / 'app'; self.app.mkdir()
        self.w = loaded(HERE / (PREFIX + 'installer.py'), 'isolated_health_actions')
        self.variant = variant; self.w.backup_root = lambda name: self.root / ('private-' + name)
        self.m = self.w.load_engine(variant); self.m.APP = self.app
        self.m.UID, self.m.GID = os.getuid(), os.getgid()
        self.w.load_engine = lambda variant=None: self.m
        self.before = {path: (HERE / 'evidence/before' / path).read_bytes() for path in self.m.PATHS}
        self.after = {path: (HERE / 'evidence/after' / path).read_bytes() for path in self.m.PATHS}
        self.before['index.php'] = (HERE / 'evidence/public' / variant / 'index-before.php').read_bytes()
        self.after['index.php'] = (HERE / 'evidence/public' / variant / 'index-after.php').read_bytes()
        for path, content in (self.after if image == 'after' else self.before).items(): self.write(path, content, mode)
        self.guards = self.w.prerequisites(self.m)
        for path in self.guards:
            source = HERE / ('evidence/public/' + variant if path in self.m.PUBLIC_PREREQUISITES else 'evidence/prerequisite') / path
            self.write(path, source.read_bytes())
        self.guard_before = {path: (self.app / path).read_bytes() for path in self.guards}
        self.guard_ids = {path: identity(self.app / path) for path in self.guards}
        self.sentinels = {'config.php': b'<?php // existing owner configuration\n', '.htaccess': b'# host rules\n',
            'data/content.json': b'{"editorial":"preserved"}', 'data/private/users.json': b'{"roles":"unchanged"}',
            'data/private/timeclock.json': b'{"time":"unchanged"}', 'data/private/payroll-settings.json': b'{"channel":"off"}',
            'data/private/prayers.json': b'{"care":"private"}', '.git/HEAD': b'ref: refs/heads/main\n'}
        for path, content in self.sentinels.items(): self.write(path, content, 0o600)
        self.sentinel_ids = {path: identity(self.app / path) for path in self.sentinels}
        self.real_choose = self.w.choose_php82_cli
        self.w.choose_php82_cli = lambda: ('/synthetic/php82', '8.2.34')
    def close(self): self.temp.cleanup()
    def write(self, path, content, mode=0o644):
        target = self.app / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content); target.chmod(mode)
    def foreign(self, path, content=None):
        target = self.app / path; temporary = self.root / 'foreign'
        temporary.write_bytes(target.read_bytes() if content is None else content); temporary.chmod(0o644)
        os.replace(str(temporary), str(target))
    def php(self, argv, **kwargs):
        assert argv[:2] == ['/synthetic/php82', '-n'], argv
        if argv[-1] == '-v': return b'PHP 8.2.34 (cli)\n'
        assert argv[2] == '-l' and Path(argv[3]).name in ('stage-2.code', 'stage-3.code', 'stage-4.code', 'stage-5.code') and Path(argv[3]).is_file(), argv
        return b'No syntax errors detected\n'
    def cli(self, *args):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['installer.py'] + list(args)), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = self.w.main()
        return code, output.getvalue()
    def apply(self):
        with mock.patch.object(subprocess, 'check_output', side_effect=self.php): return self.cli('apply')
    def preserved(self, except_guard=None):
        for path, content in self.sentinels.items():
            assert (self.app / path).read_bytes() == content and identity(self.app / path) == self.sentinel_ids[path], path
        for path, content in self.guard_before.items():
            if path != except_guard:
                assert (self.app / path).read_bytes() == content and identity(self.app / path) == self.guard_ids[path], path
    def session(self): return next(self.m.BACKUPS.glob('repair-*'))


class Transactions(unittest.TestCase):
    def fixture(self, *args, **kwargs):
        f = Fixture(*args, **kwargs); self.addCleanup(f.close); return f
    def test_exact_existing_target_apply_idempotence_rollback_preserves_both_modes(self):
        for mode in (0o644, 0o664):
            f = self.fixture(mode=mode)
            code, text = f.cli('check'); self.assertEqual(code, 0, text); self.assertFalse(f.m.BACKUPS.exists())
            with mock.patch.object(subprocess, 'check_output', side_effect=f.php) as calls: code, text = f.cli('apply')
            self.assertEqual(code, 0, text); self.assertEqual(sum(c[0][0][2] == '-l' for c in calls.call_args_list), 4)
            for path in f.m.PATHS: self.assertEqual((f.app / path).read_bytes(), f.after[path])
            self.assertEqual((f.app / 'member/notifications.php').stat().st_mode & 0o777, mode)
            target = identity(f.app / 'member/notifications.php'); journal = identity(f.session() / 'journal.json')
            with mock.patch.object(f.w, 'choose_php82_cli', side_effect=AssertionError('No PHP needed')): code, text = f.cli('apply')
            self.assertEqual(code, 0, text); self.assertEqual(identity(f.app / 'member/notifications.php'), target)
            self.assertEqual(identity(f.session() / 'journal.json'), journal)
            code, text = f.cli('rollback', '--session', f.session().name); self.assertEqual(code, 0, text)
            self.assertEqual((f.app / 'member/notifications.php').read_bytes(), f.before['member/notifications.php']); f.preserved()
    def test_unknown_missing_unsafe_link_or_mode_refuses_without_backup(self):
        for kind in ('unknown', 'missing', 'symlink', 'hardlink', 'mode'):
            f = self.fixture(); target = f.app / 'member/notifications.php'
            if kind == 'unknown': f.foreign('member/notifications.php', b'<?php // unknown local patch\n')
            elif kind == 'missing': target.unlink()
            elif kind == 'symlink':
                link = f.root / 'original'; target.rename(link); target.symlink_to(link)
            elif kind == 'hardlink': os.link(str(target), str(f.root / 'extra-link'))
            else: target.chmod(0o666)
            code, text = f.apply(); self.assertEqual(code, 1, kind + text); self.assertFalse(f.m.BACKUPS.exists()); f.preserved()
    def test_every_actual_readonly_prerequisite_is_required(self):
        seed = self.fixture()
        for path in seed.guards:
            f = self.fixture(); f.foreign(path, b'<?php // independent unreviewed code\n')
            code, text = f.apply(); self.assertEqual(code, 1, path + text)
            self.assertFalse(f.m.BACKUPS.exists()); f.preserved(except_guard=path)
    def test_staged_tamper_or_php_error_cannot_replace_live_code(self):
        for kind in ('tamper', 'syntax', 'missing-cli'):
            f = self.fixture(); lint = f.m.lint
            def changed(session):
                (session / 'stage-2.code').write_bytes(b'<?php // forged\n'); return lint(session)
            if kind == 'tamper': f.m.lint = changed
            if kind == 'syntax': f.m.lint = lambda session: (_ for _ in ()).throw(subprocess.CalledProcessError(255, 'php'))
            if kind == 'missing-cli':
                f.w.choose_php82_cli = f.real_choose; f.w.php82_candidates = lambda: []
            code, text = f.apply(); self.assertEqual(code, 1, kind + text)
            self.assertEqual((f.app / 'member/notifications.php').read_bytes(), f.before['member/notifications.php'])
            if kind == 'missing-cli': self.assertFalse(f.m.BACKUPS.exists())
            f.preserved()
    def test_owned_checkpoint_failure_restores_original(self):
        f = self.fixture(); journal = f.m.journal; failed = [False]
        def stopped(session, value):
            if value['phase'] == 'applying' and value['files']['member/notifications.php']['installed'] is not None and value['intent'] is None and not failed[0]:
                failed[0] = True; raise OSError('Synthetic owned checkpoint failure')
            return journal(session, value)
        with mock.patch.object(f.m, 'journal', side_effect=stopped): code, text = f.apply()
        self.assertEqual(code, 1, text); self.assertTrue(failed[0]); self.assertEqual(f.m.load(f.session())['phase'], 'rolled_back')
        self.assertEqual((f.app / 'member/notifications.php').read_bytes(), f.before['member/notifications.php']); f.preserved()
    def test_ambiguous_move_retains_journal_and_refuses_retry(self):
        f = self.fixture(); replace = f.m.replace
        def interrupted(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source == 'stage-2.code': raise OSError('Synthetic ambiguous replacement')
            return result
        with mock.patch.object(f.m, 'replace', side_effect=interrupted): code, text = f.apply()
        self.assertEqual(code, 1, text); value = f.m.load(f.session())
        self.assertEqual(value['phase'], 'manual_review'); self.assertIn('member/notifications.php', value['uncertain'])
        code, text = f.apply(); self.assertEqual(code, 1, text); self.assertNotIn('CHECK ALREADY_REPAIRED', text); f.preserved()
    def test_same_bytes_concurrent_prerequisite_change_prevents_success(self):
        f = self.fixture(); journal = f.m.journal; path = 'lib/screen-navigation.php'
        def changed(session, value):
            result = journal(session, value)
            if value['phase'] == 'applied': f.foreign(path)
            return result
        with mock.patch.object(f.m, 'journal', side_effect=changed): code, text = f.apply()
        self.assertEqual(code, 1, text); self.assertNotIn('CHECK ALREADY_REPAIRED', text); f.preserved(except_guard=path)
    def test_noop_cannot_hide_same_bytes_target_replacement(self):
        f = self.fixture(image='after'); apply = f.m.apply
        def raced(): result = apply(); f.foreign('member/notifications.php'); return result
        with mock.patch.object(f.m, 'apply', side_effect=raced): code, text = f.cli('apply')
        self.assertEqual(code, 1, text); self.assertIn('Code lease changed', text)
    def test_fixed_roots_scope_and_identity_ignore_environment(self):
        w = loaded(HERE / (PREFIX + 'installer.py'), 'fixed_scope')
        with mock.patch.dict(os.environ, {'KCMC_APP_ROOT': '/tmp/forged', 'KCMC_PRIVATE_DATA_DIR': '/tmp/private', 'KCMC_UID': '0'}): m = w.load_engine('main')
        self.assertEqual(m.APP, Path('/home/bobsome1/public_html/kcmc-connect'))
        self.assertEqual(m.BACKUPS, Path('/home/bobsome1/kcmc-follow-up-main-backups'))
        self.assertEqual((m.UID, m.GID), (2162, 2147)); self.assertEqual(m.PATHS, derive.PATHS); self.assertEqual(m.DEPENDENCIES, derive.DEPENDENCIES)

    def test_both_public_variants_apply_and_retain_unique_variant(self):
        for variant in ('main','livecalendar'):
            for mode in (0o644,0o664):
                f=self.fixture(variant=variant,mode=mode)
                self.assertEqual(f.w.select_variant(f.m),variant)
                code,text=f.apply();self.assertEqual(code,0,text)
                self.assertEqual(f.w.select_variant(f.m),variant)
                for path in f.m.PATHS:
                    self.assertEqual((f.app/path).read_bytes(),f.after[path])
                    self.assertEqual((f.app/path).stat().st_mode & 0o777,mode)
                code,text=f.cli('rollback','--session',f.session().name);self.assertEqual(code,0,text)
                for path in f.m.PATHS:self.assertEqual((f.app/path).read_bytes(),f.before[path])
                f.preserved()
    def test_historical_installed_stylesheet_is_accepted_without_replacement(self):
        historical = HERE.parent / 'kcmc-app-theme-oct15/evidence/public/livecalendar/public-presentation.css'
        content = historical.read_bytes()
        self.assertEqual((sha(content), len(content)),
            ('b08824180406891f3ff784967dc507e62488b4cb9b12f3a81347731be61a5acb', 17233))
        f = self.fixture(variant='livecalendar')
        self.assertEqual((f.app / 'public-presentation.css').read_bytes(), content)
        before = identity(f.app / 'public-presentation.css')
        code, text = f.cli('check'); self.assertEqual(code, 0, text)
        code, text = f.apply(); self.assertEqual(code, 0, text)
        self.assertEqual((f.app / 'public-presentation.css').read_bytes(), content)
        self.assertEqual(identity(f.app / 'public-presentation.css'), before)
        code, text = f.cli('rollback', '--session', f.session().name); self.assertEqual(code, 0, text)
        self.assertEqual(identity(f.app / 'public-presentation.css'), before); f.preserved()
    def test_crossed_canonical_and_historical_stylesheets_refuse_without_backup(self):
        for variant, other in (('main', 'livecalendar'), ('livecalendar', 'main')):
            for image in ('before', 'after'):
                f = self.fixture(variant=variant, image=image)
                content = (HERE / 'evidence/public' / other / 'public-presentation.css').read_bytes()
                f.foreign('public-presentation.css', content)
                for action in ('check', 'apply'):
                    code, text = f.cli(action)
                    self.assertEqual(code, 1, variant + '/' + image + text)
                    self.assertIn('Approved current code prerequisite required: public-presentation.css', text)
                    self.assertFalse(f.m.BACKUPS.exists())
                for path in f.m.PATHS:
                    self.assertEqual((f.app / path).read_bytes(), (f.after if image == 'after' else f.before)[path])
                f.preserved(except_guard='public-presentation.css')
    def test_unknown_index_can_be_diagnosed_without_authorizing_repair(self):
        f=self.fixture();f.foreign('index.php',b'<?php // unknown local homepage change\n')
        code,text=f.cli('diagnose');self.assertEqual(code,0,text)
        self.assertIn('CODE index.php sha256=',text);self.assertNotIn('CHECK READY',text)
        self.assertFalse(f.m.BACKUPS.exists());f.preserved()
        code,text=f.apply();self.assertEqual(code,1,text);self.assertFalse(f.m.BACKUPS.exists())
    def test_mixed_target_bundle_refuses_before_backup(self):
        for path in derive.PATHS:
            f=self.fixture();f.write(path,f.after[path])
            code,text=f.apply();self.assertEqual(code,1,path+text)
            self.assertIn('Mixed before/after',text);self.assertFalse(f.m.BACKUPS.exists());f.preserved()
    def test_uncertain_consumers_retain_all_needed_providers(self):
        for consumer in ('member/notifications.php','admin/push.php'):
            f=self.fixture();replace=f.m.replace;number=f.m.PATHS.index(consumer)
            def interrupted(source,target,**kwargs):
                result=replace(source,target,**kwargs)
                if source=='stage-'+str(number)+'.code':raise OSError('Ambiguous consumer replacement')
                return result
            with mock.patch.object(f.m,'replace',side_effect=interrupted):code,text=f.apply()
            self.assertEqual(code,1,text);value=f.m.load(f.session())
            self.assertEqual(value['phase'],'manual_review');self.assertIn(consumer,value['uncertain'])
            expected={'sw.js','member/push-settings.js','member/notifications.php'}
            if consumer=='admin/push.php':expected.add(consumer)
            for path in f.m.PATHS:self.assertEqual((f.app/path).read_bytes(),(f.after if path in expected else f.before)[path])
            code,text=f.apply();self.assertEqual(code,1,text);f.preserved()
    def test_script_recreated_after_completed_restore_keeps_worker(self):
        f=self.fixture();code,text=f.apply();self.assertEqual(code,0,text)
        journal=f.m.journal;recreated=[False];foreign=[None]
        def raced(session,value):
            result=journal(session,value)
            if value['phase']=='rolling_back' and value['files']['member/push-settings.js']['installed'] is None and not recreated[0]:
                recreated[0]=True;f.foreign('member/push-settings.js',f.after['member/push-settings.js'])
                foreign[0]=identity(f.app/'member/push-settings.js')
            return result
        with mock.patch.object(f.m,'journal',side_effect=raced):code,text=f.cli('rollback','--session',f.session().name)
        self.assertEqual(code,1,text);self.assertTrue(recreated[0])
        value=f.m.load(f.session());self.assertEqual(value['phase'],'manual_review')
        self.assertIn('member/push-settings.js',value['uncertain'])
        self.assertEqual((f.app/'sw.js').read_bytes(),f.after['sw.js'])
        self.assertEqual(identity(f.app/'member/push-settings.js'),foreign[0])
        for path in f.m.PATHS[2:]:self.assertEqual((f.app/path).read_bytes(),f.before[path])
        f.preserved()
    def test_other_variant_unfinished_journal_blocks_apply_and_noop(self):
        f=self.fixture();code,text=f.apply();self.assertEqual(code,0,text)
        value=f.m.load(f.session());value['release']='kcmc-follow-up-20261018-livecalendar'
        value['phase']='manual_review';value['uncertain']=['index.php']
        row=f.w.VARIANTS['livecalendar']['index']
        for kind,source in (('original','before'),('candidate','after'),('installed','after')):
            record=value['files']['index.php'][kind]
            if record is not None:record['sha256']=row[source+'_sha256'];record['bytes']=row[source+'_bytes']
        other=f.w.backup_root('livecalendar');other.mkdir(mode=0o700)
        session=other/f.session().name;session.mkdir(mode=0o700)
        (session/'journal.json').write_text(json.dumps(value));(session/'journal.json').chmod(0o600)
        code,text=f.apply();self.assertEqual(code,1,text);self.assertNotIn('CHECK ALREADY_REPAIRED',text)
        for path in f.m.PATHS:f.write(path,f.before[path])
        count=len(list(f.m.BACKUPS.glob('repair-*')))
        code,text=f.apply();self.assertEqual(code,1,text);self.assertEqual(len(list(f.m.BACKUPS.glob('repair-*'))),count)
        f.preserved()


class Provenance(unittest.TestCase):
    def test_exact_delta_readonly_guards_and_reproducible_installer(self):
        raw, extension, source, runtime, guards, variants = derive.verify_inputs(allow_unapproved=CANDIDATE)
        self.assertEqual(sha(raw), derive.FROZEN_SHA256); self.assertEqual(sha(extension), derive.EXTENSION_SHA256)
        if GIT_ROOT is not None:
            prefix = 'KCMC-Connect-Phase6-Recreated/'
            changed = subprocess.check_output(['git', 'diff', '--name-only', derive.BASE_COMMIT, derive.SOURCE_COMMIT, '--', prefix], cwd=str(GIT_ROOT)).decode().splitlines()
            self.assertEqual(changed, sorted(prefix + path for path in derive.PATHS))
            for path in derive.PATHS:
                for kind, ref in (('before', derive.BASE_COMMIT), ('after', derive.SOURCE_COMMIT)):
                    content = subprocess.check_output(['git', 'show', ref + ':' + prefix + path], cwd=str(GIT_ROOT))
                    self.assertEqual(content, (HERE / 'evidence' / kind / path).read_bytes())
                    self.assertEqual(subprocess.check_output(['git', 'ls-tree', ref, '--', prefix + path], cwd=str(GIT_ROOT)).split()[0], b'100644')
            for path, row in guards.items():
                for ref in (derive.BASE_COMMIT, derive.SOURCE_COMMIT):
                    content = subprocess.check_output(['git', 'show', ref + ':' + prefix + path], cwd=str(GIT_ROOT))
                    self.assertEqual((sha(content), len(content)), (row['sha256'], row['bytes']))
            for name,variant in variants.items():
                for path,row in variant['public_prerequisites'].items():
                    if name == 'livecalendar' and path == 'public-presentation.css':
                        historical_path = 'tools/kcmc-app-theme-oct15/evidence/public/livecalendar/' + path
                        content = subprocess.check_output(['git', 'show', derive.BASE_COMMIT + ':' + historical_path], cwd=str(GIT_ROOT))
                        manifest = subprocess.check_output(['git', 'show', derive.BASE_COMMIT + ':' + derive.THEME_PUBLIC_MANIFEST], cwd=str(GIT_ROOT))
                        self.assertEqual(sha(manifest), derive.THEME_PUBLIC_MANIFEST_SHA256)
                        self.assertEqual(json.loads(manifest.decode('utf-8'))['livecalendar']['public_prerequisites'][path], row)
                        self.assertEqual(content, (HERE / 'evidence/public/livecalendar' / path).read_bytes())
                        self.assertEqual((sha(content), len(content)), (row['sha256'], row['bytes']))
                    else:
                        for ref in (derive.BASE_COMMIT, derive.SOURCE_COMMIT):
                            content = subprocess.check_output(['git', 'show', ref + ':' + prefix + path], cwd=str(GIT_ROOT))
                            self.assertEqual((sha(content),len(content)),(row['sha256'],row['bytes']))
            historical_index = subprocess.check_output(['git', 'show', derive.BASE_COMMIT + ':tools/kcmc-app-theme-oct15/evidence/public/livecalendar/index-after.php'], cwd=str(GIT_ROOT))
            self.assertEqual(historical_index, (HERE / 'evidence/public/livecalendar/index-before.php').read_bytes())
        with tempfile.TemporaryDirectory(prefix='kcmc-follow-up-reproduce-') as directory:
            copied = Path(directory) / 'package'; shutil.copytree(str(HERE), str(copied))
            command = [sys.executable, '-B', '-c', 'import derive_installer as d; d.build(candidate=True)'] if CANDIDATE else [sys.executable, '-B', 'derive_installer.py']
            subprocess.check_call(command, cwd=str(copied))
            for name in ('installer.py', 'provenance.json'):
                self.assertEqual((HERE / (PREFIX + name)).read_bytes(), (copied / (PREFIX + name)).read_bytes())
    def test_repinning_manifest_cannot_cross_historical_css_with_main(self):
        with tempfile.TemporaryDirectory(prefix='kcmc-follow-up-provenance-') as directory:
            copied = Path(directory) / 'package'; shutil.copytree(str(HERE), str(copied))
            checked = loaded(copied / 'derive_installer.py', 'independent_bundle_pins')
            checked.verify_inputs(allow_unapproved=CANDIDATE)
            canonical = (copied / 'evidence/public/main/public-presentation.css').read_bytes()
            (copied / 'evidence/public/livecalendar/public-presentation.css').write_bytes(canonical)
            path = copied / 'public-variants-reviewed.json'; manifest = json.loads(path.read_text())
            manifest['livecalendar']['public_prerequisites']['public-presentation.css'] = manifest['main']['public_prerequisites']['public-presentation.css']
            path.write_text(json.dumps(manifest, indent=2) + '\n')
            checked.PINS['public-variants-reviewed.json'] = sha(path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'Independent canonical/historical public bundle pins changed: livecalendar'):
                checked.verify_inputs(allow_unapproved=CANDIDATE)


if __name__ == '__main__': unittest.main()
