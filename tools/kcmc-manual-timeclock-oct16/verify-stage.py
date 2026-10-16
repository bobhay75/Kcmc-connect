#!/usr/bin/env python3
"""Real PHP8.2 version and staged syntax only; temporary code transactions."""
from __future__ import print_function
import argparse
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import test_installer as fixture


def prepared(php, variant, image='before'):
    f = fixture.Fixture(variant, image)
    f.w.php82_candidates = f.theme.php82_candidates = lambda: [php]
    f.w.choose_php82_cli = f.theme.choose_php82_cli = f.real_choose
    return f


def basic(php, variant):
    f = prepared(php, variant)
    try:
        code, text = f.cli('check'); assert code == 0 and 'CHECK READY' in text, text
        code, text = f.cli('apply'); assert code == 0 and 'REPAIRED lib/timeclock.php' in text, text
        assert f.m.inspect()[0] == 'after'
        prior = {path: fixture.identity(f.app / path) for path in f.m.PATHS}
        code, text = f.cli('apply'); assert code == 0 and 'no replacement' in text, text
        assert prior == {path: fixture.identity(f.app / path) for path in f.m.PATHS}
        code, text = f.cli('rollback', '--session', f.session().name); assert code == 0, text
        for path, content in f.before.items(): assert (f.app / path).read_bytes() == content, path
        f.preserved()
        print('REAL_PHP_82 ' + variant + ' five staged files/apply/no-op/rollback PASS')
    finally: f.close()


def coordinated(php, variant):
    f = prepared(php, variant, 'pretheme')
    try:
        output = io.StringIO()
        with contextlib.redirect_stdout(output): f.c.coordinate(f.theme, f.w)
        assert 'COMPLETE_REPAIRED' in output.getvalue(), output.getvalue()
        assert f.m.inspect()[0] == 'after'; f.preserved(check_guards=False)
        snapshot = {p: fixture.identity(f.app / p) for p in f.m.PATHS + tuple(f.guards)}
        # An obsolete theme install must never run after final manual changes.
        def refused(): raise AssertionError('Obsolete theme main was invoked')
        f.theme.main = refused
        output = io.StringIO()
        with contextlib.redirect_stdout(output): f.c.coordinate(f.theme, f.w)
        assert 'obsolete theme installer skipped' in output.getvalue(), output.getvalue()
        assert snapshot == {p: fixture.identity(f.app / p) for p in snapshot}
        print('REAL_PHP_82 ' + variant + ' pre-theme through manual + final rerun PASS')
    finally: f.close()


def late_guard(php):
    f = prepared(php, 'livecalendar')
    try:
        journal = f.m.journal
        def changed(session, value):
            result = journal(session, value)
            if value['phase'] == 'applied': f.foreign('lib/screen-navigation.php')
            return result
        f.m.journal = changed
        code, text = f.cli('apply'); assert code == 1 and 'CHECK ALREADY_REPAIRED' not in text, text
        assert f.m.load(f.session())['phase'] == 'applied'; f.preserved(except_guard='lib/screen-navigation.php')
        print('REAL_PHP_82 late same-byte theme dependency replacement refuses success PASS')
    finally: f.close()


def uncertain_consumer(php):
    f = prepared(php, 'livecalendar')
    try:
        replace = f.m.replace
        def interrupted(source, target, **kwargs):
            result = replace(source, target, **kwargs)
            if source == 'stage-1.code': raise OSError('Synthetic uncertain member screen publication')
            return result
        f.m.replace = interrupted
        code, text = f.cli('apply'); assert code == 1 and 'CHECK ALREADY_REPAIRED' not in text, text
        value = f.m.load(f.session()); assert value['phase'] == 'manual_review'
        assert 'member/timeclock.php' in value['uncertain']
        assert value['files']['lib/timeclock.php']['installed'] is not None
        assert (f.app / 'lib/timeclock.php').read_bytes() == f.after['lib/timeclock.php']
        f.preserved()
        print('REAL_PHP_82 ambiguous retained consumer keeps required existing library PASS')
    finally: f.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--php', default=shutil.which('php')); args = parser.parse_args()
    if not args.php: raise ValueError('A real PHP8.2 CLI is required')
    php = str(Path(args.php).resolve()); original = subprocess.check_output
    def checked(argv, **kwargs):
        assert argv[0] == php and argv[1] == '-n' and argv[2] in ('-v', '-l'), 'Only version and staged syntax probes allowed'
        if argv[2] == '-l': assert Path(argv[3]).name.startswith('stage-'), 'Application execution forbidden'
        return original(argv, **kwargs)
    subprocess.check_output = checked
    try:
        basic(php, 'main'); basic(php, 'livecalendar')
        coordinated(php, 'main'); coordinated(php, 'livecalendar'); late_guard(php); uncertain_consumer(php)
    finally: subprocess.check_output = original
    return 0


if __name__ == '__main__': raise SystemExit(main())
