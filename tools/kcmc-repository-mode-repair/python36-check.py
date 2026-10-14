#!/usr/bin/env python3
"""Exercise portable metadata APIs in isolated synthetic temporary files only."""
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

HERE = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='kcmc-py36-metadata-') as folder:
    root = Path(folder)
    for name in ('repair.py', 'align-repository.py'):
        shutil.copyfile(str(HERE / name), str(root / name))
    spec = importlib.util.spec_from_file_location('synthetic_runtime', str(root / 'repair.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.UID == 2162 and module.GID == 2147 and len(module.PATHS) == 13
    helper = module.load_helper()
    assert helper.TARGET == module.TARGET
    module.UID = os.getuid() + 1
    try:
        module.run('check', helper=helper)
    except module.Refusal as error:
        assert str(error) == 'Expected hosting caller UID/GID required'
    else:
        raise AssertionError('Unexpected caller was accepted')
    module.UID, module.GID = os.getuid(), os.getgid()
    module.REPO = root / 'unused-synthetic-repository'
    module.PRIVATE_ROOT = root / 'private-journals'
    path = root / 'synthetic-public-file'
    data = b'Synthetic public compatibility fixture\n'
    path.write_bytes(data)
    path.chmod(0o644)
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        oid = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest().encode()
        record = {'name': module.PATHS[0], 'path': path, 'parent': helper.physical(path.parent),
                  'fd': fd, 'state': os.fstat(fd), 'before': 0o644, 'oid': oid}
        assert module.blob(fd, helper) == oid
        module.lease(record, helper)
        module.change_mode(fd, 0o664)
        record['state'] = os.fstat(fd)
        assert stat.S_IMODE(record['state'].st_mode) == 0o664
        module.lease(record, helper)
        module.change_mode(fd, 0o644)
        record['state'] = os.fstat(fd)
        with module.transaction(helper) as session:
            module.journal(session, [record], 'synthetic')
            assert stat.S_IMODE(session.stat().st_mode) == 0o700
            journal = session / 'journal.json'
            assert stat.S_IMODE(journal.stat().st_mode) == 0o600
            parsed = json.loads(journal.read_text())
            assert parsed['phase'] == 'synthetic' and parsed['baseline_head'] == module.BASELINE
            assert data.decode().strip() not in journal.read_text()
    finally:
        os.close(fd)
print('PASS: frozen loader, caller denial, FD hashing/leases/chmod, private flock/journal APIs; synthetic files only.')
