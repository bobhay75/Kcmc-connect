#!/usr/bin/env python3
"""Build an offline review bundle; never access or modify the hosting account."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
BASE = '1d14b582b73780c020ba3d489a3a2d58cf5f45e5'
SOURCE = 'f62fd1e1fb499ac695688c26428f9ed221e863da'
MODIFIED = ('index.php', 'manifest.webmanifest', 'assets/icons/icon-192.png',
            'assets/icons/icon-512.png', 'sw.js')
ADDED = ('home-welcome.css', 'assets/visuals/kcmc-building-original-20261018.jpg')

CHECKER = '''#!/usr/bin/env python3
"""Read-only host preflight. No apply, force, network or configuration access."""
import hashlib,json,os,stat,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
PIN=__MANIFEST_PIN__
def need(ok,message):
    if not ok: raise RuntimeError(message)
def read(root,name,missing=False):
    p=root/name
    for parent in [root]+list(p.parents):
        need(not parent.is_symlink(),'Symbolic directory refused: '+str(parent))
    if not p.exists() and not p.is_symlink():
        need(missing,'Missing code: '+name); return None
    info=p.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and
         stat.S_IMODE(info.st_mode) in (0o644,0o664),'Unsafe code metadata: '+name)
    data=p.read_bytes()
    return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
def inspect(root):
    raw=(HERE/'manifest.json').read_bytes()
    need(hashlib.sha256(raw).hexdigest()==PIN,'Release manifest changed')
    manifest=json.loads(raw)
    matches=[]
    for variant,bundle in manifest['variants'].items():
        if all(read(root,n)==row for n,row in bundle['guards'].items()):
            for phase in ['before','after']:
                if all(read(root,n,True)==row for n,row in bundle[phase].items()):
                    matches.append((variant,phase))
    need(len(matches)==1,'Unknown, mixed or incomplete public bundle; no installation authorized')
    return matches[0]
if __name__=='__main__':
    try:
        need(len(sys.argv)==2,'Usage: python3 check-release.py /home/bobsome1/public_html/kcmc-connect')
        variant,phase=inspect(Path(os.path.abspath(sys.argv[1])))
        print('CHECK',variant,phase,'(read only; no installation performed)')
    except (OSError,RuntimeError) as exc:
        print('REFUSED:',exc,file=sys.stderr);sys.exit(1)
'''

RUNBOOK = '''# KCMC welcome homepage release candidate

This bundle is review material. It performs no deployment. Release approval and a
successful current-host preflight are required before installation.

Scope: five existing public files and two new public assets. The original church
photograph is byte-for-byte unchanged. No private records, configuration, account
code, calendar code, mail, payroll, cron or repository files belong in the write set.

The main and installed livecalendar variants are independently pinned. Their old
hero class-order differences disappear when the approved fixed-photo hero replaces
that whole section. Both derive exactly the same final index.php. The installed
livecalendar stylesheet remains unchanged and is checked as a read-only guard.

1. Extract this ZIP into a private staging directory outside public_html. Verify
   the ZIP SHA256 against the review receipt. Do not extract it over the live app.
2. Run `python3 -I -B check-release.py /home/bobsome1/public_html/kcmc-connect`.
   Continue only for the expected variant in `before` state. Unknown, unsafe or
   mixed bundles require fresh investigation; there is no force option.
3. Before any replacement, create an actual private backup of all five existing
   targets, recording their hashes, modes and ownership. Verify that backup matches
   manifest.json for the selected variant. Record that both new targets are absent.
4. A guarded host transaction must stage all seven `after/` files, lint staged
   index.php with the host PHP 8.2+ CLI, recheck the complete preflight and unchanged
   prerequisite metadata, then install assets and manifest before index.php, with
   sw.js last. Preserve existing code modes and ownership. The host transaction
   adapter is not included or approved by this review bundle.
5. Re-run preflight: require the same variant in `after` state. Verify the real
   public homepage on phone and desktop, Visit / Watch / Events / Prayer / Family,
   app icon, and offline reload. Record actual public responses and final hashes.

Rollback: if any replacement or acceptance check fails, stop the transaction and
verify each current target is its exact recorded before or after image. Restore
the five actual backups, restoring index.php and sw.js before removing either new
asset. Remove a new asset only if it is the exact installed after image and no
retained consumer requires it. Refuse overwriting any unrecognized concurrent edit.
Re-run preflight and require the original variant in `before` state. `before/` holds
reviewed reference images; actual host backups are authoritative for rollback.

Browser caches may retain a newer worker until the next update/reload. Verify the
rollback online and after a fresh worker update; do not claim that server rollback
immediately changes every already installed device.
'''


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def image(ref, name):
    return git('show', ref + ':' + PREFIX + name)


def metadata(data):
    return None if data is None else {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def build(destination):
    changed = git('diff', '--name-only', BASE, SOURCE, '--', PREFIX).decode().splitlines()
    assert set(changed) == {PREFIX+n for n in MODIFIED+ADDED}, 'Exact seven-file public scope required'
    before = {n: image(BASE, n) for n in MODIFIED}
    after = {n: image(SOURCE, n) for n in MODIFIED+ADDED}
    # Verify the reference variant evidence against its immutable source object.
    evidence = 'tools/kcmc-follow-up-oct18/evidence/public/'
    live_before = git('show', BASE+':'+evidence+'livecalendar/index-after.php')
    assert git('show', BASE+':'+evidence+'main/index-after.php') == before['index.php']
    live_after = live_before.decode()
    prior, final = before['index.php'].decode().splitlines(True), after['index.php'].decode().splitlines(True)
    for group in difflib.SequenceMatcher(a=prior, b=final, autojunk=False).get_grouped_opcodes(3):
        first, last = group[0], group[-1]
        old, new = ''.join(prior[first[1]:last[2]]), ''.join(final[first[3]:last[4]])
        # Only the superseded gallery class ordering differs in the installed variant.
        old = old.replace('class="home-cover-photo hero-photo is-current"', 'class="hero-photo is-current home-cover-photo"').replace('class="home-cover-photo hero-photo"', 'class="hero-photo home-cover-photo"')
        assert old and live_after.count(old) == 1, 'Unique installed homepage anchor required'
        live_after = live_after.replace(old, new, 1)
    assert live_after.encode() == after['index.php'], 'Installed variant must reach exact reviewed homepage'
    entries = {'README.md': RUNBOOK.encode()}
    manifest = {'baseline_commit': BASE, 'runtime_source_commit': SOURCE, 'variants': {}}
    for variant in ('main', 'livecalendar'):
        prior = dict(before)
        if variant == 'livecalendar': prior['index.php'] = live_before
        guards = {}
        for n in ('public-presentation.css', 'public-presentation.js', 'styles.css',
                  'app.js', 'lib/screen-navigation.php', 'app-theme.css', 'app-navigation.js'):
            data = image(BASE, n)
            assert data == image(SOURCE, n), 'Read-only prerequisite changed: '+n
            if variant == 'livecalendar' and n == 'public-presentation.css':
                data = git('show', BASE+':'+evidence+'livecalendar/'+n)
            guards[n] = metadata(data)
        manifest['variants'][variant] = {'before': {n: metadata(prior.get(n)) for n in MODIFIED+ADDED},
                                         'after': {n: metadata(after[n]) for n in MODIFIED+ADDED}, 'guards': guards}
        for n, data in prior.items(): entries['before/'+variant+'/'+n] = data
    for n, data in after.items(): entries['after/'+n] = data
    raw = (json.dumps(manifest, sort_keys=True, indent=2)+'\n').encode()
    entries['manifest.json'] = raw
    entries['check-release.py'] = CHECKER.replace('__MANIFEST_PIN__', repr(hashlib.sha256(raw).hexdigest())).encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 19, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
    print(hashlib.sha256(destination.read_bytes()).hexdigest(), destination)
    return manifest, entries


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
