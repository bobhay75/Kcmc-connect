#!/usr/bin/env python3
"""Fixed-account PR161 public-brand transaction; Python 3.6+, no network.

Place beside the unchanged reviewed manifest/check-release.py/after/before files.
check is read-only. apply changes exactly the thirteen manifest targets. A private
journal and actual-byte backups allow conditional rollback after interruption.
This adapter never reads or changes application configuration or data stores.
"""
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

HERE = Path(__file__).resolve().parent
APP = Path('/home/bobsome1/public_html/kcmc-connect')
BACKUPS = Path('/home/bobsome1/kcmc-brand-oct20-backups')
UID, GID = 2162, 2147
RELEASE = 'kcmc-brand-oct20-pr161'
MANIFEST_PIN = '84ed0526d049b04d066d0498efc96b098eb05f54a267600b6aa0256b821967ed'
PHP_CANDIDATES = ('/opt/alt/php82/usr/bin/php',
                  '/opt/cpanel/ea-php82/root/usr/bin/php',
                  '/usr/local/bin/php', '/usr/bin/php')
MODIFIED = ('index.php', 'home-welcome.css', 'sw.js')
ADDED = tuple('assets/visuals/' + name + '-20261018.jpg' for name in (
    'kcmc-contemporary-after-service', 'kcmc-contemporary-fellowship',
    'kcmc-contemporary-gathering', 'kcmc-contemporary-music',
    'kcmc-contemporary-room', 'kcmc-contemporary-room-portrait',
    'kcmc-traditional-front', 'kcmc-traditional-message',
    'kcmc-traditional-sanctuary', 'kcmc-traditional-worship'))
PATHS = MODIFIED + ADDED
ORDER = ADDED + ('home-welcome.css', 'index.php', 'sw.js')
GUARDS = ('app-navigation.js', 'app-theme.css', 'app.js',
          'assets/icons/icon-192.png', 'assets/icons/icon-512.png',
          'assets/visuals/kcmc-building-original-20261018.jpg',
          'lib/screen-navigation.php', 'manifest.webmanifest',
          'public-presentation.css', 'public-presentation.js', 'styles.css')
MAX_BYTES = 16 * 1024 * 1024
LEASE_KEYS = ('sha256', 'bytes', 'dev', 'ino', 'mtime_ns', 'ctime_ns',
              'mode', 'uid', 'gid', 'nlink')


class Refusal(RuntimeError):
    pass


def need(ok, message):
    if not ok:
        raise Refusal(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('ascii')


def caller():
    need((os.getuid(), os.geteuid(), os.getgid(), os.getegid()) ==
         (UID, UID, GID, GID), 'Run as hosting account UID 2162 / GID 2147')
    need(APP.is_absolute() and BACKUPS.is_absolute() and HERE.is_absolute() and
         'public_html' not in BACKUPS.parts and 'public_html' not in HERE.parts and
         APP != BACKUPS and APP != HERE, 'Fixed private staging roots required')


class Parent(object):
    """Hold no-follow descriptors for every ancestor throughout an operation."""
    def __init__(self, path):
        self.path, self.opened = Path(path), []

    def __enter__(self):
        need(self.path.is_absolute(), 'Absolute path required')
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
            need(stat.S_ISDIR(visible.st_mode) and
                 (visible.st_dev, visible.st_ino) == (held.st_dev, held.st_ino),
                 'Parent directory changed or became linked: ' + str(path))
            if path == APP or APP in path.parents:
                need((visible.st_uid, visible.st_gid) == (UID, GID) and
                     not stat.S_IMODE(visible.st_mode) & 0o7002,
                     'Unsafe application directory metadata')
            if path == BACKUPS or BACKUPS in path.parents:
                need((visible.st_uid, visible.st_gid, stat.S_IMODE(visible.st_mode)) ==
                     (UID, GID, 0o700), 'Unsafe private directory metadata')

    def __exit__(self, *unused):
        for fd, unused_path in reversed(self.opened):
            os.close(fd)
        self.opened = []


def metadata(info, raw):
    return {'sha256': digest(raw), 'bytes': len(raw), 'dev': info.st_dev,
            'ino': info.st_ino, 'mtime_ns': info.st_mtime_ns,
            'ctime_ns': info.st_ctime_ns, 'mode': stat.S_IMODE(info.st_mode),
            'uid': info.st_uid, 'gid': info.st_gid, 'nlink': info.st_nlink}


def same(first, second):
    return first is None and second is None or (
        first is not None and second is not None and
        all(first[key] == second[key] for key in LEASE_KEYS))


def read_at(parent, name, missing=False):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=parent.fd)
    except FileNotFoundError:
        parent.check()
        need(missing, 'Missing file: ' + name)
        return None, None
    try:
        prior = os.fstat(fd)
        need(stat.S_ISREG(prior.st_mode) and prior.st_nlink == 1 and
             (prior.st_uid, prior.st_gid) == (UID, GID),
             'Nonregular, linked or foreign-owned file refused: ' + name)
        need(0 <= prior.st_size <= MAX_BYTES, 'Oversized file refused')
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            need(size <= MAX_BYTES, 'Oversized file refused')
        raw = b''.join(chunks)
        first = metadata(prior, raw)
        need(same(first, metadata(os.fstat(fd), raw)) and size == prior.st_size,
             'File changed during read: ' + name)
        visible = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        need(stat.S_ISREG(visible.st_mode) and same(first, metadata(visible, raw)),
             'File replaced during read: ' + name)
        parent.check()
        return raw, first
    finally:
        os.close(fd)


def read(path, missing=False, modes=(0o644, 0o664)):
    path = Path(path)
    with Parent(path.parent) as parent:
        raw, info = read_at(parent, path.name, missing)
    need(info is None or info['mode'] in modes, 'Unsafe file mode: ' + str(path))
    return raw, info


def pin(info):
    return None if info is None else {k: info[k] for k in ('sha256', 'bytes')}


def manifest():
    raw, unused = read(HERE / 'manifest.json')
    need(digest(raw) == MANIFEST_PIN, 'Reviewed release manifest changed')
    value = json.loads(raw.decode('utf-8'))
    need(set(value['variants']) == {'main', 'livecalendar'}, 'Unknown variants')
    for variant in value['variants'].values():
        need(set(variant['before']) == set(PATHS) == set(variant['after']) and
             set(variant['guards']) == set(GUARDS), 'Exact reviewed scope required')
        need(all(variant['before'][name] is None for name in ADDED),
             'New images must be absent before installation')
    for name, expected in value['payloads'].items():
        unused, actual = read(HERE / name)
        need(pin(actual) == expected, 'Reviewed payload changed: ' + name)
    return value


def inspect(reviewed):
    found = {name: read(APP / name, missing=name in ADDED) for name in PATHS}
    guards = {name: read(APP / name) for name in GUARDS}
    matches = []
    for variant, scope in reviewed['variants'].items():
        if all(pin(guards[name][1]) == expected for name, expected in scope['guards'].items()):
            for phase in ('before', 'after'):
                if all(pin(found[name][1]) == expected for name, expected in scope[phase].items()):
                    matches.append((variant, phase))
    need(len(matches) == 1, 'Unknown, mixed or incomplete public bundle; refused')
    for name, unused in list(found.items()) + list(guards.items()):
        expected = (found if name in found else guards)[name][1]
        need(same(read(APP / name, missing=name in ADDED)[1], expected),
             'File changed during preflight: ' + name)
    return matches[0][0], matches[0][1], found, guards


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
        need(stat.S_ISDIR(info.st_mode) and
             (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (UID, GID, 0o700),
             'Unsafe private directory: ' + str(path))
        parent.check()


def write_new(path, raw, mode=0o600):
    path = Path(path)
    with Parent(path.parent) as parent:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     mode, dir_fd=parent.fd)
        try:
            os.fchmod(fd, mode)
            need((os.fstat(fd).st_uid, os.fstat(fd).st_gid) == (UID, GID),
                 'New-file ownership differs from reviewed account')
            view = memoryview(raw)
            while view:
                count = os.write(fd, view)
                need(count > 0, 'Private write failed')
                view = view[count:]
            os.fsync(fd)
            parent.check()
            visible, held = os.stat(path.name, dir_fd=parent.fd, follow_symlinks=False), os.fstat(fd)
            need((visible.st_dev, visible.st_ino, visible.st_nlink) ==
                 (held.st_dev, held.st_ino, 1), 'Private write path changed')
            os.fsync(parent.fd)
        finally:
            os.close(fd)
    return read(path, modes=(mode,))[1]


def replace(source, target, source_info, target_info):
    """Check exact leases immediately before one anchored atomic replacement."""
    source, target = Path(source), Path(target)
    with Parent(source.parent) as src, Parent(target.parent) as dst:
        need(same(read_at(src, source.name)[1], source_info), 'Staged file changed')
        need(same(read_at(dst, target.name, missing=target_info is None)[1], target_info),
             'Target changed immediately before replacement: ' + target.name)
        need(os.fstat(src.fd).st_dev == os.fstat(dst.fd).st_dev,
             'Stage and target must be on the same filesystem')
        src.check()
        dst.check()
        os.replace(source.name, target.name, src_dir_fd=src.fd, dst_dir_fd=dst.fd)
        os.fsync(src.fd)
        os.fsync(dst.fd)
        src.check()
        dst.check()


def journal(session, value):
    path = session / 'journal.json'
    prior = read(path, missing=True, modes=(0o600,))[1]
    tmp = session / ('journal-' + uuid.uuid4().hex + '.tmp')
    info = write_new(tmp, encode(value))
    replace(tmp, path, info, prior)


def read_journal(session):
    private_dir(session)
    raw, unused = read(session / 'journal.json', missing=True, modes=(0o600,))
    if raw is None:
        raise FileNotFoundError('Transaction journal has not been created')
    value = json.loads(raw.decode('ascii'))
    need(value['release'] == RELEASE and value['manifest_sha256'] == MANIFEST_PIN and
         value['app'] == str(APP) and value['variant'] in ('main', 'livecalendar') and
         set(value['original']) == set(MODIFIED) and set(value['guards']) == set(GUARDS),
         'Journal is outside this release scope')
    for info in list(value['original'].values()) + list(value['guards'].values()):
        need(set(info) == set(LEASE_KEYS) and info['mode'] in (0o644, 0o664) and
             (info['uid'], info['gid'], info['nlink']) == (UID, GID, 1),
             'Invalid recorded metadata')
    return value


def unfinished(except_session=None):
    private_dir(BACKUPS)
    entries = list(BACKUPS.iterdir())
    need(len(entries) < 500, 'Backup inventory requires manual review')
    for item in entries:
        if item.name == 'deploy.lock' or item == except_session:
            continue
        need(re.fullmatch(r'release-\d{8}T\d{6}Z-[0-9a-f]{32}', item.name) is not None,
             'Unrecognized backup entry requires review: ' + item.name)
        try:
            value = read_journal(item)
        except FileNotFoundError:
            raise Refusal('Unstarted session requires exact-session rollback: ' + item.name)
        need(value['state'] != 'recovered_code_with_photos_retained',
             'Code restored; retained photos require a public-reference review: ' + item.name)
        need(value['state'] in ('applied', 'rolled_back'),
             'Unfinished transaction requires exact-session rollback: ' + item.name)


def existing_journals_clear():
    """Read existing journals without creating a directory or lock file."""
    try:
        BACKUPS.lstat()
    except FileNotFoundError:
        return
    unfinished()


@contextlib.contextmanager
def deployment_lock():
    private_dir(BACKUPS, create=True)
    with Parent(BACKUPS) as parent:
        fd = os.open('deploy.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                     0o600, dir_fd=parent.fd)
        try:
            info = os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                 (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (UID, GID, 0o600),
                 'Unsafe deployment lock')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            visible = os.stat('deploy.lock', dir_fd=parent.fd, follow_symlinks=False)
            need((visible.st_dev, visible.st_ino) == (info.st_dev, info.st_ino),
                 'Deployment lock changed')
            parent.check()
            yield
        finally:
            os.close(fd)


def php_cli():
    for path in PHP_CANDIDATES:
        if not os.path.isfile(path) or not os.access(path, os.X_OK):
            continue
        result = subprocess.run([path, '-n', '-v'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=15)
        match = re.search(br'PHP (\d+)\.(\d+)\.', result.stdout)
        if result.returncode == 0 and match and (int(match.group(1)), int(match.group(2))) >= (8, 2):
            return path
    raise Refusal('A host PHP 8.2+ CLI is required; no application code was executed')


def verify_leases(expected, guards):
    for name, info in list(expected.items()) + list(guards.items()):
        need(same(read(APP / name, missing=name in ADDED)[1], info),
             'Concurrent change refused: ' + name)


def backup_path(session, name):
    need(name in MODIFIED, 'Backup outside modified scope')
    return session / ('before-' + name)


def verify_known_state(reviewed, record):
    """Rollback permits only exact before/after bytes with reviewed owner/mode."""
    scope = reviewed['variants'][record['variant']]
    current = {}
    for name in GUARDS:
        unused, info = read(APP / name)
        need(pin(info) == scope['guards'][name] and same(info, record['guards'][name]),
             'Read-only prerequisite changed; rollback refused: ' + name)
    for name in PATHS:
        unused, info = read(APP / name, missing=name in ADDED)
        need(pin(info) in (scope['before'][name], scope['after'][name]),
             'Unrecognized intervening edit; rollback refused: ' + name)
        if info is not None:
            mode = record['original'][name]['mode'] if name in MODIFIED else 0o644
            need(info['mode'] == mode and (info['uid'], info['gid']) == (UID, GID),
                 'Target metadata changed; rollback refused: ' + name)
        current[name] = info
    return current


def retire_unstarted(reviewed, session, record=None):
    """Retire preparation interrupted before any live write; restore nothing."""
    variant, phase, found, guards = inspect(reviewed)
    need(phase == 'before', 'An unstarted session cannot account for changed live files')
    if record is not None:
        need(record['state'] == 'preparing' and record['variant'] == variant and
             not record.get('installed') and record.get('intent') is None,
             'Session cannot be retired as unstarted')
        verify_leases({name: found[name][1] for name in ADDED}, record['guards'])
        for name in MODIFIED:
            need(same(found[name][1], record['original'][name]),
                 'Original target metadata changed during interrupted preparation')
    else:
        # The only possible writes before the first durable journal are the
        # session directory, initial journal temporary, and (older adapter)
        # three actual backups. Never remove or restore any of these files.
        private_dir(session)
        entries = list(session.iterdir())
        need(len(entries) <= 10, 'Unstarted session inventory requires review')
        allowed = {'before-' + name for name in MODIFIED}
        for path in entries:
            need(path.name in allowed or
                 re.fullmatch(r'journal-[0-9a-f]{32}\.tmp', path.name) is not None,
                 'Unrecognized pre-journal entry requires review')
            read(path, modes=(0o600,))
        record = {'version': 1, 'release': RELEASE, 'manifest_sha256': MANIFEST_PIN,
                  'app': str(APP), 'variant': variant,
                  'original': {name: found[name][1] for name in MODIFIED},
                  'guards': {name: guards[name][1] for name in GUARDS}, 'installed': []}
    record.update(state='rolled_back', intent=None, retired_before_live_writes=True)
    journal(session, record)
    return {'result': 'unstarted_session_retired', 'variant': variant,
            'session': str(session), 'writes_performed': True,
            'live_writes_performed': False}


def rollback_locked(reviewed, session, cleanup_photos=False):
    try:
        record = read_journal(session)
    except FileNotFoundError:
        return retire_unstarted(reviewed, session)
    if record['state'] == 'preparing':
        return retire_unstarted(reviewed, session, record)
    scope = reviewed['variants'][record['variant']]
    if record['state'] == 'rolled_back':
        current = verify_known_state(reviewed, record)
        need(all(pin(current[name]) == scope['before'][name] for name in PATHS),
             'Retired rollback receipt cannot change a later installation')
        return {'result': 'already_rolled_back', 'variant': record['variant'],
                'session': str(session), 'writes_performed': False}
    if record['state'] == 'recovered_code_with_photos_retained':
        current = verify_known_state(reviewed, record)
        need(all(pin(current[name]) == scope['before'][name] for name in MODIFIED),
             'Recovered receipt cannot change a later installation')
    originals = {}
    for name in MODIFIED:
        raw, info = read(backup_path(session, name), modes=(0o600,))
        need(pin(info) == scope['before'][name] == pin(record['original'][name]),
             'Actual private backup failed verification: ' + name)
        originals[name] = raw
    current = verify_known_state(reviewed, record)  # Refuse all unknown state before restoring anything.
    if cleanup_photos:
        # Only the same uninterrupted apply process may clean up introduced
        # photographs automatically. Every original/current postimage must still
        # be the exact inode and lease captured by that process. Rename can alter
        # ctime, so postimage comparison excludes only that one field.
        need(set(record.get('staged_after', {})) == set(PATHS), 'Missing immediate transaction leases')
        for name, info in current.items():
            if info is None:
                continue
            if pin(info) == scope['after'][name]:
                expected = record['staged_after'][name]
                need(all(info[key] == expected[key] for key in LEASE_KEYS if key != 'ctime_ns'),
                     'Installed inode changed; automatic cleanup refused: ' + name)
            else:
                need(same(info, record['original'][name]),
                     'Original inode changed; automatic cleanup refused: ' + name)
    record['state'] = 'rolling_back'
    journal(session, record)
    for name in ('index.php', 'sw.js', 'home-welcome.css'):
        verify_leases(current, record['guards'])
        if pin(current[name]) == scope['before'][name]:
            continue
        temporary = session / ('restore-' + uuid.uuid4().hex + '-' + name)
        staged = write_new(temporary, originals[name], record['original'][name]['mode'])
        record['intent'] = 'restore:' + name
        journal(session, record)
        verify_leases(current, record['guards'])
        replace(temporary, APP / name, staged, current[name])
        current[name] = read(APP / name)[1]
        need(pin(current[name]) == scope['before'][name], 'Restore verification failed')
    verify_leases(current, record['guards'])
    retained = [name for name in ADDED if current[name] is not None]
    if retained and not cleanup_photos:
        record.update(state='recovered_code_with_photos_retained', intent=None,
                      retained_images=retained)
        journal(session, record)
        return {'result': 'recovered_code_with_photos_retained', 'variant': record['variant'],
                'session': str(session), 'writes_performed': True,
                'retained_images': retained, 'exact_original_bundle': False,
                'next_step': 'Review additional public consumers before any photo cleanup; no cleanup bypass is provided'}
    # All consumers supplied by this release and all read-only public guards now
    # match their recorded originals. Refuse deletion if any pinned text consumer
    # retains a new-image reference. No private/application store is inspected.
    need(all(pin(current[name]) == scope['before'][name] for name in MODIFIED),
         'Retained release consumers prevent image removal')
    consumer_bytes = [read(APP / name)[0] for name in MODIFIED +
                      tuple(n for n in GUARDS if not n.endswith(('.jpg', '.png')))]
    for name in ADDED:
        need(all(Path(name).name.encode('ascii') not in raw for raw in consumer_bytes),
             'Retained public consumer references added image: ' + name)
        verify_leases(current, record['guards'])
        if current[name] is None:
            continue
        record['intent'] = 'remove:' + name
        journal(session, record)
        target = APP / name
        with Parent(target.parent) as parent:
            need(same(read_at(parent, target.name)[1], current[name]),
                 'Added image changed immediately before removal')
            parent.check()
            os.unlink(target.name, dir_fd=parent.fd)
            os.fsync(parent.fd)
            parent.check()
        current[name] = None
    variant, phase, unused, unused_guards = inspect(reviewed)
    need((variant, phase) == (record['variant'], 'before'), 'Rollback tuple verification failed')
    record.update(state='rolled_back', intent=None)
    journal(session, record)
    return {'result': 'rolled_back', 'variant': variant, 'session': str(session),
            'writes_performed': True}


def apply(reviewed, expected_variant):
    variant, phase, found, guards = inspect(reviewed)
    need(variant == expected_variant, 'Unexpected host variant; refused')
    if phase == 'after':
        existing_journals_clear()
        return {'result': 'already_installed', 'variant': variant, 'writes_performed': False}
    php = php_cli()
    with deployment_lock():
        unfinished()
        variant, phase, found, guards = inspect(reviewed)
        need((variant, phase) == (expected_variant, 'before'), 'Host changed since preflight')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        session = BACKUPS / ('release-' + stamp + '-' + uuid.uuid4().hex)
        private_dir(session, create=True)
        need(session.stat().st_dev == APP.stat().st_dev, 'Private stage must share application filesystem')
        record = {'version': 1, 'release': RELEASE, 'manifest_sha256': MANIFEST_PIN,
                  'app': str(APP), 'variant': variant, 'state': 'preparing', 'intent': None,
                  'original': {name: found[name][1] for name in MODIFIED},
                  'guards': {name: guards[name][1] for name in GUARDS}, 'installed': []}
        journal(session, record)
        for name in MODIFIED:
            write_new(backup_path(session, name), found[name][0])
            need(pin(read(backup_path(session, name), modes=(0o600,))[1]) == pin(found[name][1]),
                 'Actual backup verification failed')
        try:
            staged = {}
            for number, name in enumerate(ORDER):
                raw, info = read(HERE / 'after' / name)
                need(pin(info) == reviewed['variants'][variant]['after'][name], 'Payload changed')
                path = session / ('stage-%02d-' % number + Path(name).name)
                mode = found[name][1]['mode'] if name in MODIFIED else 0o644
                staged[name] = (path, write_new(path, raw, mode))
            lint = subprocess.run([php, '-n', '-l', str(staged['index.php'][0])],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            need(lint.returncode == 0, 'Host PHP lint failed before any live replacement')
            expected = {name: found[name][1] for name in PATHS}
            guard_leases = record['guards']
            verify_leases(expected, guard_leases)
            record['staged_after'] = {name: staged[name][1] for name in PATHS}
            record['state'] = 'installing'
            journal(session, record)
            for name in ORDER:
                verify_leases(expected, guard_leases)
                record['intent'] = 'install:' + name
                journal(session, record)
                verify_leases(expected, guard_leases)
                replace(staged[name][0], APP / name, staged[name][1], expected[name])
                unused, actual = read(APP / name)
                need(pin(actual) == reviewed['variants'][variant]['after'][name] and
                     actual['mode'] == staged[name][1]['mode'], 'Installed file verification failed')
                expected[name] = actual
                record['installed'].append(name)
                record['intent'] = None
                journal(session, record)
            after_variant, after_phase, unused, unused_guards = inspect(reviewed)
            need((after_variant, after_phase) == (variant, 'after'), 'After tuple verification failed')
            verify_leases(expected, guard_leases)
            record['state'] = 'applied'
            journal(session, record)
            return {'result': 'installed', 'variant': variant, 'session': str(session),
                    'manifest_sha256': MANIFEST_PIN, 'php_cli': php,
                    'files': list(ORDER), 'writes_performed': True,
                    'rollback_command': 'python3 -I -B install-brand.py rollback --session ' + session.name,
                    'public_browser_acceptance': 'required'}
        except (Exception, KeyboardInterrupt) as exc:
            try:
                rollback_locked(reviewed, session, cleanup_photos=True)
            except (Exception, KeyboardInterrupt) as recovery:
                raise Refusal('Transaction stopped. Conditional rollback requires review. '
                              'Session: %s; cause: %s; rollback: %s' % (session, exc, recovery))
            raise Refusal('Transaction failed and original bundle was restored. Session: %s; cause: %s' %
                          (session, exc))


def rollback(reviewed, session_name):
    need(re.fullmatch(r'release-\d{8}T\d{6}Z-[0-9a-f]{32}', session_name) is not None,
         'Provide the exact printed session basename, not a path')
    session = BACKUPS / session_name
    with deployment_lock():
        unfinished(except_session=session)
        return rollback_locked(reviewed, session)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='check', choices=('check', 'apply', 'rollback'))
    parser.add_argument('--expected-variant', choices=('main', 'livecalendar'))
    parser.add_argument('--session')
    args = parser.parse_args()
    need((args.action == 'apply') == (args.expected_variant is not None),
         '--expected-variant is required only for apply')
    need((args.action == 'rollback') == (args.session is not None),
         '--session is required only for rollback')
    caller()
    reviewed = manifest()
    if args.action == 'check':
        variant, phase, unused, unused_guards = inspect(reviewed)
        existing_journals_clear()
        result = {'result': 'check', 'variant': variant, 'state': phase,
                  'manifest_sha256': MANIFEST_PIN, 'writes_performed': False}
    elif args.action == 'apply':
        result = apply(reviewed, args.expected_variant)
    else:
        result = rollback(reviewed, args.session)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise Refusal('Process interrupted by signal %s' % signum)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('REFUSED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
