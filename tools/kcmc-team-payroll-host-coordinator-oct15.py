#!/usr/bin/env python3
"""Fixed two-release coordinator; code only, no network or application execution."""
from __future__ import print_function
import argparse
import contextlib
import hashlib
import os
from pathlib import Path
import stat
import sys
import types

CORE_SHA256 = 'dd83356bb84e29bc8e9f871820d268861cfd58df83d7707519e4171c9f79b711'
TEAM_SHA256 = 'a968690ed84b9e45c7975570be8d368da8a403008f3b82ccc0c2c935ac2c5f0f'
MAX_HELPER_BYTES = 4194304


class Refusal(RuntimeError): pass


def require(ok,message):
    if not ok: raise Refusal(message)


def helper_bytes(path,expected):
    require(isinstance(expected,str) and len(expected)==64,'Coordinator helpers have not been frozen; no action authorized')
    flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK
    fd=os.open(str(path),flags)
    try:
        first=os.fstat(fd)
        require(stat.S_ISREG(first.st_mode) and first.st_nlink==1 and first.st_uid==os.geteuid() and
                0<first.st_size<=MAX_HELPER_BYTES,'Downloaded helper metadata refused')
        chunks=[]; size=0
        while True:
            part=os.read(fd,65536)
            if not part: break
            chunks.append(part); size+=len(part); require(size<=MAX_HELPER_BYTES,'Downloaded helper is oversized')
        content=b''.join(chunks); last=os.fstat(fd); visible=os.stat(str(path),follow_symlinks=False)
        keys=('st_dev','st_ino','st_mode','st_uid','st_gid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        require(all(getattr(first,key)==getattr(last,key)==getattr(visible,key) for key in keys) and len(content)==first.st_size,
                'Downloaded helper changed during verification')
        require(hashlib.sha256(content).hexdigest()==expected,'Downloaded helper checksum refused')
        return content
    finally: os.close(fd)


def load_helpers(core_path,team_path):
    # Verify BOTH complete byte images before compiling/executing either helper.
    verified=[helper_bytes(core_path,CORE_SHA256),helper_bytes(team_path,TEAM_SHA256)]
    result=[]
    for name,content in zip(('verified_core_v2','verified_team_payroll'),verified):
        module=types.ModuleType(name); module.__file__='<'+name+'>'
        exec(compile(content,module.__file__,'exec'),module.__dict__); result.append(module)
    return result


def verify_projection(team,records):
    for path,(info,parent) in records.items(): team.verify_parent(path,parent); team.verify_lease(path,info)


def projected_before(core,engines,team_wrapper,team):
    core_paths=engines['owner'].PATHS+engines[core.VARIANTS[0]].PATHS
    require(len(core_paths)==21 and len(set(core_paths))==21,'Fixed core inventory differs')
    after={}
    for key in ('owner',core.VARIANTS[0]):
        for path,row in engines[key].FILES.items(): after[path]=(row['after_sha256'],row['after_bytes'])
    overlap=set(core_paths)&set(team.PATHS)
    require(len(team.PATHS)==23 and len(overlap)==6 and len(team_wrapper.PREREQUISITES)==15 and
            set(core_paths)==overlap|set(team_wrapper.PREREQUISITES),'Fixed release composition differs')
    for path in overlap:
        row=team.FILES[path]
        require((row['before_sha256'],row['before_bytes'])==after[path],'Core target and next preimage differ: '+path)
    for path,row in team_wrapper.PREREQUISITES.items():
        require((row['sha256'],row['bytes'])==after[path],'Read-only next prerequisite differs: '+path)
    records={}
    for path in team.PATHS:
        if path in overlap: continue  # Already checked by exact whole core preflight.
        unused,info,parent=team.optional_live(path); row=team.FILES[path]
        require((info is None and row['before_sha256'] is None) or
                (info is not None and info['sha256']==row['before_sha256'] and info['bytes']==row['before_bytes']),
                'Unknown or mixed next code bundle: '+path+'; no new repair authorized')
        records[path]=(info,parent)
    verify_projection(team,records); return records


@contextlib.contextmanager
def projection_guard(core,team,records):
    factory=core.load_engines
    def guarded_factory():
        modules=factory()
        for module in modules.values():
            frozen=module.locked
            def make_guard(original):
                @contextlib.contextmanager
                def guarded_locked():
                    verify_projection(team,records)
                    with original() as check:
                        def checked():
                            verify_projection(team,records); check(); verify_projection(team,records)
                        checked(); yield checked; checked()
                    verify_projection(team,records)
                return guarded_locked
            module.locked=make_guard(frozen)
        return modules
    core.load_engines=guarded_factory
    try: yield
    finally: core.load_engines=factory


def run_action(helper,action):
    previous=sys.argv
    try:
        sys.argv=['verified-installer.py',action]
        require(helper.main()==0,'Verified '+action+' refused; see fixed helper diagnostics above')
    finally: sys.argv=previous


def core_journals_clear(core):
    # Old core code tuples are obsolete after phase2, but an unfinished core
    # transaction still requires review and may not be hidden by a final no-op.
    engines=core.load_engines()
    for key in core.ENGINE_IDS:
        module=engines[key]
        try: module.caller(); module.inventory(); module.unfinished()
        except module.Refusal as error: raise Refusal(str(error))


def coordinate(core,team_wrapper):
    team=team_wrapper.load_engine(); completed=[]
    try:
        # A whole final state needs no interpretation by an obsolete core tuple.
        final=False
        try:
            state,files,captured=team_wrapper.preflight(team)
            if state=='after':
                team_wrapper.verify_files(team,files); team_wrapper.verify_prerequisites(team,captured); final=True
        except (team_wrapper.Refusal,team.Refusal,OSError,ValueError): pass
        if final:
            core_journals_clear(core)
            print('FINAL_BUNDLE_ALREADY_PRESENT; verifying complete no-op without core downgrade.')
            for action in ('check','apply','check'):
                core_journals_clear(core)
                team_wrapper.verify_files(team,files); team_wrapper.verify_prerequisites(team,captured)
                run_action(team_wrapper,action)
                core_journals_clear(core)
                team_wrapper.verify_files(team,files); team_wrapper.verify_prerequisites(team,captured)
            core_journals_clear(core)
            team_wrapper.verify_files(team,files); team_wrapper.verify_prerequisites(team,captured)
            print('COMPLETE_ALREADY_REPAIRED; no replacement or new backup.'); return
        engines=core.load_engines()
        states,bootstrap=core.preflight(engines)
        records=projected_before(core,engines,team_wrapper,team)
        engines['owner'].verify_lease(core.PREREQUISITE['path'],bootstrap)
        with projection_guard(core,team,records):
            for action in ('check','apply','check'):
                verify_projection(team,records); run_action(core,action); verify_projection(team,records)
        completed.append('core21')
        print('PRIOR_VERIFIED_RELEASE core21; code remains installed if the next release later refuses.')
        state,unused,captured=team_wrapper.preflight(team)
        require(state=='before','Next complete before bundle required after core repair')
        for action in ('check','apply','check'): run_action(team_wrapper,action)
        completed.append('team_payroll23')
        print('COMPLETE_REPAIRED; both code releases verified. No config, cron, email, push, payment or private-record operation.')
    except BaseException:
        if completed: print('PRIOR_VERIFIED_RELEASES '+', '.join(completed)+'; no automatic downgrade was attempted.',file=sys.stderr)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('core_installer'); parser.add_argument('team_installer'); args=parser.parse_args(); helpers=[]
    try:
        helpers=load_helpers(Path(args.core_installer),Path(args.team_installer)); coordinate(*helpers); return 0
    except BaseException as error:
        known=(Refusal,)
        for helper in helpers:
            known+=(helper.Refusal,)
        message=str(error) if isinstance(error,known) else 'Unexpected coordinator failure; stopped safely'
        print('REFUSED '+message,file=sys.stderr)
        print('Both releases retain their own journals and private backups; inspect helper diagnostics before retrying.',file=sys.stderr)
        return 1


if __name__=='__main__': sys.exit(main())
