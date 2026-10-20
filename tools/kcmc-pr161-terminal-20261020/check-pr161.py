#!/usr/bin/env python3
"""Download the exact reviewed KCMC package, stage privately, and CHECK only."""
import hashlib, io, os, stat, subprocess, sys, tempfile, urllib.request, zipfile
from pathlib import Path

URL = 'https://raw.githubusercontent.com/bobhay75/Kcmc-connect/31b0adfd5f3d17c8a2844d5f3d48a025d017ca8b/tools/kcmc-pr161-terminal-20261020/kcmc-pr161-host-execution-20261020.zip'
SHA = '31ae463beb41b5a371e7da6feaf3ff84a398ef169632be915a7240320febd55e'
SIZE = 2991498
ACCOUNT_HOME = Path('/home/bobsome1')
APP = '/home/bobsome1/public_html/kcmc-connect'

def unpack(raw, parent):
    if len(raw) != SIZE or hashlib.sha256(raw).hexdigest() != SHA:
        raise RuntimeError('Download length or SHA256 differs; nothing staged or applied')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) != 26 or len(set(names)) != len(names) or sum(e.file_size for e in entries) > 6*1024*1024:
            raise RuntimeError('Unexpected archive inventory')
        payloads = []
        for entry in entries:
            name = entry.filename
            if name.startswith('/') or '\\' in name or any(p in ('', '.', '..') for p in name.split('/')):
                raise RuntimeError('Unsafe archive path')
            if not stat.S_ISREG(entry.external_attr >> 16) or entry.flag_bits & 1:
                raise RuntimeError('Nonregular or encrypted archive entry')
            data = archive.read(entry)
            if len(data) != entry.file_size:
                raise RuntimeError('Incomplete archive entry')
            payloads.append((name, data))
    stage = Path(tempfile.mkdtemp(prefix='kcmc-pr161-check-', dir=str(parent)))
    os.chmod(str(stage), 0o700)
    print('PRIVATE_STAGE=' + str(stage), flush=True)
    for name, data in payloads:
        path = stage / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        for ancestor in [path.parent] + list(path.parent.parents):
            if ancestor == stage.parent:
                break
            if ancestor.is_symlink() or not ancestor.is_dir():
                raise RuntimeError('Unsafe staging directory')
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fchmod(handle.fileno(), 0o644)
            os.fsync(handle.fileno())
    return stage

def main():
    if sys.version_info < (3, 6):
        raise RuntimeError('Python 3.6 or newer is required')
    if (os.getuid(), os.geteuid(), os.getgid(), os.getegid()) != (2162, 2162, 2147, 2147):
        raise RuntimeError('Run in the bobsome1 cPanel Terminal (UID2162/GID2147)')
    for directory in [ACCOUNT_HOME] + list(ACCOUNT_HOME.parents):
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError('Unsafe account directory')
    with urllib.request.urlopen(URL, timeout=45) as response:
        raw = response.read(SIZE + 1)
    stage = unpack(raw, ACCOUNT_HOME)
    print('ZIP_SHA256=' + SHA, flush=True)
    commands = [('check-release.py', APP), ('install-brand.py', 'check'),
                ('content-publication/publish.py', 'check')]
    failed = False
    for arguments in commands:
        print('\nCHECK: ' + ' '.join(arguments), flush=True)
        result = subprocess.run([sys.executable, '-I', '-B'] + list(arguments),
                                cwd=str(stage), timeout=120)
        failed = failed or result.returncode != 0
    print('\nCHECKS FINISHED. No apply command was run. Send all output, including PRIVATE_STAGE and content SHA256.', flush=True)
    return 1 if failed else 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print('CHECK REFUSED: ' + str(error), file=sys.stderr)
        sys.exit(1)
