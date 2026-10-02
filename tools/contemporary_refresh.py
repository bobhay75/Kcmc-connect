#!/usr/bin/env python3
"""KCMC Contemporary Worship refresh; Python 3.6+, no external dependencies.
Run on cPanel: python3 contemporary_refresh.py [--check | --rollback BACKUP]
Only public HTML/CSS/carousel interval/cache versions are changed.
Use the supplied local church photograph, retain alt text, hide photo labels,
and retain/reinstate the previously approved seven-minute welcome rotation.
Never run Deploy HEAD from the old main after applying this scoped patch.
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
VERSION = 'contemporary-20261002'
PRIOR_VERSION = 'hero-captions-20261002'
CACHE = 'kcmc-connect-v3.0.3-public-only-' + VERSION
MARKER = 'KCMC_PHOTO_CAPTIONS_HIDDEN_20261002'
CSS = ('\n/* ' + MARKER + ' BEGIN */\n'
       '/* Hide visible photo labels only; keep alt text and carousel status. */\n'
       '[data-hero-gallery] [data-hero-caption],\n'
       '[data-hero-gallery] .photo-source,\n'
       '[data-family-welcome] .photo-source { display:none !important; }\n'
       '/* ' + MARKER + ' END */\n')
OLD_TIMER = 'timer = setTimeout(() => { show(current + 1, false); schedule(); }, 8000);'
NEW_TIMER = 'timer = setTimeout(() => { show(current + 1, false); schedule(); }, 420000);'

FEATURE_MARKER = "KCMC_CONTEMPORARY_FEATURE_20261002"
OLD_SECTION = '  <section class="section">\n    <div class="wrap video-card">\n      <div class="video-art contemporary-art"><div><span class="pill">Worship online</span><br><br><b>Contemporary<br>Worship</b></div></div>\n      <div class="video-copy"><div class="eyebrow">Messages &amp; worship</div><h2 style="font-family:Georgia,serif;font-size:3rem;font-weight:400;margin:.15em 0">Worship wherever you are.</h2><p class="muted">Find KCMC messages and worship on the church’s official Facebook page. Facebook may ask you to sign in.</p><div class="btns"><a class="btn gold" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener">Watch messages</a><a class="btn secondary" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener">All live videos</a></div></div>\n    </div>\n  </section>'
NEW_SECTION = '  <!-- KCMC_CONTEMPORARY_FEATURE_20261002 BEGIN -->\n  <section class="section cw-section" data-contemporary-feature aria-labelledby="cw-title">\n    <div class="wrap">\n      <div class="cw-feature">\n        <div class="cw-copy">\n          <p class="cw-kicker">Sunday mornings <span>10:30 AM</span></p>\n          <h2 id="cw-title">Contemporary<br><span>Worship.</span></h2>\n          <p class="cw-intro">Come as you are. Find your place.</p>\n          <p class="cw-description">A relaxed, coffee-shop setting with fellowship, refreshments, and an uplifting message from the Bible.</p>\n          <p class="cw-family">Bringing the family? Launch Kids meets during the 10:30 service.</p>\n          <div class="cw-actions">\n            <a class="cw-button cw-primary" href="#visit" data-route="visit">Plan your Sunday <span aria-hidden="true">&#8594;</span></a>\n            <a class="cw-button cw-secondary" href="https://www.facebook.com/KimberlingCityMethodistChurch/live_videos" target="_blank" rel="noopener noreferrer">Watch messages</a>\n          </div>\n          <p class="cw-online-note">Messages and worship are on our official Facebook page. Facebook may ask you to sign in.</p>\n        </div>\n        <div class="cw-media">\n          <img src="assets/visuals/kcmc-worship-2017.webp" alt="People gathered around tables for worship at KCMC, photographed in 2017" width="640" height="344" loading="lazy" decoding="async">\n        </div>\n      </div>\n    </div>\n  </section>\n  <!-- KCMC_CONTEMPORARY_FEATURE_20261002 END -->'
FEATURE_CSS = '\n/* KCMC_CONTEMPORARY_FEATURE_20261002 BEGIN */\n/* This section does not style the welcome carousel, private pages or photo captions. */\n.cw-section{padding:54px 0 64px}\n.cw-feature{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.12fr);background:#102d40;border:1px solid #3e5869;border-radius:28px;overflow:hidden;box-shadow:0 20px 52px rgba(0,0,0,.2)}\n.cw-copy{padding:clamp(24px,3.4vw,42px);min-width:0;display:flex;flex-direction:column;justify-content:center}\n.cw-kicker{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:.75rem;font-weight:800;line-height:1.5;text-transform:uppercase;letter-spacing:.14em;margin:0 0 20px;color:#ead2a4}\n.cw-kicker span{display:inline-block;border:1px solid #8f7955;border-radius:99px;padding:5px 11px;letter-spacing:.04em;color:#ffedc9}\n.cw-copy h2{font-family:Inter,ui-sans-serif,system-ui,sans-serif;font-size:clamp(2.2rem,4.2vw,3.65rem);font-weight:800;line-height:1.06;letter-spacing:-.045em;margin:0 0 22px;color:#fff;overflow-wrap:normal}\n.cw-copy h2 span{color:#f3cf90}\n.cw-intro{font-size:clamp(1.08rem,1.8vw,1.25rem);font-weight:650;color:#fff;line-height:1.5;margin:0 0 12px}\n.cw-description{font-size:1rem;line-height:1.75;color:#d8e4eb;margin:0 0 15px}\n.cw-family{font-size:.94rem;line-height:1.65;color:#d8e4eb;margin:0 0 8px;padding-left:14px;border-left:2px solid #d7b16b}\n.cw-actions{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0 14px}\n.cw-button{display:inline-flex;align-items:center;justify-content:center;gap:14px;min-height:48px;padding:12px 18px;border:1px solid #8ba3b2;border-radius:12px;text-decoration:none;font:inherit;font-size:.94rem;font-weight:800;line-height:1.35;text-align:center;white-space:normal}\n.cw-primary{background:#f3cf90;color:#12293b;border-color:#f3cf90}\n.cw-secondary{background:#102d40;color:#fff}\n.cw-button:hover{filter:brightness(1.08)}\n.cw-button:focus-visible{outline:3px solid #fff;outline-offset:4px}\n.cw-online-note{font-size:.78rem;line-height:1.6;color:#beced8;margin:0;max-width:40em}\n.cw-media{background:#162d35;min-width:0;position:relative;overflow:hidden}\n.cw-media img{display:block;width:100%;height:100%;object-fit:cover;object-position:52% center;min-height:390px}\n@media(max-width:850px){.cw-feature{grid-template-columns:1fr}.cw-media{grid-row:1}.cw-media img{height:auto;min-height:0;aspect-ratio:640/344;object-fit:contain}.cw-copy{padding:30px}.cw-copy h2{font-size:clamp(2.35rem,7.2vw,3.5rem)}.cw-kicker{margin-bottom:18px}}\n@media(max-width:420px){.cw-section{padding:32px 0 42px}.cw-feature{border-radius:20px}.cw-copy{padding:23px}.cw-copy h2{font-size:clamp(1.85rem,8vw,2.7rem)}.cw-actions{display:grid;grid-template-columns:1fr}.cw-kicker{font-size:.68rem;gap:8px}.cw-intro{font-size:1.08rem}}\n@media(prefers-reduced-motion:reduce){.cw-feature *{transition:none!important;animation:none!important}}\n/* KCMC_CONTEMPORARY_FEATURE_20261002 END */\n'

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
        if len(matches) != 1 or matches[0].group(1) not in ('1.0.0', 'tony-staff-20261001', PRIOR_VERSION, VERSION):
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
    if MARKER in css:
        if css.count(MARKER) != 2 or CSS not in css:
            raise Stop('Partial caption patch detected.')
    else:
        text['public-presentation.css'] = css + CSS
    index = text['index.php']
    if '<?php' not in index or 'data-hero-gallery' not in index:
        raise Stop('Unexpected homepage source.')
    if FEATURE_MARKER in index:
        if index.count(FEATURE_MARKER) != 2 or NEW_SECTION not in index:
            raise Stop('Edited or partial Contemporary Worship section; preserved.')
    else:
        index = one(index, OLD_SECTION, NEW_SECTION, 'Contemporary Worship section')
    text['index.php'] = versions(index, 'homepage')
    css = text['public-presentation.css']
    if FEATURE_MARKER in css:
        if css.count(FEATURE_MARKER) != 2 or FEATURE_CSS not in css:
            raise Stop('Edited or partial Contemporary stylesheet; preserved.')
    else:
        text['public-presentation.css'] = css + FEATURE_CSS
    sw = text['sw.js']
    match = re.search(r"^const CACHE='([^']+)';", sw)
    allowed = ('kcmc-connect-v3.0.3-public-only',
               'kcmc-connect-v3.0.3-public-only-photos-20261001',
               'kcmc-connect-v3.0.3-public-only-tony-staff-20261001',
               'kcmc-connect-v3.0.3-public-only-' + PRIOR_VERSION, CACHE)
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
    image = regular(app / 'assets/visuals/kcmc-worship-2017.webp').read_bytes()
    if len(image) < 100 or image[:4] != b'RIFF' or image[8:12] != b'WEBP':
        raise Stop('Local worship photograph is not a readable WebP; no files changed.')
    original = {name: regular(app / name).read_bytes() for name in FILES}
    desired = transform(original)
    changed = {name: desired[name] for name in FILES if desired[name] != original[name]}
    if not changed:
        print('ALREADY INSTALLED: Contemporary Worship refresh; seven-minute welcome rotation.')
        return None
    backup = Path(tempfile.mkdtemp(prefix='contemporary-', dir=str(backups)))
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
    print('SUCCESS: Contemporary Worship section refreshed; welcome rotation is 7 minutes.')
    print('Uses your local worship photo. Photo labels hidden; accounts and private data not edited.')
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
    backups = Path.home() / '.kcmc-contemporary-backups'
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
