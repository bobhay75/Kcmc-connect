#!/usr/bin/env python3
"""Real PHP8.2 compile/transaction fixtures; no app, cron, mail or private records."""
from __future__ import print_function
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import test_installer as fixture


def prepared(php, profile='pre_a7'):
    result = fixture.Fixture(profile); result.w.php82_candidates = lambda: [php]; result.w.choose_php82_cli = result.real_choose
    return result


def command(f, *args):
    code, text = f.cli(*args)
    return code, text


def require_failure(f, *args):
    code, text = command(f, *args); assert code == 1, text
    assert 'CHECK ALREADY_REPAIRED;' not in text and 'GROUP workflows REPAIRED' not in text, text
    return text


def basic(php, profile):
    f = prepared(php, profile)
    try:
        code, text = command(f, 'check'); assert code == 0 and 'CHECK READY' in text, text
        code, text = command(f, 'apply'); assert code == 0 and 'GROUP workflows REPAIRED' in text, text
        assert f.w.select(f.engines)[:2] == ('common_after', 'after')
        ids = {p: fixture.identity(f.app / p) for p in f.m.PATHS}
        code, text = command(f, 'apply'); assert code == 0 and 'both independent code groups verified' in text, text
        for p, identity in ids.items(): assert fixture.identity(f.app / p) == identity
        code, text = command(f, 'rollback', '--group', 'workflows', '--variant', profile, '--session', f.session(profile).name); assert code == 0, text
        code, text = command(f, 'rollback', '--group', 'owner', '--session', f.session('owner').name); assert code == 0, text
        for p, before in f.before.items():
            if before is None: assert not (f.app / p).exists(), p
            else: assert (f.app / p).read_bytes() == before, p
        f.preserved(); print('REAL_PHP_82 ' + profile + ' both groups/five new files/apply/common-after/no-op/exact rollback PASS')
    finally: f.close()


def uncertain_link(php):
    f = prepared(php)
    try:
        link = f.m.no_clobber_link
        def fail(*args, **kwargs): link(*args, **kwargs); raise OSError('Synthetic ambiguous new-route link')
        f.m.no_clobber_link = fail; require_failure(f, 'apply')
        value = f.m.load(f.session(f.profile)); assert value['phase'] == 'manual_review'
        path = 'admin/prayer-care.php'; assert path in value['uncertain'] and value['files'][path]['installed'] is None
        assert (f.app / path).stat().st_nlink == 2
        for p in ('lib/timeclock.php', 'lib/push-subscriptions.php'): f.m.verify_lease(p, value['files'][p]['installed'])
        f.preserved(); print('REAL_PHP_82 uncertain link/two names/no candidate-only deletion/changed providers retained PASS')
    finally: f.close()


def uncertain_consumer(php):
    f = prepared(php)
    try:
        replace = f.m.replace
        def fail(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source == 'stage-17.code': raise OSError('Synthetic ambiguous consumer rename')
            return result
        f.m.replace = fail; require_failure(f, 'apply'); value = f.m.load(f.session(f.profile))
        assert value['phase'] == 'manual_review' and 'member/index.php' in value['uncertain']
        for p in ('lib/timeclock.php', 'lib/push-subscriptions.php', 'admin/home.php'): f.m.verify_lease(p, value['files'][p]['installed'])
        f.preserved(); print('REAL_PHP_82 uncertain consumer/reverse recovery/new routes and providers retained PASS')
    finally: f.close()


def late_prerequisite(php):
    f = prepared(php)
    try:
        journal = f.m.journal
        def fail(session, value):
            result = journal(session, value)
            if value['phase'] == 'applied': f.drift_bootstrap()
            return result
        f.m.journal = fail; text = require_failure(f, 'apply'); assert 'PRIVATE_BACKUP_ROOT ' in text
        value = f.m.load(f.session(f.profile)); assert value['phase'] == 'applied'
        for p in f.m.PATHS: f.m.verify_lease(p, value['files'][p]['installed'])
        f.preserved(True); print('REAL_PHP_82 late applied-journal prerequisite drift/no success/all installed leases retained PASS')
    finally: f.close()


def rollback_prerequisite(php):
    f = prepared(php)
    try:
        code, text = command(f, 'apply'); assert code == 0, text
        unlink = f.m.unlink_name
        def fail(name, **kwargs):
            result = unlink(name, **kwargs)
            if name == 'home.php': f.drift_bootstrap()
            return result
        f.m.unlink_name = fail
        text = require_failure(f, 'rollback', '--group', 'workflows', '--variant', f.profile, '--session', f.session(f.profile).name)
        assert ' ROLLED_BACK ' not in text
        value = f.m.load(f.session(f.profile)); assert value['phase'] == 'manual_review'
        f.preserved(True); print('REAL_PHP_82 rollback prerequisite drift/uncertain deletion/manual review PASS')
    finally: f.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--php', default=shutil.which('php')); args = parser.parse_args()
    if not args.php: raise ValueError('A real PHP8.2 CLI is required')
    php = str(Path(args.php).resolve())
    original = subprocess.check_output
    def checked(argv, **kwargs):
        assert argv[0] == php and argv[1] == '-n' and (argv[2] == '-v' or argv[2] == '-l'), 'Only real PHP version/syntax probes are allowed'
        return original(argv, **kwargs)
    subprocess.check_output = checked
    try:
        for profile in fixture.derive.VARIANTS: basic(php, profile)
        uncertain_link(php); uncertain_consumer(php); late_prerequisite(php); rollback_prerequisite(php)
    finally: subprocess.check_output = original
    return 0


if __name__ == '__main__': raise SystemExit(main())
