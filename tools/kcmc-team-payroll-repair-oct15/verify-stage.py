#!/usr/bin/env python3
"""Real PHP8.2 syntax plus temporary transactions; app code is never executed."""
from __future__ import print_function
import argparse
from pathlib import Path
import shutil
import subprocess
import test_installer as fixture


def prepared(php):
    f=fixture.Fixture(); f.w.php82_candidates=lambda:[php]; f.w.choose_php82_cli=f.real_choose; return f


def require_failure(f,*args):
    code,text=f.cli(*args); assert code==1,text
    assert 'REPAIRED ' not in text and 'ROLLED_BACK ' not in text,text
    return text


def basic(php):
    f=prepared(php)
    try:
        code,text=f.cli('check'); assert code==0 and 'CHECK READY' in text,text
        code,text=f.cli('apply'); assert code==0 and 'REPAIRED lib/bootstrap.php' in text,text
        assert f.m.inspect()[0]=='after'
        ids={path:fixture.identity(f.app/path) for path in f.m.PATHS}
        code,text=f.cli('apply'); assert code==0 and 'ALREADY_REPAIRED; no replacement' in text,text
        for path,prior in ids.items(): assert fixture.identity(f.app/path)==prior,path
        code,text=f.cli('rollback','--session',f.session().name); assert code==0,text
        f.assert_before(); f.preserved()
        print('REAL_PHP_82 exact23targets/nine absent files/apply/no-op/bootstrap mode/exact reverse rollback PASS')
    finally: f.close()


def uncertain_link(php):
    f=prepared(php)
    try:
        link=f.m.no_clobber_link
        def fail(*args,**kwargs): link(*args,**kwargs); raise OSError('Synthetic ambiguous provider link')
        f.m.no_clobber_link=fail; require_failure(f,'apply'); value=f.journal()
        path=next(path for path in f.m.PATHS if f.before[path] is None)
        assert value['phase']=='manual_review' and path in value['uncertain']
        assert value['files'][path]['installed'] is None and (f.app/path).stat().st_nlink==2
        f.m.verify_lease('lib/bootstrap.php',value['files']['lib/bootstrap.php']['installed']); f.preserved()
        print('REAL_PHP_82 new provider link uncertainty/two names/retained bootstrap/no candidate deletion PASS')
    finally: f.close()


def uncertain_consumer(php):
    f=prepared(php)
    try:
        replace=f.m.replace; index=f.m.PATHS.index('member/index.php')
        def fail(source,target,**kwargs):
            result=replace(source,target,**kwargs)
            if source=='stage-'+str(index)+'.code': raise OSError('Synthetic ambiguous account consumer')
            return result
        f.m.replace=fail; require_failure(f,'apply'); value=f.journal()
        assert value['phase']=='manual_review' and 'member/index.php' in value['uncertain']
        for path in ('lib/bootstrap.php','lib/payroll.php','lib/team-workspace.php','member/work.php'):
            assert value['files'][path]['installed'] is not None,path
            f.m.verify_lease(path,value['files'][path]['installed'])
        f.preserved(); print('REAL_PHP_82 uncertain account consumer/changed bootstrap and new providers retained PASS')
    finally: f.close()


def late_prerequisite(php):
    f=prepared(php)
    try:
        journal=f.m.journal; path=next(iter(f.w.PREREQUISITES))
        def fail(session,value):
            result=journal(session,value)
            if value['phase']=='applied': f.foreign(path)
            return result
        f.m.journal=fail; require_failure(f,'apply'); value=f.journal()
        assert value['phase']=='applied'
        for target in f.m.PATHS: f.m.verify_lease(target,value['files'][target]['installed'])
        f.preserved(path); print('REAL_PHP_82 late core prerequisite inode drift/no success/applied journal retained PASS')
    finally: f.close()


def late_bootstrap(php):
    f=prepared(php)
    try:
        journal=f.m.journal
        def fail(session,value):
            result=journal(session,value)
            if value['phase']=='applied': f.foreign('lib/bootstrap.php')
            return result
        f.m.journal=fail; text=require_failure(f,'apply')
        assert 'Code lease changed: lib/bootstrap.php' in text and f.journal()['phase']=='applied',text
        f.preserved(); print('REAL_PHP_82 late bootstrap same-bytes replacement/final installed-lease verification PASS')
    finally: f.close()


def rollback_prerequisite(php):
    f=prepared(php)
    try:
        code,text=f.cli('apply'); assert code==0,text
        unlink=f.m.unlink_name; first=[True]; path=next(iter(f.w.PREREQUISITES))
        def fail(name,**kwargs):
            result=unlink(name,**kwargs)
            if first[0]: first[0]=False; f.foreign(path)
            return result
        f.m.unlink_name=fail; require_failure(f,'rollback','--session',f.session().name)
        assert f.journal()['phase']=='manual_review'
        f.preserved(path); print('REAL_PHP_82 core prerequisite drift during rollback/uncertain deletion/manual review PASS')
    finally: f.close()


def reappearing_consumer(php,path):
    f=prepared(php)
    try:
        code,text=f.cli('apply'); assert code==0,text
        journal=f.m.journal; injected=[False]; foreign=[None]
        def changed(session,value):
            result=journal(session,value)
            if value['phase']=='rolling_back' and value['files'][path]['installed'] is None and value['intent'] is None and not injected[0]:
                injected[0]=True; foreign[0]=f.foreign(path,(fixture.HERE/'evidence/after'/path).read_bytes())
            return result
        f.m.journal=changed; require_failure(f,'rollback','--session',f.session().name)
        assert injected[0] and fixture.identity(f.app/path)==foreign[0]
        value=f.journal(); assert value['phase']=='manual_review' and path in value['uncertain']
        for provider in ('lib/bootstrap.php','lib/team-workspace.php','api/team-workspace.php'):
            assert value['files'][provider]['installed'] is not None,provider
            f.m.verify_lease(provider,value['files'][provider]['installed'])
        f.preserved(); print('REAL_PHP_82 completed consumer recreation/'+path+'/foreign inode/providers/manual_review PASS')
    finally: f.close()


def future_consumer(php):
    f=prepared(php)
    try:
        journal=f.m.journal; injected=[False]; foreign=[None]; path='member/index.php'
        def changed(session,value):
            result=journal(session,value)
            if value['phase']=='applying' and value['files']['lib/payroll.php']['installed'] is not None and value['files'][path]['installed'] is None and value['intent'] is None and not injected[0]:
                injected[0]=True; foreign[0]=f.foreign(path,(fixture.HERE/'evidence/after'/path).read_bytes())
            return result
        f.m.journal=changed; require_failure(f,'apply'); value=f.journal()
        assert injected[0] and fixture.identity(f.app/path)==foreign[0] and value['phase']=='manual_review'
        for provider in ('lib/bootstrap.php','lib/team-workspace.php','lib/payroll.php'):
            assert value['files'][provider]['installed'] is not None,provider
            f.m.verify_lease(provider,value['files'][provider]['installed'])
        f.preserved(); print('REAL_PHP_82 future uninstalled consumer replacement/foreign inode/providers/manual_review PASS')
    finally: f.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--php',default=shutil.which('php')); args=parser.parse_args()
    if not args.php: raise ValueError('Real PHP8.2 CLI required')
    php=str(Path(args.php).resolve()); original=subprocess.check_output
    def checked(argv,**kwargs):
        assert argv[0]==php and argv[1]=='-n' and argv[2] in ('-v','-l'),'Only real PHP version and staged syntax probes allowed'
        return original(argv,**kwargs)
    subprocess.check_output=checked
    try:
        basic(php); uncertain_link(php); uncertain_consumer(php); late_prerequisite(php); late_bootstrap(php); rollback_prerequisite(php)
        reappearing_consumer(php,'member/work.php'); reappearing_consumer(php,'member/index.php'); future_consumer(php)
    finally: subprocess.check_output=original
    return 0


if __name__=='__main__': raise SystemExit(main())
