#!/usr/bin/env python3
"""Real PHP8.2 syntax only; never execute KCMC or touch its records."""
from __future__ import print_function
import argparse
from pathlib import Path
import shutil
import subprocess
import test_installer as fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--php', default=shutil.which('php')); args = parser.parse_args()
    if not args.php: raise ValueError('A real PHP8.2 CLI is required')
    php = str(Path(args.php).resolve()); original = subprocess.check_output
    def checked(argv, **kwargs):
        assert argv[0] == php and argv[1] == '-n' and argv[2] in ('-v', '-l'), 'Only version and staged syntax probes allowed'
        if argv[2] == '-l': assert Path(argv[3]).name in ('stage-2.code','stage-3.code','stage-4.code','stage-5.code'), 'Application execution forbidden'
        return original(argv, **kwargs)
    subprocess.check_output = checked
    try:
        for variant,mode in ((variant,mode) for variant in ('main','livecalendar') for mode in (0o644,0o664)):
            f = fixture.Fixture(mode=mode,variant=variant)
            try:
                f.w.php82_candidates = lambda: [php]; f.w.choose_php82_cli = f.real_choose
                code, text = f.cli('check'); assert code == 0 and 'CHECK READY' in text, text
                code, text = f.cli('apply'); assert code == 0 and 'REPAIRED sw.js, member/push-settings.js, member/notifications.php, admin/push.php, index.php, admin/operations.php' in text, text
                assert f.m.inspect()[0] == 'after'
                before = fixture.identity(f.app / 'member/notifications.php')
                code, text = f.cli('apply'); assert code == 0 and 'no replacement' in text, text
                assert before == fixture.identity(f.app / 'member/notifications.php')
                code, text = f.cli('rollback', '--session', f.session().name); assert code == 0, text
                assert (f.app / 'member/notifications.php').read_bytes() == f.before['member/notifications.php']
                assert (f.app / 'member/notifications.php').stat().st_mode & 0o777 == mode
                f.preserved()
                print('REAL_PHP_82 follow-up variant=' + variant + ' mode=' + format(mode, '04o') + ' staged/apply/no-op/rollback PASS')
            finally: f.close()
    finally: subprocess.check_output = original
    return 0


if __name__ == '__main__': raise SystemExit(main())
