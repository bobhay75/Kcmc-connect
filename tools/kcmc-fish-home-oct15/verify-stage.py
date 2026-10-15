#!/usr/bin/env python3
"""Real PHP 8.2 syntax-only staging for both temporary-copy variants."""
from __future__ import print_function
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile

HERE=Path(__file__).resolve().parent
def sha(data):
    return hashlib.sha256(data).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--php',default=shutil.which('php'),help='Test-only PHP 8.2 CLI; production installer path stays fixed')
    args=parser.parse_args()
    if not args.php:raise ValueError('PHP CLI needed for staging validation')
    spec=importlib.util.spec_from_file_location('stage_fish_installer',str(HERE/'installer.py'))
    wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
    # This override exists only in the temporary validation helper. The published
    # installer's argument parser has no runtime override, and its own version
    # validation is exercised here against the actual test CLI before staging.
    wrapper.php82_candidates=lambda:[str(Path(args.php).resolve())]
    selected_php,selected_version=wrapper.choose_php82_cli()
    print('REAL_PHP_CLI_SELECTION '+selected_php+' PHP '+selected_version+' PASS')
    for variant in wrapper.VARIANTS:
        with tempfile.TemporaryDirectory(prefix='kcmc-fish-real-php-') as temporary:
            root=Path(temporary);app=root/'app';app.mkdir();engines=wrapper.load_engines()
            for name,m in engines.items():
                m.APP=app;m.BACKUPS=root/('private-'+name);m.UID=os.getuid();m.GID=os.getgid();m.PHP=selected_php
            m=engines[variant];originals={}
            for path in m.PATHS:
                originals[path]=(HERE/'evidence'/variant/path).read_bytes();(app/path).write_bytes(originals[path]);(app/path).chmod(0o644)
            (app/'public-presentation.css').chmod(0o664)
            (app/'data').mkdir();private=app/'data/content.json';private.write_bytes(b'{"synthetic":"owner records preserved"}');private.chmod(0o600)
            private_id=private.stat()
            selected,state,unused=wrapper.select(engines)
            assert selected==variant and state=='before'
            session=m.apply();assert session is not None
            for path in m.PATHS:assert sha((app/path).read_bytes())==m.FILES[path]['after_sha256']
            identities={path:(app/path).stat() for path in m.PATHS}
            assert m.apply() is None
            for path,old in identities.items():
                new=(app/path).stat();assert (old.st_ino,old.st_mtime_ns,old.st_ctime_ns)==(new.st_ino,new.st_mtime_ns,new.st_ctime_ns)
            m.rollback(session.name)
            for path,data in originals.items():assert (app/path).read_bytes()==data
            assert (app/'public-presentation.css').stat().st_mode & 0o777 == 0o664
            now=private.stat();assert (now.st_ino,now.st_mtime_ns,now.st_ctime_ns)==(private_id.st_ino,private_id.st_mtime_ns,private_id.st_ctime_ns)
            print('REAL_PHP_82 '+variant+' exact stage/apply/no-op/rollback/private preservation PASS')
    return 0
if __name__=='__main__':
    raise SystemExit(main())
