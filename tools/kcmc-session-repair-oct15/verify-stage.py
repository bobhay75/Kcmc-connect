#!/usr/bin/env python3
"""Real PHP 8.2 lint/apply/no-op/rollback, temporary code and synthetic stores only."""
from __future__ import print_function
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
def identity(path):
    s=path.stat();return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def sha(data):return hashlib.sha256(data).hexdigest()

def prepare(wrapper,variant,root,php):
    app=root/'app';app.mkdir();engines=wrapper.load_engines()
    for name,m in engines.items():m.APP=app;m.BACKUPS=root/('private-'+name);m.UID=os.getuid();m.GID=os.getgid();m.PHP=php
    m=engines[variant];originals={}
    for path in m.PATHS:
        file=app/path;file.parent.mkdir(parents=True,exist_ok=True);originals[path]=(HERE/'evidence'/variant/path).read_bytes();file.write_bytes(originals[path]);file.chmod(0o644)
    (app/'member/password.php').chmod(0o664)
    sentinels={}
    for path in ('config.php','data/content.json','data/private/users.json','member/activate.php','member/reset-password.php','lib/timeclock.php','app.js'):
        file=app/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(b'synthetic owner bytes retained\n');file.chmod(0o600);sentinels[path]=(file.read_bytes(),identity(file))
    return app,engines,m,originals,sentinels

def preserve(app,sentinels):
    for path,(data,old) in sentinels.items():assert (app/path).read_bytes()==data and identity(app/path)==old

def probe_helper(app,php):
    # Execute only the retained helper in this temporary fixture. No bootstrap,
    # owner configuration or private account store is loaded by this probe.
    source=(app/'lib/session-lifetime.php').read_text()
    assert source.startswith('<?php\n')
    program=source[len('<?php\n'):]+'''
$user=['id'=>'synthetic-probe','password_hash'=>password_hash('Synthetic dependency probe 2031!',PASSWORD_DEFAULT)];
$session=[];
kcmc_session_bind_credentials($session,$user);
if(!kcmc_session_credentials_match($session,$user))exit(11);
kcmc_session_initialize_auth($session,2000000000);
if(kcmc_session_apply_lifetime($session,2000000001)['status']!=='active')exit(12);
echo 'RETAINED_HELPER_USABLE';
'''
    result=subprocess.check_output([php,'-n','-r',program],stderr=subprocess.STDOUT,timeout=30)
    assert result==b'RETAINED_HELPER_USABLE'

def uncertain_recovery(wrapper,variant,php,index,helper_change=None):
    with tempfile.TemporaryDirectory(prefix='kcmc-session-uncertain-php82-') as temporary:
        app,engines,m,originals,sentinels=prepare(wrapper,variant,Path(temporary),php);rename=m.replace
        def injected(source,target,**kwargs):
            result=rename(source,target,**kwargs)
            if source=='stage-'+str(index)+'.code':
                if helper_change=='corrupt':(app/'lib/session-lifetime.php').write_bytes(b'<?php // synthetic concurrent helper edit\n')
                elif helper_change=='missing':(app/'lib/session-lifetime.php').unlink()
                raise OSError('Synthetic post-rename uncertainty')
            return result
        m.replace=injected
        try:m.apply()
        except m.Refusal as error:assert 'manual review' in str(error)
        else:raise AssertionError('Uncertain commit cannot report successful recovery')
        session=next(m.BACKUPS.glob('repair-*'));value=m.load(session)
        assert value['phase']=='manual_review' and m.PATHS[index] in value['uncertain']
        assert value['files']['lib/session-lifetime.php']['installed'] is not None
        if helper_change=='missing':assert not (app/'lib/session-lifetime.php').exists()
        elif helper_change=='corrupt':assert (app/'lib/session-lifetime.php').read_bytes()==b'<?php // synthetic concurrent helper edit\n'
        else:
            m.verify_lease('lib/session-lifetime.php',value['files']['lib/session-lifetime.php']['installed'])
            assert sha((app/'lib/session-lifetime.php').read_bytes())==m.FILES['lib/session-lifetime.php']['after_sha256']
            probe_helper(app,php)
        preserve(app,sentinels)
        print('REAL_PHP_82 '+variant+' uncertain-stage-'+str(index)+' helper-'+str(helper_change or 'retained')+' manual-review/private preservation PASS')

def concurrent_rollback(wrapper,variant,php):
    with tempfile.TemporaryDirectory(prefix='kcmc-session-conflict-php82-') as temporary:
        app,engines,m,originals,sentinels=prepare(wrapper,variant,Path(temporary),php);session=m.apply();rename=m.replace
        changed=(app/'lib/bootstrap.php').read_bytes()+b'\n// Synthetic concurrent consumer change\n'
        def injected(source,target,**kwargs):
            result=rename(source,target,**kwargs)
            if target=='password.php':(app/'lib/bootstrap.php').write_bytes(changed)
            return result
        m.replace=injected
        try:m.rollback(session.name)
        except m.Refusal as error:assert 'manual review' in str(error)
        else:raise AssertionError('Concurrent rollback cannot report successful recovery')
        value=m.load(session);assert value['phase']=='manual_review'
        assert (app/'lib/bootstrap.php').read_bytes()==changed
        m.verify_lease('lib/session-lifetime.php',value['files']['lib/session-lifetime.php']['installed'])
        probe_helper(app,php);preserve(app,sentinels)
        print('REAL_PHP_82 '+variant+' consumer-edit-during-rollback retained-helper/manual-review/private preservation PASS')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--php',default=shutil.which('php'));args=parser.parse_args()
    if not args.php:raise ValueError('Test PHP 8.2 CLI is required')
    spec=importlib.util.spec_from_file_location('real_stage_session',str(HERE/'installer.py'))
    wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
    wrapper.php82_candidates=lambda:[str(Path(args.php).resolve())]
    selected,version=wrapper.choose_php82_cli();print('REAL_PHP_CLI_SELECTION '+selected+' PHP '+version+' PASS')
    for variant in wrapper.VARIANTS:
        with tempfile.TemporaryDirectory(prefix='kcmc-session-php82-') as temporary:
            app,engines,m,originals,sentinels=prepare(wrapper,variant,Path(temporary),selected)
            found,state,unused=wrapper.select(engines);assert (found,state)==(variant,'before')
            session=m.apply();assert session is not None
            for path in m.PATHS:assert sha((app/path).read_bytes())==m.FILES[path]['after_sha256']
            installed={p:identity(app/p) for p in m.PATHS};assert m.apply() is None
            for path,old in installed.items():assert identity(app/path)==old
            m.rollback(session.name)
            for path,data in originals.items():assert (app/path).read_bytes()==data
            assert (app/'member/password.php').stat().st_mode & 0o777==0o664
            preserve(app,sentinels)
            print('REAL_PHP_82 '+variant+' four-file stage/apply/no-op/rollback/private preservation PASS')
        uncertain_recovery(wrapper,variant,selected,1)
        uncertain_recovery(wrapper,variant,selected,3)
        uncertain_recovery(wrapper,variant,selected,1,'corrupt')
        uncertain_recovery(wrapper,variant,selected,1,'missing')
        concurrent_rollback(wrapper,variant,selected)
    return 0
if __name__=='__main__':raise SystemExit(main())
