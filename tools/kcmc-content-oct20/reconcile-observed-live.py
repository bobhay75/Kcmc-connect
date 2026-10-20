#!/usr/bin/env python3
"""Publish the reviewed October 20 delta against one inspected live snapshot.

The original publisher and fixture remain unchanged. This separate operation
adds the explicitly approved Friends of Faith class only when the exact reviewed
live snapshot lacks it, then uses the original planner for every other change.
There is one content replacement, an actual-byte backup, and conditional rollback.
Python 3.6+. No network, configurable target, force flag, or hash override.
"""
from __future__ import print_function

import argparse
import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types
import unicodedata

STAGE = Path('/home/bobsome1/kcmc-pr161-check-z8h3hqw2')
CONTENT = Path('/home/bobsome1/public_html/kcmc-connect/data/content.json')
BACKUPS = Path('/home/bobsome1/kcmc-content-oct20-backups')
UID, GID = 2162, 2147
OBSERVED_SHA = '966fd76335dab9a1f7a4bf85edc889a2aa49fe1093fb40249741ca792cb2035b'
PUBLISHER_PIN = '5ab350947ca46d00fb002eca8fd73997bbfea57642a3025080bfc1a89a7209d5'
FIXTURE_PIN = '382d7d80029f1bc4a45c57b2ba0e2a0abfb95b3353a4bb4914b5551693ccb871'
IDENTIFIER = 'faith-friends-20261018'
KNOWN_CONFLICT = 'missing_known_record:events.' + IDENTIFIER
OPERATION = 'kcmc-observed-content-reconciliation-20261020'


def pinned_file(path, expected):
    """Bounded stable no-follow read before executing the already reviewed code."""
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise RuntimeError('unsafe_staging_parent')
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        prior = os.fstat(handle.fileno())
        if (not stat.S_ISREG(prior.st_mode) or prior.st_nlink != 1 or
                (prior.st_uid, prior.st_gid) != (UID, GID) or
                prior.st_size > 100000):
            raise RuntimeError('unsafe_staged_file')
        raw = handle.read(100001)
        after = os.fstat(handle.fileno())
    visible = path.lstat()
    stamp = lambda value: (value.st_dev, value.st_ino, value.st_size,
                           value.st_mtime_ns, value.st_ctime_ns, value.st_mode,
                           value.st_uid, value.st_gid, value.st_nlink)
    if stamp(prior) != stamp(after) or stamp(after) != stamp(visible):
        raise RuntimeError('staged_file_changed_during_read')
    if len(raw) > 100000 or hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError('staged_file_checksum_failed:' + path.name)
    return raw


def load_publisher():
    path = STAGE / 'content-publication' / 'publish.py'
    source = pinned_file(path, PUBLISHER_PIN)
    pinned_file(path.parent / 'reviewed-content.json', FIXTURE_PIN)
    pub = types.ModuleType('kcmc_verified_editorial_publisher')
    pub.__file__ = str(path)
    exec(compile(source, str(path), 'exec'), pub.__dict__)
    if pub.CONTENT != CONTENT or pub.BACKUPS != BACKUPS or pub.FIXTURE_PIN != FIXTURE_PIN:
        raise RuntimeError('fixed_publisher_scope_changed')
    return pub


def class_clue(event):
    value = ' '.join(str(event.get(key, '')) for key in
                     ('id', 'title', 'location', 'description'))
    words = re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', value).casefold())
    tokens = set(words)
    return (bool(tokens.intersection({'faith', 'friend', 'friends', 'chandler'})) or
            {'pairs', 'spares'}.issubset(tokens) or
            {'sunday', 'bible', 'study'}.issubset(tokens) or
            'becoming like jesus' in ' '.join(words))


def plan_reconciliation(pub, raw, reviewed, now):
    pub.need(pub.digest(raw) == OBSERVED_SHA, 'live_content_changed_since_review')
    original = pub.decode(raw)
    unused_candidate, unused_actions, conflicts = pub.plan(original, reviewed, now)
    pub.need(conflicts == [KNOWN_CONFLICT],
             'unexpected_editorial_conflicts:' + ','.join(conflicts))
    # Check every record, including hidden/deleted records and future-start
    # recurrences. "friendship" in Hope Keepers is not a class identity.
    pub.need(not any(class_clue(item) for item in original['events']),
             'possible_existing_class_requires_review')
    changes = [item for item in reviewed['records']
               if item['section'] == 'events' and item['id'] == IDENTIFIER]
    pub.need(len(changes) == 1 and not changes[0]['originally_missing'],
             'reviewed_class_identity_changed')
    seeded = copy.deepcopy(original)
    seeded['events'].append(copy.deepcopy(changes[0]['target']))
    candidate, actions, conflicts = pub.plan(seeded, reviewed, now)
    pub.need(not conflicts, 'additional_editorial_conflicts:' + ','.join(conflicts))
    pub.need(len(pub.encoded(candidate)) <= pub.MAX_BYTES, 'oversized_candidate')
    return candidate, ['add:events.' + IDENTIFIER] + actions


def live_read(pub):
    raw, info = pub.read_file(pub.CONTENT)
    pub.need((info.st_uid, info.st_gid) == (UID, GID), 'unexpected_content_owner')
    return raw, info


def check(pub, now):
    raw, unused = live_read(pub)
    candidate, actions = plan_reconciliation(pub, raw, pub.fixture(), now)
    return {'result': 'ready', 'read_only': True, 'writes_performed': False,
            'before_sha256': pub.digest(raw), 'after_sha256': pub.digest(pub.encoded(candidate)),
            'actions': actions, 'conflicts': []}


def apply(pub, now):
    # Resolve all known preconditions before even creating a cooperative lock.
    preflight = check(pub, now)
    print(json.dumps(preflight, indent=2), flush=True)
    lock_path = Path(str(pub.CONTENT) + '.lock')
    pub.ordinary(lock_path, missing=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, 'a+b') as handle:
        held, visible = os.fstat(handle.fileno()), pub.ordinary(lock_path)
        pub.need(stat.S_ISREG(held.st_mode) and held.st_nlink == 1 and
                 (held.st_uid, held.st_gid) == (UID, GID) and
                 (held.st_dev, held.st_ino) == (visible.st_dev, visible.st_ino),
                 'unsafe_content_lock')
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        raw, info = live_read(pub)
        reviewed = pub.fixture()
        candidate, actions = plan_reconciliation(pub, raw, reviewed, now)
        after = pub.encoded(candidate)
        pub.need(pub.digest(after) == preflight['after_sha256'], 'plan_changed_since_preflight')
        backup_root = pub.private_directory(pub.BACKUPS)
        stamp = now.astimezone(pub.UTC).strftime('%Y%m%dT%H%M%SZ') + '-' + os.urandom(8).hex()
        backup = backup_root / (stamp + '.json')
        receipt = backup_root / (stamp + '.receipt.json')
        pub.write_private(backup, raw)
        pub.need(pub.digest(pub.read_file(backup)[0]) == OBSERVED_SHA,
                 'backup_verification_failed')
        record = {'version': 1, 'operation': OPERATION, 'target': str(pub.CONTENT),
                  'backup': str(backup), 'before_sha256': OBSERVED_SHA,
                  'after_sha256': pub.digest(after), 'mode': stat.S_IMODE(info.st_mode),
                  'uid': info.st_uid, 'gid': info.st_gid, 'actions': actions,
                  'publisher_sha256': PUBLISHER_PIN, 'fixture_sha256': FIXTURE_PIN}
        pub.write_private(receipt, pub.encoded(record))
        pub.sync_directory(backup_root)
        pub.sync_directory(backup_root.parent)
        rollback = 'python3 -I -B ' + str(pub.HERE / 'publish.py') + ' rollback --receipt ' + str(receipt)
        print('PRIVATE_RECEIPT=' + str(receipt), flush=True)
        print('ROLLBACK_COMMAND=' + rollback, flush=True)
        # The only replacement of live content. The original guarded primitive
        # repeats the expected-hash/inode check immediately before replacement.
        pub.replace_exact(pub.CONTENT, after, OBSERVED_SHA, info)
        installed, unused = live_read(pub)
        pub.need(pub.digest(installed) == record['after_sha256'], 'post_publish_verification_failed')
        document = pub.decode(installed)
        current, unused_actions, conflicts = pub.plan(document, reviewed, now)
        pub.need(not conflicts and current == document, 'publisher_postcheck_failed')
    return {'result': 'published', 'writes_performed': True,
            'sha256': record['after_sha256'], 'receipt': str(receipt),
            'rollback_command': rollback, 'publisher_check': 'already_current',
            'actions': actions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'apply'), nargs='?', default='check')
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 6):
            raise RuntimeError('Python 3.6 or newer is required')
        if (os.getuid(), os.geteuid(), os.getgid(), os.getegid()) != (UID, UID, GID, GID):
            raise RuntimeError('Run in the bobsome1 cPanel Terminal')
        pub = load_publisher()
        now = dt.datetime.now(dt.timezone.utc)
        report = apply(pub, now) if args.command == 'apply' else check(pub, now)
        print(json.dumps(report, indent=2), flush=True)
        return 0
    except Exception as error:
        # A receipt may have been written before an interrupted replacement;
        # do not falsely promise that every failure means nothing changed.
        print(json.dumps({'result': 'stopped', 'reason': str(error),
                          'next_step': 'Keep the complete output and any printed receipt for review.'}),
              file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
