#!/usr/bin/env python3
"""KCMC: hide photo captions, rotate every seven minutes; scoped, reversible patch.
Run on cPanel: python3 hero_caption_fix.py [--check | --rollback BACKUP]
No image, authentication, private data or editorial-content changes.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

FILES = ('public-presentation.js', 'public-presentation.css', 'index.php', 'sw.js')
LEGACY_VERSION = 'hero-captions-20261002'
VERSION = 'photo-labels-20261003'
CACHE = 'kcmc-connect-v3.0.3-public-only-' + VERSION
LEGACY_MARKER = 'KCMC_PHOTO_CAPTIONS_HIDDEN_20261002'
LEGACY_CSS = ('\n/* ' + LEGACY_MARKER + ' BEGIN */\n'
       '/* Hide visible photo labels only; keep alt text and carousel status. */\n'
       '[data-hero-gallery] [data-hero-caption],\n'
       '[data-hero-gallery] .photo-source,\n'
       '[data-family-welcome] .photo-source { display:none !important; }\n'
       '/* ' + LEGACY_MARKER + ' END */\n')
MARKER = 'KCMC_PHOTO_SUBTITLES_HIDDEN_20261003'
CSS = ('\n/* ' + MARKER + ' BEGIN */\n'
       '/* Hide visible photo labels only; keep alt text and carousel status. */\n'
       '[data-hero-caption],\n'
       '.hero-photo-caption,\n'
       '.photo-source { display:none !important; }\n'
       '/* ' + MARKER + ' END */\n')
OLD_TIMER = 'timer = setTimeout(() => { show(current + 1, false); schedule(); }, 8000);'
NEW_TIMER = 'timer = setTimeout(() => { show(current + 1, false); schedule(); }, 420000);'

class Stop(RuntimeError):
    pass

def sha(data):
    return hashlib.sha256(data).hexdigest()

def one(text, old, new, label):
    if old == new:
        return text
    if text.count(new) == 1 and old not in text:
        return text
    if text.count(old) != 1 or new in text:
        raise Stop('Unexpected ' + label + '; no files changed.')
    return text.replace(old, new, 1)

def versions(text, label):
    for asset in ('public-presentation.js', 'public-presentation.css'):
        pattern = re.escape(asset) + r'\?v=([A-Za-z0-9._-]+)'
        matches = list(re.finditer(pattern, text))
        if len(matches) != 1 or matches[0].group(1) not in ('1.0.0', 'tony-staff-20261001', LEGACY_VERSION, VERSION):
            raise Stop('Unexpected ' + label + ' asset version: ' + asset)
        text = re.sub(pattern, asset + '?v=' + VERSION, text)
    return text

def transform(original):
    text = {name: original[name].decode('utf-8') for name in FILES}
    js = text['public-presentation.js']
    if not all(s in js for s in ('[data-hero-gallery]', 'const motion = window.matchMedia', 'function schedule()', 'function show(')):
        raise Stop('Unexpected gallery implementation.')
    text['public-presentation.js'] = one(js, OLD_TIMER, NEW_TIMER, 'hero timer')
    css = text['public-presentation.css']
    # .photo-source belongs to an optional family-photo layout, not the carousel.
    # The existing gallery and timer are validated above; do not require that layout.
    if '.hero-photo' not in css:
        raise Stop('Unexpected public gallery stylesheet; no files changed.')
    if LEGACY_MARKER in css:
        if css.count(LEGACY_MARKER) != 2 or LEGACY_CSS not in css:
            raise Stop('Partial legacy caption patch detected.')
        css = css.replace(LEGACY_CSS, '')
    if MARKER in css:
        if css.count(MARKER) != 2 or CSS not in css:
            raise Stop('Partial caption patch detected.')
        text['public-presentation.css'] = css
    else:
        text['public-presentation.css'] = css + CSS
    index = text['index.php']
    if '<?php' not in index or 'data-hero-gallery' not in index:
        raise Stop('Unexpected homepage source.')
    text['index.php'] = versions(index, 'homepage')
    sw = text['sw.js']
    match = re.search(r"^const CACHE='([^']+)';", sw)
    allowed = ('kcmc-connect-v3.0.3-public-only',
               'kcmc-connect-v3.0.3-public-only-photos-20261001',
               'kcmc-connect-v3.0.3-public-only-tony-staff-20261001',
               'kcmc-connect-v3.0.3-public-only-' + LEGACY_VERSION, CACHE)
    if not match or match.group(1) not in allowed:
        raise Stop('Unknown service-worker release; no files changed.')
    sw = sw[:match.start(1)] + CACHE + sw[match.end(1):]
    text['sw.js'] = versions(sw, 'service worker')
    return {name: text[name].encode('utf-8') for name in FILES}

def regular(path):
    if path.is_symlink() or path.resolve() != path.absolute() or not path.is_file():
        raise Stop('Expected regular file: ' + str(path))
    return path

def stage(path, data, mode, gid):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(str(path), mode)
    if path.stat().st_gid != gid:
        os.chown(str(path), -1, gid)

def lint(directory, names):
    for name in names:
        command = None
        if name.endswith('.php'):
            command = [shutil.which('php') or 'php', '-n', '-l', str(directory / name)]
        elif name.endswith('.js') and shutil.which('node'):
            command = ['node', '--check', str(directory / name)]
        if command:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            if result.returncode:
                raise Stop('Syntax check failed: ' + name)

def rollback(app, backup):
    manifest = json.loads(regular(backup / 'manifest.json').read_text())
    if manifest.get('root') != str(app):
        raise Stop('Rollback target mismatch.')
    pending = []
    for name, row in manifest['files'].items():
        if name not in FILES:
            raise Stop('Unapproved rollback path.')
        original = regular(backup / 'original' / name).read_bytes()
        current = regular(app / name).read_bytes()
        if sha(original) != row['old_sha256']:
            raise Stop('Backup integrity check failed.')
        if sha(current) not in (row['old_sha256'], row['new_sha256']):
            raise Stop('Later edits in ' + name + '; rollback refused.')
        if sha(current) != row['old_sha256']:
            pending.append((name, original, row))
    for name, original, row in pending:
        temp = backup / 'restore' / name
        stage(temp, original, row['mode'], row['gid'])
        os.replace(str(temp), str(app / name))
    return len(pending)

def apply(app, backups, check=False):
    original = {name: regular(app / name).read_bytes() for name in FILES}
    desired = transform(original)
    changed = {name: desired[name] for name in FILES if desired[name] != original[name]}
    if not changed:
        print('ALREADY INSTALLED: captions hidden; hero interval is seven minutes.')
        return None
    backup = Path(tempfile.mkdtemp(prefix='hero-', dir=str(backups)))
    if backup.stat().st_dev != app.stat().st_dev:
        raise Stop('Backup and app must be on the same filesystem.')
    manifest = {'root': str(app), 'files': {}}
    for name in changed:
        info = (app / name).stat()
        mode = stat.S_IMODE(info.st_mode)
        stage(backup / 'original' / name, original[name], mode, info.st_gid)
        stage(backup / 'patched' / name, changed[name], mode, info.st_gid)
        manifest['files'][name] = {'old_sha256': sha(original[name]), 'new_sha256': sha(changed[name]), 'mode': mode, 'gid': info.st_gid}
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    lint(backup / 'patched', changed)
    if check:
        print('PREFLIGHT PASSED: ' + ', '.join(changed) + '. No live files changed.')
        return backup
    written = []
    try:
        for name in FILES:
            if regular(app / name).read_bytes() != original[name]:
                raise Stop('Concurrent change detected: ' + name)
        for name in changed:
            if regular(app / name).read_bytes() != original[name]:
                raise Stop('Concurrent change detected: ' + name)
            os.replace(str(backup / 'patched' / name), str(app / name))
            written.append(name)
            if (app / name).read_bytes() != changed[name]:
                raise Stop('Write verification failed: ' + name)
        lint(app, changed)
    except BaseException:
        # Never overwrite another editor's subsequent change during recovery.
        for name in reversed(written):
            if regular(app / name).read_bytes() != changed[name]:
                print('STOP: later edit preserved in ' + name + '; review backup ' + str(backup), file=sys.stderr)
                continue
            row = manifest['files'][name]
            temp = backup / 'restore' / name
            stage(temp, original[name], row['mode'], row['gid'])
            os.replace(str(temp), str(app / name))
        raise
    print('SUCCESS: photo captions hidden; hero changes every 7 minutes while playing.')
    print('Images, alt text, pause/next controls, accounts and private data are unchanged.')
    print('Changed only: ' + ', '.join(changed))
    print('Private backup: ' + str(backup))
    print('Rollback: ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(Path(__file__).absolute())) + ' --rollback ' + shlex.quote(str(backup)))
    print('Close and reopen KCMC Connect to load the new public assets.')
    return backup

def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    app = Path.home() / 'public_html/kcmc-connect'
    backups = Path.home() / '.kcmc-hero-backups'
    if not shutil.which('php'):
        raise Stop('PHP CLI is unavailable.')
    if not app.is_dir() or app.resolve() != app.absolute():
        raise Stop('Expected KCMC app folder is missing or symlinked.')
    if backups.resolve() != backups.absolute():
        raise Stop('Backup path is symlinked.')
    backups.mkdir(mode=0o700, exist_ok=True)
    backups.chmod(0o700)
    fd = os.open(str(backups / '.lock'), os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            backup = args.rollback.absolute()
            if backup.parent != backups or backup.is_symlink():
                raise Stop('Rollback must use this patch\'s private backup folder.')
            print('Restored ' + str(rollback(app, backup)) + ' public code files.')
        else:
            apply(app, backups, args.check)

if __name__ == '__main__':
    try:
        main()
    except (Stop, OSError, ValueError, subprocess.SubprocessError) as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        sys.exit(1)
