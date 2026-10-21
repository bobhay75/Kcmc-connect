#!/usr/bin/env python3
"""Four-file digital bulletin and disclosure patch; no content/config/private-record writes."""
import argparse, fcntl, hashlib, json, os, shutil, stat, tempfile, subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
VARIANTS = json.loads((PACKAGE / 'manifest.json').read_text())
parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['check', 'apply', 'rollback'])
parser.add_argument('--root', default='/home/bobsome1/public_html/kcmc-connect')
parser.add_argument('--session')
parser.add_argument('--php', help='PHP executable for staged syntax checks')
args = parser.parse_args()
root = Path(args.root)
if root.is_symlink() or not root.is_dir() or root.resolve() != root:
    raise SystemExit('STOP: application path must be a real absolute directory.')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def target(rel):
    path = root / rel
    info = path.lstat()
    if path.resolve() != path or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
        raise RuntimeError('Unexpected file type or owner: ' + rel)
    return path

# Accept either verified predecessor as a whole; never combine file variants.
MANIFEST = None
if args.action == 'rollback' and args.session:
    proposed = json.loads((Path(args.session) / 'manifest.json').read_text())
    if proposed not in VARIANTS.values():
        raise SystemExit('Unknown rollback manifest.')
    MANIFEST = proposed
else:
    for candidate in VARIANTS.values():
        hashes = {rel: digest(target(rel).read_bytes()) for rel in candidate}
        if any(all(hashes[rel] == spec[label] for rel, spec in candidate.items()) for label in ['before', 'after']):
            MANIFEST = candidate
            break
if MANIFEST is None:
    raise SystemExit('STOP: application differs from the reviewed versions. Nothing changed.')

def state():
    hashes = {rel: digest(target(rel).read_bytes()) for rel in MANIFEST}
    for label in ['before', 'after']:
        if all(hashes[rel] == spec[label] for rel, spec in MANIFEST.items()):
            return label
    raise RuntimeError('Files differ from the reviewed patch. Nothing changed.')

def replace(path, data, mode):
    fd, name = tempfile.mkstemp(prefix='.kcmc-slide-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

# Lock a private sibling file; never use the public application as a backup area.
lock = root.parent.parent / '.kcmc-digital-bulletin.lock'
fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'a') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    current = state()
    if args.action == 'check':
        print(json.dumps({'state': current, 'writes_performed': False}))
    elif args.action == 'apply':
        if current == 'after':
            print('Already installed; no changes.')
        else:
            payload = {rel: (PACKAGE / 'payload' / rel).read_bytes() for rel in MANIFEST}
            assert all(digest(data) == MANIFEST[rel]['after'] for rel, data in payload.items()), 'Payload verification failed'
            php = args.php or shutil.which('php') or '/opt/alt/php82/usr/bin/php'
            if not os.access(php, os.X_OK):
                raise SystemExit('STOP: PHP syntax checker unavailable. Nothing changed.')
            for rel in payload:
                if rel.endswith('.php'):
                    checked = subprocess.run([php, '-l', str(PACKAGE / 'payload' / rel)], capture_output=True, text=True)
                    if checked.returncode:
                        raise SystemExit('STOP: staged PHP check failed for ' + rel + '. Nothing changed.')
            session = Path(tempfile.mkdtemp(prefix='kcmc-digital-bulletin-backup-', dir=root.parent.parent))
            modes = {}
            for rel in MANIFEST:
                path = target(rel)
                modes[rel] = stat.S_IMODE(path.stat().st_mode)
                backup = session / rel
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(path.read_bytes())
            (session / 'manifest.json').write_text(json.dumps(MANIFEST))
            (session / 'modes.json').write_text(json.dumps(modes))
            changed = []
            try:
                for rel, data in payload.items():
                    path = target(rel)
                    if digest(path.read_bytes()) != MANIFEST[rel]['before']:
                        raise RuntimeError('Concurrent edit detected: ' + rel)
                    replace(path, data, modes[rel])
                    changed.append(rel)
                assert state() == 'after'
            except BaseException:
                for rel in reversed(changed):
                    path = target(rel)
                    if digest(path.read_bytes()) == MANIFEST[rel]['after']:
                        replace(path, (session / rel).read_bytes(), modes[rel])
                raise
            print(json.dumps({'result': 'installed', 'files': list(MANIFEST), 'backup': str(session), 'state': state()}))
    else:
        if not args.session:
            raise SystemExit('Rollback requires --session BACKUP_PATH')
        session = Path(args.session)
        if session.is_symlink() or session.resolve() != session or session.stat().st_uid != os.getuid():
            raise SystemExit('Invalid backup path.')
        if json.loads((session / 'manifest.json').read_text()) != MANIFEST:
            raise SystemExit('Backup manifest does not match.')
        saved = {rel: (session / rel).read_bytes() for rel in MANIFEST}
        assert all(digest(data) == MANIFEST[rel]['before'] for rel, data in saved.items()), 'Backup verification failed'
        modes = json.loads((session / 'modes.json').read_text())
        if current == 'after':
            for rel, data in saved.items():
                path = target(rel)
                if digest(path.read_bytes()) != MANIFEST[rel]['after']:
                    raise RuntimeError('Concurrent edit detected: ' + rel)
                replace(path, data, modes[rel])
        print(json.dumps({'result': 'rolled_back', 'state': state()}))
