#!/usr/bin/env python3
"""Review, publish, or roll back only the October 20 KCMC editorial delta.

Python 3.6 compatible. The default check is read-only. Apply requires the exact
reviewed live-content hash; the target is fixed and no network call is made.
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
import tempfile
import unicodedata

HERE = Path(__file__).resolve().parent
CONTENT = Path('/home/bobsome1/public_html/kcmc-connect/data/content.json')
BACKUPS = Path('/home/bobsome1/kcmc-content-oct20-backups')
FIXTURE_PIN = '382d7d80029f1bc4a45c57b2ba0e2a0abfb95b3353a4bb4914b5551693ccb871'
MAX_BYTES = 16 * 1024 * 1024
UTC = dt.timezone.utc
CENTRAL_OCTOBER = dt.timezone(dt.timedelta(hours=-5))


class Refusal(Exception):
    pass


def need(ok, code):
    if not ok:
        raise Refusal(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(rows):
    result = {}
    for key, value in rows:
        need(key not in result, 'duplicate_json_key')
        result[key] = value
    return result


def decode(raw):
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda unused: (_ for _ in ()).throw(Refusal('invalid_json_number')))
    except (UnicodeError, ValueError, RecursionError):
        raise Refusal('invalid_json')


def ordinary(path, missing=False):
    path = Path(path)
    need(path.is_absolute(), 'absolute_path_required')
    for p in reversed(path.parents):
        info = p.lstat()
        need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode), 'unsafe_parent')
    try:
        info = path.lstat()
    except FileNotFoundError:
        need(missing, 'missing_file')
        return None
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
         not stat.S_ISLNK(info.st_mode), 'unsafe_file')
    need(info.st_size <= MAX_BYTES, 'oversized_file')
    return info


def read_file(path):
    prior = ordinary(path)
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        current = os.fstat(handle.fileno())
        need((prior.st_dev, prior.st_ino) == (current.st_dev, current.st_ino), 'file_changed')
        raw = handle.read(MAX_BYTES + 1)
        after = os.fstat(handle.fileno())
    final = ordinary(path)
    fields = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns)
    need(fields(prior) == fields(after) == fields(final) and len(raw) <= MAX_BYTES, 'file_changed')
    return raw, final


def fixture():
    raw, unused = read_file(HERE / 'reviewed-content.json')
    need(digest(raw) == FIXTURE_PIN, 'reviewed_package_changed')
    return decode(raw)


def normalize_title(value):
    text = unicodedata.normalize('NFKC', str(value)).casefold().replace('&', ' and ')
    text = re.sub(r'[^\w\s]', ' ', text)
    text = ' '.join(text.split())
    aliases = {
        'salt and light meal and adult bible study': 'salt and light adult bible study',
        'rooted youth group': 'rooted youth',
        'line dancing beginner': 'beginner line dancing',
        'line dancing intermediate': 'intermediate line dancing',
        'faith and friends adult bible study class': 'friends of faith sunday bible study',
    }
    return aliases.get(text, text)


def parse_date(value):
    try:
        return dt.datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise Refusal('invalid_event_date')


def parse_instant(value):
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(Z|[+-]\d{2}:\d{2})', value)
    need(match is not None, 'invalid_expiry')
    offset = match.group(2)
    zone = UTC if offset == 'Z' else dt.timezone((1 if offset[0] == '+' else -1) * dt.timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6])))
    return dt.datetime.strptime(match.group(1), '%Y-%m-%dT%H:%M:%S').replace(tzinfo=zone)


def same_occurrence(existing, target, match_time=True):
    if normalize_title(existing.get('title', '')) != normalize_title(target.get('title', '')):
        return False
    compact = lambda x: re.sub(r'\s+', '', str(x)).casefold()
    if match_time and compact(existing.get('time')) != compact(target.get('time')):
        return False
    start, proposed = parse_date(existing.get('date')), parse_date(target.get('date'))
    if existing.get('repeat') == 'weekly':
        until = existing.get('repeat_until', '')
        return proposed >= start and (proposed - start).days % 7 == 0 and (not until or proposed <= parse_date(until))
    return start == proposed


def plan(document, reviewed, now):
    need(isinstance(document, dict), 'invalid_document')
    need(now.tzinfo is not None, 'timezone_required')
    today = now.astimezone(CENTRAL_OCTOBER).date()
    need(dt.date(2026, 10, 20) <= today <= dt.date(2026, 10, 25), 'review_window_closed')
    candidate = copy.deepcopy(document)
    need(isinstance(candidate.get('meta'), dict) and candidate['meta'].get('content_release') == '3.0.0', 'legacy_content_requires_publishing_desk_review')
    for section in ('events', 'announcements'):
        items = candidate.get(section)
        need(isinstance(items, list), 'invalid_record_container')
        need(all(isinstance(item, dict) and isinstance(item.get('id'), str) and item['id'] for item in items), 'invalid_record')
        need(len({item['id'] for item in items}) == len(items), 'duplicate_record_ids')
    need(isinstance(candidate.get('bulletin'), dict), 'invalid_bulletin')
    actions, conflicts = [], []
    for field, change in reviewed['bulletin'].items():
        actual = candidate['bulletin'].get(field)
        if actual not in change['accepted_before']:
            conflicts.append('bulletin.' + field)
        elif actual != change['after']:
            candidate['bulletin'][field] = copy.deepcopy(change['after'])
            actions.append('update:bulletin.' + field)
    for change in reviewed['records']:
        section, identifier, target = change['section'], change['id'], change['target']
        need(section in ('events', 'announcements') and target['id'] == identifier, 'invalid_review_scope')
        expires = target.get('expires_at')
        if (expires and parse_instant(expires) <= now) or (section == 'events' and target.get('repeat') != 'weekly' and parse_date(target['date']) < today):
            actions.append('skip_expired:' + section + '.' + identifier)
            continue
        existing = next((item for item in candidate[section] if item['id'] == identifier), None)
        if existing is None:
            # Removing a previously known record is an editorial choice. Do not
            # silently recreate it from a historical newsletter or fixture.
            if not change['originally_missing']:
                conflicts.append('missing_known_record:' + section + '.' + identifier)
                continue
            # Match the day independently of time so a new staff time change
            # cannot become a second copy of the same gathering.
            matches = [item for item in candidate[section] if section == 'events' and same_occurrence(item, target, match_time=False)]
            if matches:
                if len(matches) == 1 and same_occurrence(matches[0], target) and matches[0].get('repeat') == 'weekly' and matches[0].get('status', 'published') == 'published' and not matches[0].get('deleted_at'):
                    actions.append('keep_existing_weekly:' + identifier)
                else:
                    conflicts.append('possible_duplicate:' + section + '.' + identifier)
            else:
                candidate[section].append(copy.deepcopy(target))
                actions.append('add:' + section + '.' + identifier)
            continue
        if existing.get('deleted_at') or existing.get('status', 'published') != 'published':
            conflicts.append('editorial_visibility:' + section + '.' + identifier)
            continue
        if section == 'events' and not change['originally_missing']:
            # A known ID must not hide a different event or a new staff time edit.
            if any(existing.get(key) != target.get(key) for key in ('title','date','time','end_time')):
                conflicts.append('event_identity_changed:' + identifier)
                continue
        if change['originally_missing']:
            if all(existing.get(key) == value for key, value in target.items()):
                continue
            if section == 'events' and existing.get('repeat') == 'weekly' and same_occurrence(existing, target):
                actions.append('keep_existing_weekly:' + identifier)
            else:
                conflicts.append('changed_record:' + section + '.' + identifier)
            continue
        for key, update in change['fields'].items():
            actual = {'present': key in existing}
            if key in existing:
                actual['value'] = existing[key]
            if actual not in update['accepted_before']:
                conflicts.append(section + '.' + identifier + '.' + key)
            elif existing.get(key) != update['after'] or key not in existing:
                existing[key] = copy.deepcopy(update['after'])
                actions.append('update:' + section + '.' + identifier + '.' + key)
    return candidate, actions, conflicts


def encoded(document):
    return (json.dumps(document, ensure_ascii=False, sort_keys=False, indent=2) + '\n').encode('utf-8')


def private_directory(path):
    path = Path(path)
    if not path.exists():
        path.mkdir(mode=0o700)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
         info.st_uid == os.geteuid() and not stat.S_IMODE(info.st_mode) & 0o077, 'unsafe_backup_directory')
    return path


def write_private(path, raw):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def sync_directory(path):
    directory = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def replace_exact(path, raw, expected, original_info):
    current, info = read_file(path)
    need(digest(current) == expected and (info.st_dev, info.st_ino) == (original_info.st_dev, original_info.st_ino), 'content_changed_since_review')
    fd, temporary = tempfile.mkstemp(prefix='.kcmc-content-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fchmod(handle.fileno(), stat.S_IMODE(info.st_mode))
            os.fchown(handle.fileno(), info.st_uid, info.st_gid)
            os.fsync(handle.fileno())
        again, unused = read_file(path)
        need(digest(again) == expected, 'content_changed_during_publish')
        os.replace(temporary, str(path))
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish(path, backups, expected, now, reviewed):
    ordinary(path)
    lock_path = Path(str(path) + '.lock')
    ordinary(lock_path, missing=True)
    lock = os.open(str(lock_path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock, 'a+b') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        raw, info = read_file(path)
        need(digest(raw) == expected, 'content_changed_since_review')
        candidate, actions, conflicts = plan(decode(raw), reviewed, now)
        need(not conflicts, 'editorial_conflict_requires_review')
        if candidate == decode(raw):
            return {'result': 'already_current', 'sha256': expected, 'writes_performed': False}
        after = encoded(candidate)
        need(len(after) <= MAX_BYTES, 'oversized_candidate')
        backup_root = private_directory(backups)
        stamp = now.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ') + '-' + os.urandom(4).hex()
        backup = backup_root / (stamp + '.json')
        receipt = backup_root / (stamp + '.receipt.json')
        write_private(backup, raw)
        need(digest(read_file(backup)[0]) == expected, 'backup_verification_failed')
        report = {'version': 1, 'target': str(path), 'backup': str(backup), 'before_sha256': expected,
                  'after_sha256': digest(after), 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid,
                  'gid': info.st_gid, 'actions': actions}
        write_private(receipt, encoded(report))
        sync_directory(backup_root)
        sync_directory(backup_root.parent)
        replace_exact(path, after, expected, info)
        need(digest(read_file(path)[0]) == report['after_sha256'], 'post_publish_verification_failed')
        return {'result': 'published', 'writes_performed': True, 'sha256': report['after_sha256'],
                'receipt': str(receipt), 'actions': actions}


def rollback(path, backups, receipt_path):
    backup_root = private_directory(backups).resolve()
    receipt_path = Path(receipt_path)
    need(receipt_path.parent.resolve() == backup_root and receipt_path.name.endswith('.receipt.json'), 'receipt_outside_private_backup_directory')
    receipt = decode(read_file(receipt_path)[0])
    backup = Path(receipt['backup'])
    need(receipt.get('target') == str(path) and backup.parent.resolve() == backup_root, 'receipt_target_mismatch')
    before, unused = read_file(backup)
    need(digest(before) == receipt['before_sha256'], 'backup_changed')
    lock_path = Path(str(path) + '.lock')
    ordinary(lock_path)
    with os.fdopen(os.open(str(lock_path), os.O_RDWR | os.O_NOFOLLOW), 'a+b') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        raw, info = read_file(path)
        need(digest(raw) == receipt['after_sha256'], 'newer_edits_prevent_rollback')
        need(info.st_uid == receipt['uid'] and info.st_gid == receipt['gid'] and stat.S_IMODE(info.st_mode) == receipt['mode'], 'changed_target_metadata')
        replace_exact(path, before, receipt['after_sha256'], info)
        need(digest(read_file(path)[0]) == receipt['before_sha256'], 'rollback_verification_failed')
    return {'result': 'rolled_back', 'writes_performed': True, 'sha256': receipt['before_sha256']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('check')
    apply_parser = sub.add_parser('apply')
    apply_parser.add_argument('--expected-sha256', required=True)
    rollback_parser = sub.add_parser('rollback')
    rollback_parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    now = dt.datetime.now(UTC)
    try:
        reviewed = fixture()
        if args.command == 'apply':
            need(re.fullmatch(r'[0-9a-f]{64}', args.expected_sha256) is not None, 'invalid_review_hash')
            report = publish(CONTENT, BACKUPS, args.expected_sha256, now, reviewed)
        elif args.command == 'rollback':
            report = rollback(CONTENT, BACKUPS, args.receipt)
        else:
            raw, unused = read_file(CONTENT)
            candidate, actions, conflicts = plan(decode(raw), reviewed, now)
            report = {'read_only': True, 'writes_performed': False, 'sha256': digest(raw),
                      'result': 'conflict' if conflicts else 'already_current' if candidate == decode(raw) else 'ready',
                      'actions': actions, 'conflicts': conflicts}
        print(json.dumps(report, indent=2))
        return 2 if report.get('conflicts') else 0
    except (Refusal, OSError, KeyError, TypeError) as error:
        print(json.dumps({'result': 'refused', 'code': str(error) if isinstance(error, Refusal) else 'host_or_package_unavailable'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
