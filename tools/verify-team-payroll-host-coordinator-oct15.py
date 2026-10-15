#!/usr/bin/env python3
"""Three real PHP8.2 composition scenarios; only version/syntax subprocesses."""
from __future__ import print_function
import argparse
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('exact_host_composition_fixtures',str(HERE/'test-team-payroll-host-coordinator-oct15.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--php',default=shutil.which('php'));args=parser.parse_args()
    if not args.php:raise ValueError('Real PHP8.2 CLI required')
    php=str(Path(args.php).resolve());real=subprocess.check_output
    version=real([php,'-n','-v'],stderr=subprocess.STDOUT,timeout=8)
    match=re.match(br'\APHP (8\.2\.[0-9]+) \(cli\)(?:\s|\Z)',version)
    if match is None:raise ValueError('Real PHP8.2 CLI required')
    def checked(command,**kwargs):
        assert command[0]==php and command[1]=='-n' and command[2] in ('-v','-l'),'Only PHP version and staged syntax probes permitted'
        return real(command,**kwargs)
    for core_before in (True,False):
        f=fixture.Fixture(core_before=core_before)
        try:
            f.phase.php=checked;f.core.choose_php82_cli=lambda:(php,match.group(1).decode('ascii'))
            f.phase.w.choose_php82_cli=lambda:(php,match.group(1).decode('ascii'))
            code,text=f.cli();assert code==0 and 'COMPLETE_REPAIRED' in text,text
            assert f.phase.m.inspect()[0]=='after';f.preserved_business()
            print('REAL_PHP_82 composition/'+('core-before' if core_before else 'core-after')+'/both complete PASS')
            if core_before:
                ids={path:fixture.phase.identity(f.phase.app/path) for path in f.phase.m.PATHS}
                code,text=f.cli();assert code==0 and 'COMPLETE_ALREADY_REPAIRED' in text,text
                for path,prior in ids.items():assert fixture.phase.identity(f.phase.app/path)==prior,path
                f.preserved_business();print('REAL_PHP_82 composition/final rerun/no core downgrade/no new code or backup PASS')
        finally:f.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
