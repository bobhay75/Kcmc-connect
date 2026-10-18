#!/usr/bin/env python3
"""Plan/install one store-bound payroll cron block; never run payroll or send mail."""
from __future__ import print_function

import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import uuid

APP = Path('/home/bobsome1/public_html/kcmc-connect')
PHP = Path('/opt/alt/php82/usr/bin/php')
BACKUPS = Path('/home/bobsome1/kcmc-payroll-schedule-backups')
UID, GID = 2162, 2147
SOURCE = '4b108316a3865dba8583b30ec0dd8e2eeae6968e'
GUARDS = {
    'admin/timeclock-period-close.php': 'a08b53f82e710a0bef88d1de75928bccab5e239f84085e482c2b9ba8d0cae5dc',
    'lib/payroll.php': 'cf51ec5abb06d91aa7c6a97525554771a5661eccc4bc69c1ed2aea102aa35874',
    'lib/timeclock.php': '261a911a191ec2b4413226b655162cee1855f81a86de36b7cf1faf11163317c9',
    'lib/bootstrap.php': '19a932424250b6bc33a5e844bfb942fb33a8194aa8bf912bf4494f1e27ba354e',
    'lib/post-controls.php': '5eaaf0e01cd3c7880a898eafd7979321f779ee808d007cabf5880d5b43b86fba',
}
BEGIN = b'# BEGIN KCMC PAYROLL PERIOD CLOSE v1'
END = b'# END KCMC PAYROLL PERIOD CLOSE v1'
TOKEN = b'KCMC PAYROLL PERIOD CLOSE'
MAX_CRON = 1024 * 1024
MAX_JSON = 2 * 1024 * 1024


class Refusal(Exception):
    pass


def require(ok, reason):
    if not ok:
        raise Refusal(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def walk(path, final_uid=None, private=False):
    require(path.is_absolute() and '..' not in path.parts, 'An absolute ordinary path is required')
    current = Path('/')
    for piece in path.parts[1:]:
        current = current / piece
        info = current.lstat()
        require(stat.S_ISDIR(info.st_mode), 'Directory symlinks and non-directories are refused')
    info = path.lstat()
    if final_uid is not None:
        require(info.st_uid == final_uid, 'Directory ownership requires review')
    if private:
        require(stat.S_IMODE(info.st_mode) == 0o700, 'Installer storage must have mode0700')
    return info


def read_file(path, maximum=MAX_JSON, absent=False, code=False, modes=None):
    """No-follow reads; detect replacement during the read and never chmod stores."""
    try:
        before = path.lstat()
    except FileNotFoundError:
        if absent:
            return None
        raise Refusal('A required ordinary file is unavailable')
    allowed_modes = modes or ((0o644, 0o664) if code else (0o600, 0o640, 0o644))
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == UID
            and before.st_gid == GID and stat.S_IMODE(before.st_mode) in allowed_modes
            and before.st_size <= maximum, 'File metadata requires review')
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'File changed before read')
        with os.fdopen(fd, 'rb', closefd=False) as handle:
            raw = handle.read(maximum + 1)
        after = os.fstat(fd)
        require(len(raw) <= maximum and (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
                == (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'File changed during read')
        final = path.lstat()
        require((final.st_dev, final.st_ino, final.st_mtime_ns, final.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns), 'File replaced during read')
        return raw
    finally:
        os.close(fd)


def load_json(raw, label):
    try:
        result = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError, AttributeError):
        raise Refusal(label + ' requires review')
    require(isinstance(result, dict), label + ' requires review')
    return result


def installer_file(path, maximum=MAX_JSON):
    require(stat.S_IMODE(path.lstat().st_mode) == 0o600, 'Installer files must have mode0600')
    return read_file(path, maximum)


def quote(argument):
    require(isinstance(argument, str) and not re.search(r'[\r\n\x00]', argument), 'Unsupported command argument')
    return "'" + argument.replace("'", "'\"'\"'") + "'"


def cron_line(private, fingerprint):
    require(re.search(r'[\r\n\x00\\]', str(private)) is None,
            'Private directory contains unsupported crontab path characters')
    line = ('*/15 * * * * umask 077 && KCMC_PRIVATE_DATA_DIR=' + quote(str(private)) + ' '
            + quote(str(PHP)) + ' -n ' + quote(str(APP / 'admin/timeclock-period-close.php'))
            + ' --run --expect-store ' + quote(fingerprint) + ' >> '
            + quote(str(private / 'payroll-cron.log')) + ' 2>&1')
    return line.replace('%', '\\%').encode('utf-8')


def replace_block(raw, block):
    require(len(raw) <= MAX_CRON and b'\x00' not in raw, 'Crontab is too large or invalid')
    lines = raw.splitlines(True)
    markers = [(index, line.rstrip(b'\r\n')) for index, line in enumerate(lines) if TOKEN in line]
    if not markers:
        verify_cron_shell(lines)
        return raw + (b'\n' if raw and not raw.endswith(b'\n') else b'') + block, 'absent'
    require(len(markers) == 2 and markers[0][1] == BEGIN and markers[1][1] == END
            and markers[0][0] < markers[1][0], 'Duplicate or malformed managed cron blocks require review')
    first, last = markers[0][0], markers[1][0]
    require(last == first + 2 and lines[first + 1].startswith(b'*/15 * * * * '),
            'The existing managed block must contain only its one scheduled command')
    verify_cron_shell(lines[:first])
    existing = b''.join(lines[first:last + 1])
    return b''.join(lines[:first]) + block + b''.join(lines[last + 1:]), 'matching' if existing == block else 'different'


def verify_cron_shell(lines):
    # Do not change SHELL inside the managed block: that would also affect jobs
    # after it. Refuse an incompatible inherited shell rather than install a job
    # whose POSIX assignment/redirection syntax may fail.
    shell = b'/bin/sh'
    for line in lines:
        match = re.match(br'^\s*SHELL\s*=\s*(.*?)\s*$', line.rstrip(b'\r\n'))
        if match:
            shell = match.group(1)
            if len(shell) >= 2 and shell[:1] == shell[-1:] and shell[:1] in (b'"', b"'"):
                shell = shell[1:-1]
    require(shell in (b'/bin/sh', b'/bin/bash', b'/bin/dash'), 'The inherited cron shell requires review; no job or shell setting changed')


def run(arguments, env=None):
    try:
        return subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=20, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal('An operator command could not be completed; raw output withheld')


def crontab_executable():
    for name in ('/usr/bin/crontab', '/bin/crontab'):
        path = Path(name)
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022 and os.access(name, os.X_OK):
            return name
    raise Refusal('A standard root-owned crontab executable is required')


def cron_command(arguments):
    env = dict(os.environ, LC_ALL='C', LANG='C')
    return run([crontab_executable()] + arguments, env=env)


def read_crontab():
    result = cron_command(['-l'])
    if result.returncode == 0:
        require(not result.stderr and len(result.stdout) <= MAX_CRON, 'Unexpected crontab read response')
        return True, result.stdout
    username = pwd.getpwuid(UID).pw_name
    expected = ('no crontab for ' + username + '\n').encode('utf-8')
    require(result.returncode == 1 and result.stdout == b'' and result.stderr == expected,
            'Crontab read failed; it is not treated as an absent crontab')
    return False, b''


def verify_php_metadata():
    php_info = PHP.lstat()
    require(stat.S_ISREG(php_info.st_mode) and php_info.st_uid == 0 and not php_info.st_mode & 0o022
            and os.access(str(PHP), os.X_OK), 'An ordinary trusted PHP8.2 CLI is required')


def verify_code(private, expected):
    require(os.getuid() == UID and os.getgid() == GID, 'Run this tool as the reviewed hosting account')
    require(re.search(r'[\r\n\x00\\]', str(private)) is None,
            'Private directory contains unsupported crontab path characters')
    require(re.match(r'\A[a-f0-9]{64}\Z', expected) is not None, 'A web-reviewed store fingerprint is required')
    walk(APP, UID)
    for name, wanted in GUARDS.items():
        walk((APP / name).parent)
        require(digest(read_file(APP / name, code=True)) == wanted, 'The reviewed payroll runtime differs')
    walk(private, UID)
    verify_php_metadata()
    version = run([str(PHP), '-n', '-v'])
    require(version.returncode == 0 and re.match(br'PHP 8\.2\.\d+ \(cli\)', version.stdout) is not None,
            'The selected CLI is not PHP8.2')
    env = dict(os.environ, KCMC_PRIVATE_DATA_DIR=str(private))
    result = run([str(PHP), '-n', str(APP / 'admin/timeclock-period-close.php'), '--diagnose'], env=env)
    require(result.returncode == 0 and not result.stderr, 'Reviewed runner diagnosis failed; raw output withheld')
    identity = load_json(result.stdout, 'Runner identity')
    require(identity.get('private_directory') == str(private) and identity.get('timeclock_path') == str(private / 'timeclock.json')
            and identity.get('directory_mode') == '0750' and identity.get('fingerprint') == expected,
            'CLI diagnosis does not match the owner-reviewed web store')
    return identity


def valid_email(address):
    return isinstance(address, str) and len(address) <= 254 and re.match(r'\A[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}\Z', address) is not None


def inspect(private, expected):
    identity = verify_code(private, expected)
    directory_before = private.stat()
    settings_raw = read_file(private / 'payroll-settings.json', absent=True)
    settings = load_json(settings_raw, 'Payroll settings') if settings_raw is not None else {}
    users_raw = read_file(private / 'users.json')
    users = load_json(users_raw, 'Account selection').get('users')
    require(isinstance(users, list), 'Account selection requires review')
    channel, recipient_id = settings.get('channel', 'off'), settings.get('reviewer_id', '')
    require(channel in ('off', 'queue', 'email') and isinstance(recipient_id, str), 'Payroll settings require review')
    selected = [user for user in users if isinstance(user, dict) and user.get('id') == recipient_id]
    require(len(selected) <= 1, 'Duplicate recipient identity requires review')
    recipient = selected[0] if selected and selected[0].get('active') is True else None
    config_raw = read_file(APP / 'config.php', maximum=128 * 1024, absent=True, modes=(0o600, 0o640, 0o644, 0o664))
    sender_status = 'not_verified_preserved_config_not_executed'
    reasons = []
    if channel == 'off':
        reasons.append('Choose a delivery channel in owner payroll setup')
    if recipient is None or not recipient_id:
        reasons.append('Select an existing active recipient in owner payroll setup')
    if channel == 'email':
        if recipient is not None and not valid_email(recipient.get('email')):
            reasons.append('The selected recipient email requires review')
        date = settings.get('email_activation_date', '')
        try:
            require(re.match(r'\A\d{4}-\d{2}-\d{2}\Z', date) is not None
                    and datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m-%d') == date,
                    'Email activation date requires owner setup')
        except (ValueError, TypeError, Refusal):
            reasons.append('Save owner payroll setup to establish a valid email activation date')
        url = settings.get('review_url', '')
        if url != 'https://bobsome1.com/kcmc-connect/admin/timecards.php':
            reasons.append('Owner payroll setup must use the reviewed private time-card URL')
        reasons.append('Email scheduling requires separately verified current CLI sender readiness; this queue-only installer does not execute preserved config')
    exists, original = read_crontab()
    block = BEGIN + b'\n' + cron_line(private, expected) + b'\n' + END + b'\n'
    planned, managed = replace_block(original, block)
    require(len(planned) <= MAX_CRON, 'Planned crontab exceeds the reviewed bound')
    plan = {'version': 1, 'source_commit': SOURCE, 'store_fingerprint': expected, 'private_directory': str(private),
            'app': str(APP), 'php': str(PHP), 'guards': GUARDS, 'settings_sha256': digest(settings_raw) if settings_raw is not None else None,
            'users_sha256': digest(users_raw), 'config_sha256': digest(config_raw) if config_raw is not None else None,
            'channel': channel, 'recipient_id': recipient_id,
            'crontab_existed': exists, 'crontab_sha256': digest(original), 'planned_sha256': digest(planned)}
    receipt_raw = read_file(private / 'payroll-run-status.json', absent=True)
    receipt = load_json(receipt_raw, 'Runner receipt') if receipt_raw is not None else {}
    finished = receipt.get('finished_at')
    if not isinstance(finished, str) or re.match(r'\A\d{4}-\d{2}-\d{2}T[0-9:+Z-]{8,20}\Z', finished) is None:
        finished = None
    status = {'plan_sha256': digest(canonical(plan)), 'can_apply': not reasons, 'needs': reasons,
              'recipient_selected': recipient is not None and bool(recipient_id), 'recipient_id': recipient_id,
              'channel': channel, 'sender_readiness': sender_status,
              'store_matches_web': True, 'managed_block': managed, 'runner_finished_at': finished,
              'runner_receipt_matches_store': receipt.get('store_fingerprint') == expected,
              'schedule_execution_verified': False, 'crontab_existed': exists,
              'crontab_sha256': digest(original), 'planned_sha256': digest(planned),
              'managed_command': cron_line(private, expected).decode('utf-8')}
    directory_after = walk(private, UID)
    require((directory_before.st_dev, directory_before.st_ino, directory_before.st_mode, directory_before.st_uid, directory_before.st_gid)
            == (directory_after.st_dev, directory_after.st_ino, directory_after.st_mode, directory_after.st_uid, directory_after.st_gid),
            'Private-store directory changed during inspection')
    if BACKUPS.exists() or BACKUPS.is_symlink():
        walk(BACKUPS, UID, private=True)
        status['unfinished_installations'] = unfinished_sessions()
    else:
        status['unfinished_installations'] = []
    return {'plan': plan, 'status': status, 'original': original, 'planned': planned, 'identity': identity}


def write_new(path, raw):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def sync_directory(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save_journal(session, value):
    staged = session / ('journal-' + uuid.uuid4().hex + '.tmp')
    write_new(staged, canonical(value) + b'\n')
    os.replace(str(staged), str(session / 'journal.json'))
    sync_directory(session)


@contextlib.contextmanager
def locked():
    walk(BACKUPS.parent, UID)
    try:
        BACKUPS.mkdir(mode=0o700)
        sync_directory(BACKUPS.parent)
    except FileExistsError:
        pass
    walk(BACKUPS, UID, private=True)
    lock = BACKUPS / 'schedule.lock'
    try:
        write_new(lock, b'')
    except FileExistsError:
        pass
    installer_file(lock)
    fd = os.open(str(lock), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refusal('Another schedule installer owns the private lock')
        yield
    finally:
        os.close(fd)


def unfinished_sessions():
    found = []
    for session in sorted(BACKUPS.glob('schedule-*')):
        walk(session, UID, private=True)
        journal = load_json(installer_file(session / 'journal.json'), 'Schedule journal')
        if journal.get('phase') not in ('applied', 'rolled_back'):
            found.append(session.name)
    return found


def apply(private, expected, recipient, expected_plan):
    probe = inspect(private, expected)
    require(probe['status']['can_apply'], 'Payroll setup or email-delivery verification is incomplete')
    require(recipient and probe['plan']['recipient_id'] == recipient, 'Owner-reviewed recipient does not match setup')
    require(expected_plan == probe['status']['plan_sha256'], 'The reviewed plan changed; prepare a fresh plan')
    with locked():
        require(not unfinished_sessions(), 'An unfinished schedule journal requires private review')
        current = inspect(private, expected)
        require(current['status']['plan_sha256'] == expected_plan, 'The plan changed before installation')
        if current['original'] == current['planned'] and current['plan']['crontab_existed']:
            return {'result': 'ALREADY_INSTALLED', 'plan_sha256': expected_plan, 'no_new_backup': True}
        session = BACKUPS / ('schedule-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex)
        session.mkdir(mode=0o700)
        sync_directory(BACKUPS)
        write_new(session / 'before.crontab', current['original'])
        write_new(session / 'planned.crontab', current['planned'])
        journal = {'version': 1, 'phase': 'prepared', 'plan': current['plan'], 'plan_sha256': expected_plan,
                   'before_sha256': digest(current['original']), 'planned_sha256': digest(current['planned'])}
        save_journal(session, journal)
        # Re-read after staging, immediately before installation. The private lock does
        # not lock cPanel editors; exact readback and conflict preservation still matter.
        fresh = inspect(private, expected)
        if fresh['status']['plan_sha256'] != expected_plan:
            journal['phase'] = 'conflict_before_install'
            save_journal(session, journal)
            raise Refusal('Concurrent settings or crontab edit preserved; private journal: ' + str(session))
        journal['phase'] = 'installing'
        save_journal(session, journal)
        # The durable intent write is itself an I/O window. Bindings and the
        # real crontab are checked again after it, immediately before replace.
        try:
            final = inspect(private, expected)
            require(final['status']['plan_sha256'] == expected_plan, 'Plan changed after the intent journal')
            exists, observed = read_crontab()
            require(exists == current['plan']['crontab_existed'] and observed == current['original'],
                    'Crontab changed after the intent journal')
        except Refusal:
            journal['phase'] = 'conflict_before_install'
            save_journal(session, journal)
            raise Refusal('Final preinstall review stopped; later jobs/settings preserved; private journal: ' + str(session))
        try:
            result = cron_command([str(session / 'planned.crontab')])
            exists, observed = read_crontab()
            require(result.returncode == 0 and result.stdout == b'' and result.stderr == b''
                    and exists and observed == current['planned'], 'Schedule installation/readback is uncertain')
        except Refusal:
            journal['phase'] = 'uncertain'
            save_journal(session, journal)
            raise Refusal('Schedule installation/readback is uncertain; no automatic restore; private journal: ' + str(session))
        journal['phase'] = 'applied'
        save_journal(session, journal)
        return {'result': 'INSTALLED_NOT_RUN', 'session': session.name, 'private_backup': str(session),
                'installed_sha256': digest(current['planned']), 'schedule_execution_verified': False}


def rollback(session_name):
    require(re.match(r'\Aschedule-\d{8}T\d{6}Z-[a-f0-9]{32}\Z', session_name) is not None,
            'Use an exact private schedule session basename')
    require(os.getuid() == UID and os.getgid() == GID, 'Run this tool as the reviewed hosting account')
    with locked():
        session = BACKUPS / session_name
        walk(session, UID, private=True)
        journal = load_json(installer_file(session / 'journal.json'), 'Schedule journal')
        require(journal.get('version') == 1 and journal.get('phase') == 'applied', 'Only a verified applied schedule can roll back automatically')
        original = installer_file(session / 'before.crontab', MAX_CRON)
        planned = installer_file(session / 'planned.crontab', MAX_CRON)
        require(digest(original) == journal.get('before_sha256') and digest(planned) == journal.get('planned_sha256')
                and journal.get('plan_sha256') == digest(canonical(journal.get('plan'))), 'Private schedule backup requires review')
        exists, current = read_crontab()
        require(exists and current == planned, 'Crontab changed after installation; later edits were preserved')
        existed = journal['plan'].get('crontab_existed')
        require(type(existed) is bool, 'Original crontab existence requires review')
        journal['phase'] = 'rolling_back'
        save_journal(session, journal)
        # Check again after the journal write; still no global lock against editors.
        exists, current = read_crontab()
        if not exists or current != planned:
            journal['phase'] = 'rollback_conflict'
            save_journal(session, journal)
            raise Refusal('Concurrent crontab edit preserved; rollback stopped')
        try:
            result = cron_command([str(session / 'before.crontab')] if existed else ['-r'])
            now_exists, observed = read_crontab()
            require(result.returncode == 0 and not result.stdout and not result.stderr
                    and now_exists == existed and observed == original, 'Rollback readback is uncertain')
        except Refusal:
            journal['phase'] = 'rollback_uncertain'
            save_journal(session, journal)
            raise Refusal('Rollback result is uncertain; private journal retained; no further restore attempted')
        journal['phase'] = 'rolled_back'
        save_journal(session, journal)
        return {'result': 'ROLLED_BACK', 'session': session_name, 'crontab_existed': existed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('status', 'check', 'plan', 'apply', 'rollback'))
    parser.add_argument('--private-directory')
    parser.add_argument('--expect-store')
    parser.add_argument('--expect-recipient')
    parser.add_argument('--expect-plan')
    parser.add_argument('--session')
    args = parser.parse_args(argv)
    try:
        if args.mode == 'rollback':
            require(bool(args.session), 'Rollback requires --session')
            output = rollback(args.session)
        else:
            require(bool(args.private_directory) and bool(args.expect_store), 'Use the web-reviewed private directory and store fingerprint')
            private = Path(args.private_directory)
            if args.mode == 'apply':
                require(bool(args.expect_recipient) and bool(args.expect_plan), 'Apply requires the exact owner-reviewed recipient and plan digest')
                output = apply(private, args.expect_store, args.expect_recipient, args.expect_plan)
            else:
                output = inspect(private, args.expect_store)['status']
                output['result'] = 'READ_ONLY_' + args.mode.upper()
        print(json.dumps(output, sort_keys=True))
        return 0
    except (Refusal, OSError) as error:
        reason = str(error) if isinstance(error, Refusal) else 'Filesystem operation stopped; raw paths/errors withheld'
        print(json.dumps({'result': 'REFUSED', 'reason': reason}, sort_keys=True))
        return 1


if __name__ == '__main__':
    sys.exit(main())
