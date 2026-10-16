#!/usr/bin/env python3
"""Real PHP8.2 staged syntax and temporary transactions; no app execution."""
from __future__ import print_function
import argparse
from pathlib import Path
import shutil
import subprocess
import test_installer as fixture


def prepared(php, variant):
    f = fixture.Fixture(variant); f.w.php82_candidates = lambda: [php]; f.w.choose_php82_cli = f.real_choose
    return f


def basic(php, variant):
    f = prepared(php, variant)
    try:
        code, text = f.cli('check'); assert code == 0 and 'CHECK READY' in text, text
        code, text = f.cli('apply'); assert code == 0 and 'REPAIRED app-theme.css' in text, text
        assert f.m.inspect()[0] == 'after'
        for path, content in f.after.items(): assert (f.app / path).read_bytes() == content, path
        assert (f.session() / 'journal.json').stat().st_size < f.m.MAX_BYTES
        prior = {path: fixture.identity(f.app / path) for path in f.m.PATHS}
        code, text = f.cli('apply'); assert code == 0 and 'ALREADY_REPAIRED; no replacement' in text, text
        for path, identity in prior.items(): assert fixture.identity(f.app / path) == identity, path
        code, text = f.cli('rollback', '--session', f.session().name); assert code == 0, text
        f.assert_before(); f.preserved()
        print('REAL_PHP_82 ' + variant + ' exact provider-first bundle/staged syntax/no-op/reverse rollback PASS')
    finally: f.close()


def ambiguous_consumer(php):
    f = prepared(php, 'livecalendar')
    try:
        replace = f.m.replace; index = f.m.PATHS.index('index.php')
        def failed(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source == 'stage-' + str(index) + '.code': raise OSError('Synthetic ambiguous homepage replacement')
            return result
        f.m.replace = failed
        code, text = f.cli('apply'); assert code == 1 and 'REPAIRED ' not in text, text
        value = f.journal(); assert value['phase'] == 'manual_review' and 'index.php' in value['uncertain']
        for provider in fixture.derive.PROVIDERS:
            assert value['files'][provider]['installed'] is not None, provider
            f.m.verify_lease(provider, value['files'][provider]['installed'])
        f.preserved()
        print('REAL_PHP_82 ambiguous homepage consumer/new providers retained/manual review PASS')
    finally: f.close()


def recreated_consumer(php):
    f = prepared(php, 'livecalendar')
    try:
        code, text = f.cli('apply'); assert code == 0, text
        journal = f.m.journal; changed = [False]; path = 'member/timeclock.php'
        def recreated(session, value):
            result = journal(session, value)
            if value['phase'] == 'rolling_back' and value['files'][path]['installed'] is None and value['intent'] is None and not changed[0]:
                changed[0] = True; f.foreign(path, f.after[path])
            return result
        f.m.journal = recreated
        code, text = f.cli('rollback', '--session', f.session().name); assert code == 1 and 'ROLLED_BACK ' not in text, text
        value = f.journal(); assert changed[0] and value['phase'] == 'manual_review' and path in value['uncertain']
        for provider in fixture.derive.PROVIDERS: assert value['files'][provider]['installed'] is not None, provider
        f.preserved()
        print('REAL_PHP_82 restored consumer recreation/providers retained/manual review PASS')
    finally: f.close()


def late_public_guard(php):
    f = prepared(php, 'livecalendar')
    try:
        journal = f.m.journal; path = 'public-presentation.css'
        def changed(session, value):
            result = journal(session, value)
            if value['phase'] == 'applied': f.foreign(path)
            return result
        f.m.journal = changed
        code, text = f.cli('apply'); assert code == 1 and 'CHECK ALREADY_REPAIRED' not in text, text
        assert f.journal()['phase'] == 'applied'; f.preserved(path)
        print('REAL_PHP_82 late same-byte public stylesheet replacement/final lease refuses success PASS')
    finally: f.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--php', default=shutil.which('php')); args = parser.parse_args()
    if not args.php: raise ValueError('A real PHP8.2 CLI is required')
    php = str(Path(args.php).resolve()); original = subprocess.check_output
    def checked(argv, **kwargs):
        assert argv[0] == php and argv[1] == '-n' and argv[2] in ('-v', '-l'), 'Only PHP version and staged syntax probes allowed'
        return original(argv, **kwargs)
    subprocess.check_output = checked
    try:
        basic(php, 'main'); basic(php, 'livecalendar'); ambiguous_consumer(php); recreated_consumer(php); late_public_guard(php)
    finally: subprocess.check_output = original
    return 0


if __name__ == '__main__': raise SystemExit(main())
