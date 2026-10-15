#!/usr/bin/env python3
"""Two exact fixed payload releases in temporary fixtures; no host or app runs."""
from __future__ import print_function
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
CORE=HERE/'kcmc-workflows-repair-v2-oct15'
TEAM=HERE/'kcmc-team-payroll-repair-oct15'
CANDIDATE='--candidate' in sys.argv
sys.path.insert(0,str(TEAM))
import test_installer as phase


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path)); value=importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


def sha(content):return hashlib.sha256(content).hexdigest()


class Fixture:
    def __init__(self,core_before=False):
        self.phase=phase.Fixture(); self.c=module(HERE/'kcmc-team-payroll-host-coordinator-oct15.py','isolated_fixed_coordinator')
        self.core=module(CORE/'installer.py','isolated_core_v2_wrapper'); factory=self.core.load_engines
        def engines():
            values=factory()
            for key,value in values.items():
                value.APP=self.phase.app; value.BACKUPS=self.phase.root/('core-private-'+key); value.UID=os.getuid(); value.GID=os.getgid()
            return values
        self.core.load_engines=engines; self.engines=engines(); self.core.choose_php82_cli=lambda:('/synthetic/php82','8.2.34')
        if core_before:
            for path,row in self.engines['owner'].FILES.items(): (self.phase.app/path).write_bytes((CORE/'evidence/owner_before'/path).read_bytes()); (self.phase.app/path).chmod(0o644)
            for path,row in self.engines['pre_a7'].FILES.items():
                target=self.phase.app/path
                if row['before_sha256'] is None:
                    if target.exists():target.unlink()
                else:target.write_bytes((CORE/'evidence/pre_a7'/path).read_bytes()); target.chmod(0o644)
        self.c.load_helpers=lambda unused_core,unused_team:[self.core,self.phase.w]
    def close(self):self.phase.close()
    def cli(self):
        output=io.StringIO()
        with mock.patch.object(sys,'argv',['coordinator.py','core.py','team.py']),contextlib.redirect_stdout(output),contextlib.redirect_stderr(output),mock.patch.object(subprocess,'check_output',side_effect=self.phase.php):code=self.c.main()
        return code,output.getvalue()
    def preserved_business(self):
        for path,content in self.phase.sentinels.items():
            assert (self.phase.app/path).read_bytes()==content and phase.identity(self.phase.app/path)==self.phase.ids[path],path
        assert phase.identity(self.phase.crontab)==self.phase.crontab_identity
    def no_backups(self):return not self.phase.m.BACKUPS.exists() and all(not value.BACKUPS.exists() for value in self.engines.values())


class CoordinatorTests(unittest.TestCase):
    def test_first_run_from_whole_core_before_to_both_complete(self):
        f=Fixture(core_before=True);self.addCleanup(f.close);code,text=f.cli()
        self.assertEqual(code,0,text);self.assertIn('COMPLETE_REPAIRED',text);self.assertIn('PRIOR_VERIFIED_RELEASE core21',text)
        self.assertEqual(f.phase.m.inspect()[0],'after');f.preserved_business()
    def test_retry_with_core_already_after_only_installs_next_bundle(self):
        f=Fixture();self.addCleanup(f.close);code,text=f.cli();self.assertEqual(code,0,text)
        self.assertFalse(any(value.BACKUPS.exists() for value in f.engines.values()));self.assertEqual(f.phase.m.inspect()[0],'after');f.preserved_business()
    def test_rerun_after_both_is_noop_and_skips_obsolete_core_interpretation(self):
        f=Fixture(core_before=True);self.addCleanup(f.close);self.assertEqual(f.cli()[0],0)
        before={path:phase.identity(f.phase.app/path) for path in f.phase.m.PATHS}
        sessions=sorted(str(path) for path in f.phase.root.rglob('repair-*'))
        code,text=f.cli();self.assertEqual(code,0,text);self.assertIn('FINAL_BUNDLE_ALREADY_PRESENT',text);self.assertIn('COMPLETE_ALREADY_REPAIRED',text)
        self.assertNotIn('GROUP owner',text)
        for path,value in before.items():self.assertEqual(phase.identity(f.phase.app/path),value,path)
        self.assertEqual(sorted(str(path) for path in f.phase.root.rglob('repair-*')),sessions);f.preserved_business()
    def test_final_noop_holds_initial_bundle_leases_between_helper_actions(self):
        f=Fixture();self.addCleanup(f.close);self.assertEqual(f.cli()[0],0);run=f.c.run_action;injected=[False]
        def changed(helper,action):
            result=run(helper,action)
            if not injected[0]:injected[0]=True;f.phase.foreign('lib/bootstrap.php')
            return result
        with mock.patch.object(f.c,'run_action',side_effect=changed):code,text=f.cli()
        self.assertEqual(code,1);self.assertTrue(injected[0]);self.assertNotIn('COMPLETE_ALREADY_REPAIRED',text);f.preserved_business()
    def test_final_noop_does_not_hide_unfinished_core_owner_or_workflow_journals(self):
        for key in ('owner','pre_a7'):
            f=Fixture(core_before=True);self.addCleanup(f.close);self.assertEqual(f.cli()[0],0)
            engine=f.engines[key];session=next(engine.BACKUPS.glob('repair-*'));value=engine.load(session)
            value['phase']='manual_review';engine.journal(session,value);prior=phase.identity(session/'journal.json')
            before={path:phase.identity(f.phase.app/path) for path in f.phase.m.PATHS}
            code,text=f.cli();self.assertEqual(code,1);self.assertNotIn('COMPLETE_ALREADY_REPAIRED',text);self.assertIn('Unfinished repair requires review',text)
            self.assertEqual(phase.identity(session/'journal.json'),prior)
            for path,identity in before.items():self.assertEqual(phase.identity(f.phase.app/path),identity,path)
            f.preserved_business()
    def test_unknown_noncore_next_target_blocks_even_core_repair_before_backup(self):
        f=Fixture(core_before=True);self.addCleanup(f.close);path='lib/operations-owner.php';f.phase.foreign(path,b'<?php // unknown future code retained\n')
        before={str(path.relative_to(f.phase.app)):phase.identity(path) for path in f.phase.app.rglob('*') if path.is_file()}
        code,text=f.cli();self.assertEqual(code,1);self.assertTrue(f.no_backups());self.assertNotIn('PRIOR_VERIFIED_RELEASE core21',text)
        for path,value in before.items():self.assertEqual(phase.identity(f.phase.app/path),value,path)
        f.preserved_business()
    def test_mixed_next_new_asset_blocks_core_before_backup(self):
        f=Fixture(core_before=True);self.addCleanup(f.close);path='member/workspace.js'
        (f.phase.app/path).write_bytes((TEAM/'evidence/after'/path).read_bytes());(f.phase.app/path).chmod(0o644)
        code,text=f.cli();self.assertEqual(code,1);self.assertTrue(f.no_backups());f.preserved_business()
    def test_mixed_core_owner_group_refuses_before_any_backup(self):
        f=Fixture(core_before=True);self.addCleanup(f.close);path='lib/password-lifecycle.php'
        (f.phase.app/path).write_bytes((CORE/'evidence/owner_after'/path).read_bytes())
        code,text=f.cli();self.assertEqual(code,1);self.assertTrue(f.no_backups());f.preserved_business()
    def test_core_success_is_explicit_and_preserved_if_next_stage_lint_refuses(self):
        f=Fixture(core_before=True);self.addCleanup(f.close)
        with mock.patch.object(f.phase.m,'lint',side_effect=f.phase.m.Refusal('Synthetic next-stage syntax refusal')):code,text=f.cli()
        self.assertEqual(code,1);self.assertIn('PRIOR_VERIFIED_RELEASES core21',text);self.assertNotIn('COMPLETE_REPAIRED',text)
        for key in ('owner','pre_a7'):
            for path,row in f.engines[key].FILES.items():self.assertEqual(sha((f.phase.app/path).read_bytes()),row['after_sha256'],path)
        f.phase.assert_before();f.preserved_business()
    def test_projected_noncore_inode_drift_inside_core_stage_refuses_before_replacement(self):
        f=Fixture(core_before=True);self.addCleanup(f.close);factory=f.core.load_engines;drift=[False]
        def engines():
            values=factory()
            for value in values.values():
                lint=value.lint
                def changed(session,original=lint):
                    original(session)
                    if not drift[0]:drift[0]=True;f.phase.foreign('lib/operations-owner.php')
                value.lint=changed
            return values
        f.core.load_engines=engines;code,text=f.cli();self.assertEqual(code,1);self.assertTrue(drift[0]);self.assertNotIn('GROUP owner REPAIRED',text)
        self.assertEqual((f.phase.app/'lib/password-lifecycle.php').read_bytes(),(CORE/'evidence/owner_before/lib/password-lifecycle.php').read_bytes());f.preserved_business()


class HelperIntegrityTests(unittest.TestCase):
    def test_fixed_pins_match_both_complete_real_installer_images(self):
        c=module(HERE/'kcmc-team-payroll-host-coordinator-oct15.py','isolated_fixed_image_pins')
        core,team=c.load_helpers(CORE/'installer.py',TEAM/'installer.py')
        self.assertTrue(callable(core.load_engines));self.assertTrue(callable(team.load_engine))
    def test_both_checksums_verified_before_either_helper_is_executed(self):
        c=module(HERE/'kcmc-team-payroll-host-coordinator-oct15.py','isolated_integrity_coordinator')
        with tempfile.TemporaryDirectory(prefix='kcmc-helper-integrity-') as directory:
            root=Path(directory); marker=root/'executed'; core=root/'core.py';team=root/'team.py'
            first=('from pathlib import Path\nPath('+repr(str(marker))+').write_text("unexpected")\n').encode()
            second=b'# complete second helper\n';core.write_bytes(first);team.write_bytes(second)
            c.CORE_SHA256=sha(first);c.TEAM_SHA256=sha(second);team.write_bytes(second+b'# tampered\n')
            with self.assertRaises(c.Refusal):c.load_helpers(core,team)
            self.assertFalse(marker.exists())
    def test_linked_or_symlinked_download_is_refused(self):
        c=module(HERE/'kcmc-team-payroll-host-coordinator-oct15.py','isolated_integrity_links')
        with tempfile.TemporaryDirectory(prefix='kcmc-helper-links-') as directory:
            root=Path(directory);target=root/'helper.py';target.write_bytes(b'# helper\n');other=root/'hardlink.py';os.link(str(target),str(other))
            with self.assertRaises(c.Refusal):c.helper_bytes(target,sha(target.read_bytes()))
            other.unlink();link=root/'symbolic.py';link.symlink_to(target)
            with self.assertRaises(OSError):c.helper_bytes(link,sha(target.read_bytes()))


if __name__=='__main__':unittest.main()
