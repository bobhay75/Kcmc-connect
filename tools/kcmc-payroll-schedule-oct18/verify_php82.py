#!/usr/bin/env python3
"""Real PHP8.2 --diagnose on synthetic records; executable fake cron only."""
from __future__ import print_function
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import test_schedule as tests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--php', default=shutil.which('php'))
    args = parser.parse_args()
    if not args.php:
        raise RuntimeError('A real root-owned PHP8.2 CLI is required')
    f = tests.Fixture(real_php=args.php)
    original_run = tests.M.run
    try:
        def observed(arguments, env=None):
            if arguments[0] == str(f.php):
                assert arguments == [str(f.php), '-n', '-v'] or arguments == [
                    str(f.php), '-n', str(f.app / 'admin/timeclock-period-close.php'), '--diagnose'], arguments
            else:
                assert arguments[0] == str(f.cron), arguments
            return original_run(arguments, env=env)
        tests.M.run = observed
        before = f.snapshot()
        plan = f.plan()
        assert plan['identity'] == tests.identity(f.private)
        assert before == f.snapshot() and not f.config_sentinel.exists() and not f.backups.exists()
        installed = f.apply(plan)
        assert installed['result'] == 'INSTALLED_NOT_RUN'
        assert f.apply()['result'] == 'ALREADY_INSTALLED'
        assert tests.M.rollback(installed['session'])['result'] == 'ROLLED_BACK'
        assert before == f.snapshot() and not f.config_sentinel.exists()
        # This separate synthetic-only assertion checks parity with the app's own
        # command builder. Production schedule.py executes only --diagnose and -v.
        php = "require $argv[1].'/lib/payroll.php'; echo kcmc_payroll_cron_line($argv[2]);"
        result = subprocess.run([str(f.php), '-n', '-r', php, str(f.app), str(f.php)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=dict(tests.os.environ, KCMC_PRIVATE_DATA_DIR=str(f.private)))
        assert result.returncode == 0 and result.stderr == b'', result.stderr
        assert result.stdout == tests.M.cron_line(f.private, f.expected)
        assert before == f.snapshot() and not f.config_sentinel.exists()
        print('REAL_PHP82 verified: read-only diagnosis, source command parity, queue-only apply/no-op/rollback against executable fake cron; config and records unchanged')
    finally:
        tests.M.run = original_run
        f.close()


if __name__ == '__main__': main()
