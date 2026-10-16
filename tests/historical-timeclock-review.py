#!/usr/bin/env python3
"""Retain the previous approval-service contract on its exact reviewed source.

Current manual time has its own no-approval contract. This reconstructs the
complete pinned themed application in a temporary directory, then runs every
unchanged historical review case with that historical library and synthetic
private data. It never deploys code or reads production records.
"""
import os
from pathlib import Path
import subprocess
import tempfile

from manual_clock_source_layer import ManualClockLayer, ROOT


def main():
    layer = ManualClockLayer(ROOT)
    with tempfile.TemporaryDirectory(prefix='kcmc-historical-timeclock-review-') as temporary:
        app = layer.copy_baseline(Path(temporary) / 'app')
        print('PASS: exact reviewed themed application recovered for historical approval-service coverage', flush=True)
        subprocess.run([
            os.environ.get('PHP_BINARY', 'php'),
            str(ROOT / 'tests/timeclock-own-review-contract.php'),
            str(app / 'lib/timeclock.php'),
            'all',
        ], check=True)


if __name__ == '__main__':
    main()
