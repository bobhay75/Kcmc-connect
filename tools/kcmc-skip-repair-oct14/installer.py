#!/usr/bin/env python3
"""One pinned KCMC app.js repair; Python 3.6+, offline, no application execution."""
from __future__ import print_function

import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import uuid

APP = Path('/home/bobsome1/public_html/kcmc-connect')
BACKUPS = Path('/home/bobsome1/kcmc-skip-repair-backups')
UID, GID = 2162, 2147
RELEASE = 'kcmc-skip-repair-20261014'
PATHS = ('app.js',)
MAX_BYTES = 131072
# GENERATED_REVIEWED_REPLACEMENTS
FILES = json.loads('{"app.js":{"before_sha256":"2a3e82a72ad689cec36984541c8c5a4c1b740fa2de7e38b2e1cd7b5aee373348","after_sha256":"d2d349264224e119482187e0fdbfcee6cd6ed29c16b1874c65c88cf29dd93963","replacements":[["  \'use strict\';\\n","  \'use strict\';\\n  document.querySelector(\'.skip-link[href=\\"#mainContent\\"]\')?.addEventListener(\'click\', event => {\\n    const main = document.getElementById(\'mainContent\');\\n    if (!main) return;\\n    event.preventDefault();\\n    main.setAttribute(\'tabindex\', \'-1\');\\n    main.focus({preventScroll:true});\\n    main.style.scrollMarginTop = `${document.querySelector(\'.topbar\')?.getBoundingClientRect().height || 0}px`;\\n    main.scrollIntoView({block:\'start\',behavior:\'instant\'});\\n  });\\n"]],"before_bytes":18999,"after_bytes":19463}}')
LEASE_KEYS = ('sha256', 'bytes', 'dev', 'ino', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'gid', 'nlink')


class Refusal(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise Refusal(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def caller():
    require((os.getuid(), os.geteuid(), os.getgid(), os.getegid()) == (UID, UID, GID, GID),
            'Run as the hosting account UID 2162 / GID 2147; no change made')


def inventory():
    require(tuple(FILES) == PATHS, 'Repair inventory is not exactly the reviewed app.js file')
    require(APP.is_absolute() and BACKUPS.is_absolute() and APP != BACKUPS and
            'public_html' not in BACKUPS.parts, 'Invalid fixed repair roots')
    for path in PATHS:
        item = FILES[path]
        require(set(item) == set(['before_sha256', 'after_sha256', 'before_bytes', 'after_bytes', 'replacements']),
                'Invalid embedded repair inventory')
        require(all(re.match(r'\A[0-9a-f]{64}\Z', item[key]) for key in ('before_sha256', 'after_sha256')) and
                all(isinstance(item[key], int) and 0 < item[key] <= MAX_BYTES for key in ('before_bytes', 'after_bytes')),
                'Invalid embedded code hashes')
        require(isinstance(item['replacements'], list) and item['replacements'] and
                all(isinstance(pair, list) and len(pair) == 2 and all(isinstance(v, str) for v in pair) and pair[0]
                    for pair in item['replacements']), 'Invalid embedded replacements')


class Parent(object):
    """Retain every no-follow ancestor descriptor until its operation finishes."""
    def __init__(self, path):
        self.path, self.opened = Path(path), []

    def __enter__(self):
        require(self.path.is_absolute(), 'Absolute parent required')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open('/', flags)
        self.opened.append((fd, Path('/')))
        current = Path('/')
        try:
            for part in self.path.parts[1:]:
                current = current / part
                fd = os.open(part, flags, dir_fd=fd)
                self.opened.append((fd, current))
            self.fd = fd
            self.check()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def check(self):
        for fd, path in self.opened:
            visible, held = os.lstat(str(path)), os.fstat(fd)
            require(stat.S_ISDIR(visible.st_mode) and (visible.st_dev, visible.st_ino) == (held.st_dev, held.st_ino),
                    'A parent directory changed or became linked')
            if path == APP or APP in path.parents:
                require((visible.st_uid, visible.st_gid) == (UID, GID) and
                        not (stat.S_IMODE(visible.st_mode) & 0o7002), 'Unsafe application directory owner/mode')
            if path == BACKUPS or BACKUPS in path.parents:
                require((visible.st_uid, visible.st_gid, stat.S_IMODE(visible.st_mode)) == (UID, GID, 0o700),
                        'Unsafe private directory owner/mode')

    def __exit__(self, *args):
        for fd, _ in reversed(self.opened):
            os.close(fd)
        self.opened = []


def metadata(info, data):
    return {'sha256': digest(data), 'bytes': len(data), 'dev': info.st_dev, 'ino': info.st_ino,
            'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns, 'mode': stat.S_IMODE(info.st_mode),
            'uid': info.st_uid, 'gid': info.st_gid, 'nlink': info.st_nlink}


def same(actual, expected):
    return all(actual[key] == expected[key] for key in LEASE_KEYS)


def read_at(parent, name):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, 'O_NOATIME', 0)
    fd = os.open(name, flags, dir_fd=parent.fd)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == UID and before.st_gid == GID,
                'Nonregular, linked or foreign-owned file refused')
        require(0 < before.st_size <= MAX_BYTES, 'Unexpected code/metadata size')
        chunks, size = [], 0
        while True:
            part = os.read(fd, 65536)
            if not part:
                break
            chunks.append(part)
            size += len(part)
            require(size <= MAX_BYTES, 'Oversized file refused')
        data = b''.join(chunks)
        after = os.fstat(fd)
        first, last = metadata(before, data), metadata(after, data)
        require(same(first, last) and len(data) == before.st_size, 'File changed during read')
        visible = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        require(same(metadata(visible, data), last) and stat.S_ISREG(visible.st_mode), 'File replaced during read')
        parent.check()
        return data, last
    finally:
        os.close(fd)


def read(path):
    path = Path(path)
    with Parent(path.parent) as parent:
        return read_at(parent, path.name)


def live(path):
    data, info = read(APP / path)
    require(info['mode'] in (0o644, 0o664), 'Code mode must already be 0644 or 0664: ' + path)
    return data, info


def verify_lease(path, expected):
    _, actual = live(path)
    require(same(actual, expected), 'Code lease changed: ' + path)
    return actual


def inspect():
    caller()
    inventory()
    found, kinds = {}, []
    for path in PATHS:
        data, info = live(path)
        item = FILES[path]
        matches = [kind for kind in ('before', 'after') if info['sha256'] == item[kind + '_sha256'] and
                   info['bytes'] == item[kind + '_bytes']]
        require(len(matches) == 1, 'Unknown code bytes: ' + path)
        kinds.append(matches[0])
        found[path] = (data, info)
    require(len(set(kinds)) == 1, 'Mixed before/after code bundle refused; no repair made')
    for path in PATHS:
        verify_lease(path, found[path][1])
    return kinds[0], found


def repair(path, data):
    item = FILES[path]
    require(digest(data) == item['before_sha256'] and len(data) == item['before_bytes'], 'Repair preimage changed')
    for old, new in item['replacements']:
        old, new = old.encode('utf-8'), new.encode('utf-8')
        require(data.count(old) == 1, 'Repair anchor is not unique: ' + path)
        data = data.replace(old, new, 1)
    require(digest(data) == item['after_sha256'] and len(data) == item['after_bytes'], 'Repair output hash mismatch')
    return data


def private_dir(path, create=False):
    path = Path(path)
    with Parent(path.parent) as parent:
        if create:
            try:
                os.mkdir(path.name, 0o700, dir_fd=parent.fd)
                os.fsync(parent.fd)
            except FileExistsError:
                pass
        info = os.stat(path.name, dir_fd=parent.fd, follow_symlinks=False)
        require(stat.S_ISDIR(info.st_mode) and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (UID, GID, 0o700),
                'Backup directory owner/group/mode refused')
        parent.check()


def write_private(path, data):
    path = Path(path)
    with Parent(path.parent) as parent:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent.fd)
        try:
            os.fchmod(fd, 0o600)
            require((os.fstat(fd).st_uid, os.fstat(fd).st_gid) == (UID, GID), 'Staging ownership refused')
            view = memoryview(data)
            while view:
                n = os.write(fd, view)
                require(n > 0, 'Private write failed')
                view = view[n:]
            os.fsync(fd)
            parent.check()
            visible = os.stat(path.name, dir_fd=parent.fd, follow_symlinks=False)
            held = os.fstat(fd)
            require((visible.st_dev, visible.st_ino, visible.st_nlink) == (held.st_dev, held.st_ino, 1),
                    'Private file path changed')
            os.fsync(parent.fd)
        finally:
            os.close(fd)


def replace(source, target, **kwargs):
    os.replace(source, target, **kwargs)


def journal(session, value):
    private_dir(session)
    path = Path(session) / 'journal.json'
    try:
        _, info = read(path)
        require(info['mode'] == 0o600, 'Unsafe journal mode')
    except FileNotFoundError:
        pass
    temporary = Path(session) / ('.journal-' + uuid.uuid4().hex)
    write_private(temporary, (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('ascii'))
    with Parent(session) as parent:
        parent.check()
        replace(temporary.name, path.name, src_dir_fd=parent.fd, dst_dir_fd=parent.fd)
        os.fsync(parent.fd)
        parent.check()


def session_name(name):
    require(isinstance(name, str) and re.match(r'\Arepair-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\Z', name),
            'Use the exact private repair session name')
    return BACKUPS / name


def load(session):
    require(Path(session).parent == BACKUPS, 'Session escaped fixed backup root')
    session_name(Path(session).name)
    private_dir(BACKUPS)
    private_dir(session)
    data, meta = read(Path(session) / 'journal.json')
    require(meta['mode'] == 0o600, 'Unsafe journal permissions')
    value = json.loads(data.decode('ascii'))
    require(isinstance(value, dict) and set(value) == set(['release', 'app', 'phase', 'intent', 'uncertain', 'files']) and
            value['release'] == RELEASE and value['app'] == str(APP) and isinstance(value['files'], dict) and
            set(value['files']) == set(PATHS) and
            value['phase'] in ('prepared', 'applying', 'applied', 'rolling_back', 'rolled_back', 'manual_review') and
            (value['intent'] is None or value['intent'] in PATHS) and isinstance(value['uncertain'], list) and
            all(isinstance(path, str) for path in value['uncertain']) and
            len(set(value['uncertain'])) == len(value['uncertain']) and
            all(path in PATHS for path in value['uncertain']), 'Journal scope/phase refused')
    for path in PATHS:
        record = value['files'][path]
        require(isinstance(record, dict) and set(record) == set(['original', 'candidate', 'installed']), 'Invalid journal file record')
        for kind, info in record.items():
            require(info is None and kind != 'original' or isinstance(info, dict) and set(info) == set(LEASE_KEYS) and
                    isinstance(info['sha256'], str) and re.match(r'\A[0-9a-f]{64}\Z', info['sha256']) and
                    all(type(info[key]) is int and info[key] >= 0 for key in LEASE_KEYS if key != 'sha256') and
                    info['mode'] in (0o644, 0o664) and info['uid'] == UID and info['gid'] == GID and info['nlink'] == 1,
                    'Invalid journal lease')
            if info is not None:
                source = 'before' if kind == 'original' else 'after'
                require(info['sha256'] == FILES[path][source + '_sha256'] and info['bytes'] == FILES[path][source + '_bytes'],
                        'Journal code source mismatch')
    return value


def unfinished(except_session=None):
    try:
        private_dir(BACKUPS)
    except FileNotFoundError:
        return
    with Parent(BACKUPS) as parent:
        names = os.listdir(parent.fd)
        parent.check()
    for name in names:
        if not name.startswith('repair-') or name == except_session:
            continue
        value = load(session_name(name))
        require(value['phase'] in ('applied', 'rolled_back'), 'Unfinished repair requires review: ' + name)


@contextlib.contextmanager
def locked():
    private_dir(BACKUPS, create=True)
    with Parent(BACKUPS) as parent:
        fd = os.open('.repair.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent.fd)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and (info.st_nlink, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (1, UID, GID, 0o600),
                    'Unsafe repair lock')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            visible = os.stat('.repair.lock', dir_fd=parent.fd, follow_symlinks=False)
            require((visible.st_dev, visible.st_ino) == (info.st_dev, info.st_ino), 'Repair lock path changed')
            def check_lock():
                parent.check()
                current = os.stat('.repair.lock', dir_fd=parent.fd, follow_symlinks=False)
                held = os.fstat(fd)
                require(stat.S_ISREG(current.st_mode) and
                        (current.st_dev, current.st_ino, current.st_nlink, current.st_uid, current.st_gid, stat.S_IMODE(current.st_mode)) ==
                        (info.st_dev, info.st_ino, 1, UID, GID, 0o600) and
                        (held.st_dev, held.st_ino, held.st_nlink) == (info.st_dev, info.st_ino, 1), 'Repair lock lease changed')
            check_lock()
            yield check_lock
            check_lock()
        finally:
            os.close(fd)


def lint(session):
    """Check pinned stage bytes only; Node --check is an off-host release gate."""
    for index, path in enumerate(PATHS):
        data, info = read(Path(session) / ('stage-' + str(index) + '.js'))
        item = FILES[path]
        require(info['mode'] == 0o600 and info['sha256'] == item['after_sha256'] and
                info['bytes'] == item['after_bytes'], 'Pinned JavaScript stage bytes changed')

def bundle_lease(value, check_lock):
    check_lock()
    for path in PATHS:
        record = value['files'][path]
        verify_lease(path, record['installed'] or record['original'])


def backup_device():
    with Parent(BACKUPS) as parent:
        return os.fstat(parent.fd).st_dev


def move_code(source, path, expected, staged_expected, check_lock):
    target = APP / path
    with Parent(source.parent) as src, Parent(target.parent) as dst:
        _, staged = read_at(src, source.name)
        require(same(staged, staged_expected), 'Stage lease changed')
        require(staged['dev'] == expected['dev'], 'Stage and code target must use the same filesystem')
        _, actual = read_at(dst, target.name)
        require(same(actual, expected), 'Target lease changed before replacement')
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, 'O_NOATIME', 0)
        source_fd = os.open(source.name, flags, dir_fd=src.fd)
        try:
            target_fd = os.open(target.name, flags, dir_fd=dst.fd)
            try:
                # Keep both file descriptors through rename. The final check catches
                # namespace/in-place changes; os.replace itself is not a kernel CAS.
                check_lock()
                src.check()
                dst.check()
                for parent, name, fd, lease in ((src, source.name, source_fd, staged_expected),
                                               (dst, target.name, target_fd, expected)):
                    held, visible = os.fstat(fd), os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
                    require(stat.S_ISREG(held.st_mode) and stat.S_ISREG(visible.st_mode) and
                            all(metadata(held, b'')[key] == lease[key] and metadata(visible, b'')[key] == lease[key]
                                for key in LEASE_KEYS if key not in ('sha256', 'bytes')) and held.st_size == lease['bytes'],
                            'Final file descriptor/path lease changed')
                replace(source.name, target.name, src_dir_fd=src.fd, dst_dir_fd=dst.fd)
                os.fsync(dst.fd)
                src.check()
                dst.check()
                check_lock()
                _, installed = read_at(dst, target.name)
                # Rename updates ctime; every other held candidate field must match.
                require(all(installed[key] == staged_expected[key] for key in LEASE_KEYS if key != 'ctime_ns'),
                        'Installed code identity changed')
                return installed
            finally:
                os.close(target_fd)
        finally:
            os.close(source_fd)


def set_stage_mode(path, mode):
    with Parent(path.parent) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent.fd)
        try:
            held = os.fstat(fd)
            require(stat.S_ISREG(held.st_mode) and (held.st_nlink, held.st_uid, held.st_gid, stat.S_IMODE(held.st_mode)) == (1, UID, GID, 0o600),
                    'Unsafe private stage')
            os.fchmod(fd, mode)
            os.fsync(fd)
            parent.check()
            _, info = read_at(parent, path.name)
            require((info['dev'], info['ino']) == (held.st_dev, held.st_ino), 'Stage path replaced')
            return info
        finally:
            os.close(fd)


def restore_owned(session, value, check_lock):
    """Restore only verified installed identities; intent alone never grants ownership."""
    uncertain = list(value['uncertain'])
    if value['intent'] is not None and value['intent'] not in uncertain:
        uncertain.append(value['intent'])
    value['uncertain'] = uncertain
    conflicts = []
    value['phase'] = 'rolling_back'
    try:
        journal(session, value)
    except BaseException:
        pass  # Existing durable intent remains; leases also remain in memory.
    for index in reversed(range(len(PATHS))):
        path = PATHS[index]
        record = value['files'][path]
        if record['installed'] is None or path in uncertain:
            continue
        try:
            check_lock()
            verify_lease(path, record['installed'])
            data, original_meta = read(Path(session) / ('original-' + str(index) + '.js'))
            require(original_meta['mode'] == 0o600 and digest(data) == record['original']['sha256'], 'Original backup changed')
            staged = Path(session) / ('restore-' + uuid.uuid4().hex + '.js')
            write_private(staged, data)
            candidate = set_stage_mode(staged, record['original']['mode'])
            verify_lease(path, record['installed'])
            value['intent'] = path
            journal(session, value)
            restored = move_code(staged, path, record['installed'], candidate, check_lock)
            record['original'] = restored
            record['installed'] = None
            record['candidate'] = None
            value['intent'] = uncertain[-1] if uncertain else None
            journal(session, value)
        except BaseException:
            conflicts.append(path)
            if value['intent'] == path and path not in uncertain:
                uncertain.append(path)
    value['intent'] = uncertain[-1] if uncertain else None
    value['phase'] = 'manual_review' if uncertain or conflicts else 'rolled_back'
    try:
        journal(session, value)
    except BaseException:
        value['phase'] = 'manual_review'
    return value['phase'] == 'rolled_back'


def apply():
    state, originals = inspect()
    unfinished()
    if state == 'after':
        return None
    with locked() as check_lock:
        unfinished()
        state, originals = inspect()
        if state == 'after':
            return None
        device = backup_device()
        require(all(originals[path][1]['dev'] == device for path in PATHS),
                'Backup staging and app.js must use the same filesystem; no replacement made')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        session = session_name('repair-' + stamp + '-' + uuid.uuid4().hex)
        private_dir(session, create=True)
        value = {'release': RELEASE, 'app': str(APP), 'phase': 'prepared', 'intent': None, 'uncertain': [],
                 'files': {path: {'original': originals[path][1], 'candidate': None, 'installed': None} for path in PATHS}}
        # Durable preparation precedes staging, so interrupted preparation is visible.
        journal(session, value)
        for index, path in enumerate(PATHS):
            write_private(session / ('original-' + str(index) + '.js'), originals[path][0])
            write_private(session / ('stage-' + str(index) + '.js'), repair(path, originals[path][0]))
        try:
            lint(session)
        except BaseException:
            value['phase'] = 'rolled_back'
            journal(session, value)
            raise Refusal('Pinned staged JavaScript byte verification failed; no live replacement. Private session: ' + str(session))
        bundle_lease(value, check_lock)
        value['phase'] = 'applying'
        journal(session, value)
        previous = signal.getsignal(signal.SIGTERM)
        def interrupted(signum, frame):
            raise Refusal('Repair interrupted')
        signal.signal(signal.SIGTERM, interrupted)
        try:
            for index, path in enumerate(PATHS):
                bundle_lease(value, check_lock)
                staged = session / ('stage-' + str(index) + '.js')
                candidate = set_stage_mode(staged, originals[path][1]['mode'])
                require(candidate['sha256'] == FILES[path]['after_sha256'], 'Stage bytes changed')
                value['files'][path]['candidate'] = candidate
                value['intent'] = path
                journal(session, value)
                bundle_lease(value, check_lock)
                value['files'][path]['installed'] = move_code(staged, path, originals[path][1], candidate, check_lock)
                value['intent'] = None
                journal(session, value)
            bundle_lease(value, check_lock)
            value['phase'] = 'applied'
            journal(session, value)
        except BaseException:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            complete = restore_owned(session, value, check_lock)
            raise Refusal(('Repair failed; verified owned code restored.' if complete else
                           'Repair stopped; uncertain or concurrent changes require manual review.') +
                          ' Private session: ' + str(session))
        finally:
            signal.signal(signal.SIGTERM, previous)
        return session


def rollback(name):
    caller()
    inventory()
    session = session_name(name)
    with locked() as check_lock:
        unfinished(except_session=name)
        value = load(session)
        require(value['phase'] == 'applied' and value['intent'] is None and not value['uncertain'],
                'Only a fully verified applied session may roll back')
        bundle_lease(value, check_lock)
        require(restore_owned(session, value, check_lock), 'Rollback stopped for manual review. Private session: ' + str(session))
    return session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='check', choices=('check', 'apply', 'rollback'))
    parser.add_argument('--session', help='Exact private session basename; rollback only')
    args = parser.parse_args()
    try:
        require((args.action == 'rollback') == (args.session is not None), 'Session is required only for rollback')
        if args.action == 'check':
            state, files = inspect()
            unfinished()
            print('CHECK ' + ('READY' if state == 'before' else 'ALREADY_REPAIRED'))
            for path in PATHS:
                print('CODE ' + path + ' sha256=' + files[path][1]['sha256'])
            print('Read-only check complete; no application, data or repository operation.')
        elif args.action == 'apply':
            session = apply()
            print('ALREADY_REPAIRED; no replacement or new backup.' if session is None else 'REPAIRED ' + ', '.join(PATHS))
            if session is not None:
                print('PRIVATE_ROLLBACK ' + str(session))
                print('ROLLBACK_COMMAND python3 installer.py rollback --session ' + session.name)
        else:
            print('ROLLED_BACK ' + str(rollback(args.session)))
        return 0
    except (Refusal, OSError, ValueError, subprocess.SubprocessError) as error:
        # Metadata-only diagnostics: never print subprocess output or source bytes.
        message = str(error) if isinstance(error, Refusal) else type(error).__name__ + '; check refused safely'
        print('REFUSED ' + message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
