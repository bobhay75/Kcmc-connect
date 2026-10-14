#!/usr/bin/env python3
"""Repair thirteen reported checkout modes only; no Git update or app deployment."""
from __future__ import print_function
import argparse
import contextlib
import fcntl
import hashlib
import os
from pathlib import Path
import signal
import stat
import sys
import types
import uuid

REPO = Path('/home/bobsome1/repositories/Kcmc-connect-live')
BASELINE = '4225fce8968747ad4f828a9a36087b04fd020484'
TARGET = '154b779a0ea3d27a11300bfe0454f8a7c4aca355'
UID, GID, TRACKED_COUNT = 2162, 2147, 255
PRIVATE_ROOT = Path('/home/bobsome1/kcmc-repository-metadata-repairs')
HELPER_SHA256 = '1ed8ce0980638f8ff1488a6fda785f6aa6a12c8db03bfe8e75cc13c81955e0a6'
APP = 'KCMC-Connect-Phase6-Recreated/'
PATHS = ('.cpanel.yml', '.github/workflows/security-contract.yml', '.gitignore', APP+'.htaccess',
         APP+'admin/backup.php', APP+'admin/login.php', APP+'admin/logout.php', APP+'admin/prayers.php',
         APP+'admin/setup.php', APP+'member/logout.php', APP+'member/prayer-team.php',
         APP+'member/submit-prayer.php', 'README.md')

class Refusal(RuntimeError):
    pass

def require(ok, message):
    if not ok:
        raise Refusal(message)

def load_helper():
    path = Path(__file__).with_name('align-repository.py')
    fd = os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_uid == os.getuid() and before.st_size == 14570, 'Frozen verifier file refused')
        raw = os.read(fd,14571)
        after, visible = os.fstat(fd), os.lstat(str(path))
        require(len(raw) == 14570 and stat.S_ISREG(visible.st_mode) and
                (before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns) ==
                (after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns) and
                (visible.st_dev,visible.st_ino) == (before.st_dev,before.st_ino), 'Frozen verifier changed during read')
    finally:
        os.close(fd)
    require(hashlib.sha256(raw).hexdigest() == HELPER_SHA256, 'Frozen verifier checksum mismatch')
    helper = types.ModuleType('frozen_metadata_verifier')
    exec(compile(raw, 'frozen-align-repository.py', 'exec'), helper.__dict__)
    helper.REPO = REPO
    return helper

def blob(fd, helper):
    before = os.fstat(fd)
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= helper.LIMIT,
            'File type/link/size lease refused')
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha1(b'blob '+str(before.st_size).encode()+b'\0')
    while True:
        data = os.read(fd, 65536)
        if not data:
            break
        digest.update(data)
    after = os.fstat(fd)
    require((before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
            (after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'File changed during hash check')
    return digest.hexdigest().encode()

def lease(record, helper, intent=False):
    path, fd, old = record['path'], record['fd'], record['state']
    require(helper.physical(path.parent) == record['parent'], 'Parent directory lease changed')
    visible, current = os.lstat(str(path)), os.fstat(fd)
    keys = ('st_dev','st_ino','st_nlink','st_uid','st_gid','st_size','st_mtime_ns')
    require(all(getattr(current,k) == getattr(old,k) for k in keys) and
            visible.st_dev == current.st_dev and visible.st_ino == current.st_ino and
            stat.S_ISREG(visible.st_mode), 'File identity/content metadata lease changed')
    if not intent:
        require(current.st_ctime_ns == old.st_ctime_ns and
                stat.S_IMODE(current.st_mode) == stat.S_IMODE(old.st_mode), 'File mode lease changed')
    require(current.st_uid == UID and current.st_gid == (GID if record['name'] in PATHS else old.st_gid) and
            blob(fd,helper) == record['oid'],
            'File ownership/content lease changed')
    return current

class ModeView(object):
    def __init__(self, raw):
        self.raw, self.st_mode = raw, (raw.st_mode & ~0o7777) | 0o644
    def __getattr__(self, name):
        return getattr(self.raw, name)

def prove(helper, commit, identity_config, leases, normalized=False):
    require(helper.standard_repo() == identity_config, 'Repository/configuration lease changed')
    for record in leases:
        lease(record,helper)
    original = helper.regular
    sanctioned = {record['path']:record for record in leases if record['name'] in PATHS}
    def mode_view(path):
        info = original(path)
        record = sanctioned.get(Path(path))
        if record and normalized:
            require(stat.S_IMODE(info.st_mode) == stat.S_IMODE(record['state'].st_mode) and
                    (info.st_dev,info.st_ino) == (record['state'].st_dev,record['state'].st_ino) and
                    stat.S_IMODE(info.st_mode) in (0o644,0o664), 'Sanctioned mode lease changed')
            return ModeView(info)
        return info
    helper.regular = mode_view
    try:
        helper.clean(commit)
    finally:
        helper.regular = original
    require(helper.standard_repo() == identity_config and
            helper.git(['rev-parse','--verify','HEAD']).strip().decode('ascii') == commit,
            'Repository/configuration/HEAD changed during proof')
    for record in leases:
        lease(record,helper)

def change_mode(fd, mode):
    os.fchmod(fd,mode)

def git_lease(helper, commit, identity_config, records):
    require(helper.standard_repo() == identity_config and
            helper.git(['rev-parse','--verify','HEAD']).strip().decode('ascii') == commit,
            'Global Git checkout lease changed')
    for record in records:
        if record['name'] not in PATHS:
            lease(record,helper)

def journal(session, records, phase):
    import json
    value = {'version':1,'baseline_head':BASELINE,'phase':phase,'files':[
        {'path':r['name'],'dev':r['state'].st_dev,'ino':r['state'].st_ino,
         'mode':r['before'],'uid':r['state'].st_uid,'gid':r['state'].st_gid,
         'blob_sha':r['oid'].decode('ascii')} for r in records if r['name'] in PATHS],
         'git_controls':[{'path':r['name'],'dev':r['state'].st_dev,'ino':r['state'].st_ino,
          'mode':r['before'],'uid':r['state'].st_uid,'gid':r['state'].st_gid,
          'blob_sha':r['oid'].decode('ascii')} for r in records if r['name'] not in PATHS]}
    temp = session / ('journal-'+uuid.uuid4().hex+'.tmp')
    fd = os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        data = (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
        with os.fdopen(fd,'wb',closefd=False) as out:
            out.write(data);out.flush();os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(temp),str(session/'journal.json'))

@contextlib.contextmanager
def transaction(helper):
    require('/public_html/' not in str(PRIVATE_ROOT)+'/' and
            not str(PRIVATE_ROOT).startswith(str(REPO)+'/'), 'Unsafe metadata journal location')
    helper.physical(PRIVATE_ROOT.parent)
    try:
        os.mkdir(str(PRIVATE_ROOT),0o700)
    except FileExistsError:
        pass
    info = os.lstat(str(PRIVATE_ROOT))
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == UID and stat.S_IMODE(info.st_mode) == 0o700,
            'Unsafe private metadata journal directory')
    fd = os.open(str(PRIVATE_ROOT/'.repair.lock'),os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == UID and
                stat.S_IMODE(info.st_mode) == 0o600,'Unsafe metadata repair lock')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        session = PRIVATE_ROOT/('repair-'+uuid.uuid4().hex)
        os.mkdir(str(session),0o700)
        yield session
    finally:
        os.close(fd)

def run(action='repair', helper=None):
    require(action in ('check','repair'), 'Unknown metadata action')
    require((os.getuid(),os.getgid()) == (UID,GID), 'Expected hosting caller UID/GID required')
    helper = load_helper() if helper is None else helper
    helper.REPO = REPO
    identity_config = helper.standard_repo()
    commit = helper.git(['rev-parse','--verify','HEAD']).strip().decode('ascii')
    require(commit in (BASELINE,TARGET), 'Unexpected checkout HEAD; no metadata writes')
    if commit == TARGET:
        prove(helper,TARGET,identity_config,[])
        return {'status':'already_target','changed':0}
    tree = helper.source_tree(BASELINE)
    require(len(tree) == TRACKED_COUNT and all(tree.get(p,(None,None))[0] == b'100644' for p in PATHS),
            'Expected canonical tracked count/path modes required')
    records, changed, intent = [], [], None
    try:
        for name in PATHS + ('.git/config','.git/HEAD','.git/index'):
            path = REPO/name
            parent = helper.physical(path.parent)
            fd = os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            record = {'fd':fd}
            records.append(record)
            state = os.fstat(fd)
            record.update({'name':name,'path':path,'parent':parent,'state':state,
                           'before':stat.S_IMODE(state.st_mode),'oid':blob(fd,helper)})
            lease(record,helper)
            if name in PATHS:
                require(record['oid'] == tree[name][1], 'Approved metadata target content mismatch')
        modes = set(r['before'] for r in records if r['name'] in PATHS)
        require(modes in ({0o664},{0o644}), 'Reported thirteen-file mode state is not coherent')
        normalized = modes == {0o664}
        prove(helper,BASELINE,identity_config,records,normalized)
        if not normalized or action == 'check':
            return {'status':'eligible' if normalized else 'already_repaired','changed':0}
        with transaction(helper) as session:
            journal(session,records,'prepared')
            previous = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(Refusal('Metadata repair interrupted')))
            try:
                for record in records:
                    if record['name'] not in PATHS:
                        continue
                    prove(helper,BASELINE,identity_config,records,True)
                    intent = record
                    journal(session,records,'intent:'+record['name'])
                    lease(record,helper)
                    try:
                        change_mode(record['fd'],0o644)
                    finally:
                        current = lease(record,helper,intent=True)
                        require(stat.S_IMODE(current.st_mode) in (0o644,0o664),'Unexpected intent mode')
                        record['state'] = current
                        if stat.S_IMODE(current.st_mode) == 0o644:
                            changed.append(record)
                    intent = None
                    os.fsync(record['fd'])
                    journal(session,records,'changing')
                prove(helper,BASELINE,identity_config,records,False)
                journal(session,records,'complete')
            except BaseException:
                failed = []
                if intent is not None and intent not in changed:
                    try:
                        current = lease(intent,helper,intent=True)
                        current_mode = stat.S_IMODE(current.st_mode)
                        require(current_mode in (intent['before'],0o644),'Unresolved intent mode')
                        if current_mode == 0o644:
                            intent['state'] = current
                            changed.append(intent)
                    except BaseException:
                        failed.append(intent['name'])
                try:
                    git_lease(helper,BASELINE,identity_config,records)
                    recoverable = list(reversed(changed))
                except BaseException:
                    failed += [record['name'] for record in changed] or ['global_git_lease']
                    recoverable = []
                for record in recoverable:
                    try:
                        git_lease(helper,BASELINE,identity_config,records)
                        lease(record,helper)
                        change_mode(record['fd'],record['before'])
                        record['state'] = os.fstat(record['fd'])
                        os.fsync(record['fd']);lease(record,helper)
                    except BaseException:
                        failed.append(record['name'])
                try:
                    prove(helper,BASELINE,identity_config,records,True)
                    require(all(stat.S_IMODE(r['state'].st_mode) == r['before'] for r in records
                                if r['name'] in PATHS),'Final prior-mode restoration is incomplete')
                except BaseException:
                    failed.append('final_checkout_lease')
                try:
                    journal(session,records,'review_required:'+','.join(sorted(set(failed))) if failed else 'rolled_back')
                except BaseException:
                    pass
                raise Refusal('Metadata repair failed; '+('leased prior modes restored' if not failed else
                              'manual review required for changed leases')+'; private journal: '+str(session))
            finally:
                signal.signal(signal.SIGTERM,previous)
            return {'status':'repaired','changed':len(changed),'session':str(session)}
    finally:
        for record in records:
            os.close(record['fd'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['check','repair'],nargs='?',default='check')
    try:
        result = run(parser.parse_args().action)
        print('Metadata result: '+result['status']+'; changed modes: '+str(result['changed'])+'. No file contents, ownership, Git refs or live app deployment changed.')
        if result.get('session'):
            print('Private metadata journal: '+result['session'])
        return 0
    except BaseException as error:
        if isinstance(error,(KeyboardInterrupt,SystemExit)):
            raise
        print('REFUSED: '+(str(error) if isinstance(error,Refusal) else
              'Repository verification or operating-system access refused; raw details withheld.'),file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
