#!/usr/bin/env python3
"""Reproduce the v2 coordinator for unchanged owner/workflow app payloads."""
from __future__ import print_function
import base64
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
FROZEN_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
BASE_COMMIT = '00fdd469482564a3511a29a27a99502c24a32845'
SOURCE_COMMIT = 'ba7b5df314e1be604d46443025d41b1c8fe732a4'
OWNER_FIXTURE_SHA256 = 'd872e4deb60baca4cade936412c9706294a3e8a5a2e671acddc59493ca52e527'
LINK_FIXTURE_SHA256 = 'b6ca2c3e1e218627643aa9d5962ccc11b535242bb7e4e5c25303afd776f32042'
OWNER_PATHS = ('lib/password-lifecycle.php', 'admin/users.php', 'admin/password-resets.php')
VARIANTS = ('pre_a7', 'owner_a7')
PINS = {'owner-dependency-extension.py': '748dc5de1d3f3d03c5a1e929ff65d640acfba3a09072846f09e4005f76745ae5', 'wrapper.py.in': 'ac9cb75aa8ac8263446557633eecdb4151c77b12c91be19c8c66787b2e9c108c', 'extension.py': 'a09f1d2e69f20a057be712b7c21bae3ec174e2faea60c9eb1dcbf2fca985d6c2', 'source-runtime-reviewed.json': '9775522457d5f77b7dc8f5cc6d37a9d95ab3888adf04ceed2490fe13bad3b9e8', 'runtime-reviewed.json': 'e52f907a256e501e881c68ce790e6260ed9bddb2af911f44d401cafb8ed7c46f', 'owner-runtime-reviewed.json': '817ded563dde8678b75e33993cad163410d09401833162b67f183e3f32cf1eea', 'prerequisite-reviewed.json': '2b05802509a335d3dd5af320224c408d7d7cacc38821ede2b9ad18f98775f33e'}


def sha(content): return hashlib.sha256(content).hexdigest()


def once(source, before, after):
    if source.count(before) != 1: raise ValueError('Frozen derivation anchor changed')
    return source.replace(before, after, 1)


def verify_original_package():
    original = HERE / 'provenance/original-package'
    checksums = (original / 'CHECKSUMS.sha256').read_bytes()
    if sha(checksums) != '0d74e36e21b117ebbd4bdd73bc60778036b6d416d0cc372c7a129803d6448ee3':
        raise ValueError('Original published checksum manifest changed')
    for line in checksums.decode('ascii').splitlines():
        expected, name = line.split('  ', 1)
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts: raise ValueError('Unsafe original package evidence path')
        source = original / relative if (original / relative).is_file() else HERE / relative
        if sha(source.read_bytes()) != expected: raise ValueError('Original published evidence changed: ' + name)


def verify_inputs():
    verify_original_package()
    for path, expected in PINS.items():
        if sha((HERE / path).read_bytes()) != expected: raise ValueError('Pinned package input changed: ' + path)
    raw = (HERE / 'frozen-minimal-installer.py').read_bytes()
    if sha(raw) != FROZEN_SHA256: raise ValueError('Frozen engine changed')
    manifest = json.loads((HERE / 'source-runtime-reviewed.json').read_text())
    runtime = json.loads((HERE / 'runtime-reviewed.json').read_text())
    owner = json.loads((HERE / 'owner-runtime-reviewed.json').read_text())
    prerequisite = json.loads((HERE / 'prerequisite-reviewed.json').read_text())
    if manifest['baseline_commit'] != BASE_COMMIT or len(manifest['paths']) != 18 or set(runtime) != set(VARIANTS): raise ValueError('Release scope changed')
    paths = tuple(manifest['paths']); deps = {path: tuple(values) for path, values in manifest['dependencies'].items()}
    if set(paths) != set(manifest['files']) or len(paths) != len(set(paths)) or set(owner) != set(OWNER_PATHS) or set(owner) & set(paths): raise ValueError('Groups overlap or scope changed')
    for path, values in deps.items():
        if path not in paths or any(value not in paths or paths.index(value) >= paths.index(path) for value in values): raise ValueError('Dependency order changed')
    linkraw = (HERE / 'provenance/push-owner-link-reviewed.json').read_bytes()
    ownerraw = (HERE / 'provenance/owner-account-guard-reviewed.json').read_bytes()
    if sha(linkraw) != LINK_FIXTURE_SHA256 or sha(ownerraw) != OWNER_FIXTURE_SHA256: raise ValueError('Earlier owner source fixture changed')
    link = json.loads(linkraw.decode('utf-8'))['files']['member/notifications.php']
    owner_fixture = json.loads(ownerraw.decode('utf-8'))['files']
    for profile in VARIANTS:
        files = runtime[profile]
        if tuple(files) != paths: raise ValueError('Complete profile ordering changed')
        for path in paths:
            item = files[path]; target = (HERE / 'evidence/after' / path).read_bytes()
            if sha(target) != item['after_sha256'] or len(target) != item['after_bytes']: raise ValueError('Approved target bytes changed')
            canonical = manifest['files'][path]
            if item['after_sha256'] != canonical['after_sha256'] or item['after_bytes'] != canonical['after_bytes']: raise ValueError('Profiles do not share one target tuple')
            if item['before_sha256'] is None:
                if canonical['before_sha256'] is not None or item['before_bytes'] != 0 or item['replacements'] != [] or base64.b64decode(item['after_base64'].encode('ascii'), validate=True) != target: raise ValueError('Exact absent preimage/source changed')
            else:
                before = (HERE / 'evidence' / profile / path).read_bytes()
                if sha(before) != item['before_sha256'] or len(before) != item['before_bytes'] or item['replacements'] != [[before.decode('utf-8'), target.decode('utf-8')]]: raise ValueError('Exact existing source delta changed')
                if profile == 'owner_a7' or path != 'member/notifications.php':
                    if sha(before) != canonical['before_sha256'] or len(before) != canonical['before_bytes']: raise ValueError('Canonical baseline changed')
                else:
                    parent = (HERE / 'evidence/owner_a7' / path).read_bytes()
                    if sha(parent) != link['after_sha256']: raise ValueError('Reviewed owner link target changed')
                    for old, new in reversed(link['replacements']):
                        if parent.count(new.encode('utf-8')) != 1: raise ValueError('Owner link reverse anchor changed')
                        parent = parent.replace(new.encode('utf-8'), old.encode('utf-8'), 1)
                    if parent != before or sha(before) != link['before_sha256']: raise ValueError('Pre-A7 baseline derivation changed')
    if sum(item['before_sha256'] is None for item in runtime[VARIANTS[0]].values()) != 5: raise ValueError('Expected exactly five new code paths')
    for path in OWNER_PATHS:
        item = owner[path]; row = owner_fixture[path]
        before = (HERE / 'evidence/owner_before' / path).read_bytes(); target = (HERE / 'evidence/owner_after' / path).read_bytes()
        if item['replacements'] != row['replacements'] or sha(before) != row['before_sha256'] or sha(target) != row['after_sha256']: raise ValueError('A5 payload changed')
        if sha(before) != item['before_sha256'] or len(before) != item['before_bytes'] or sha(target) != item['after_sha256'] or len(target) != item['after_bytes']: raise ValueError('A5 exact tuple changed')
    if prerequisite != {'path': 'lib/bootstrap.php', 'sha256': 'd4eecc7375f6e678632b8b88fb8c64faaba6ac43513a59bae42fe673505bc263', 'bytes': 24274}: raise ValueError('Read-only bootstrap prerequisite changed')
    bootstrap = (HERE / 'evidence/prerequisite/lib/bootstrap.php').read_bytes()
    if sha(bootstrap) != prerequisite['sha256'] or len(bootstrap) != prerequisite['bytes'] or prerequisite['path'] in set(paths) | set(owner): raise ValueError('Bootstrap evidence/scope changed')
    return raw, manifest, runtime, owner, prerequisite


def owner_engine(raw, files):
    source = raw.decode('utf-8')
    source = once(source, "BACKUPS = Path('/home/bobsome1/kcmc-minimal-repair-backups')", "BACKUPS = Path('/home/bobsome1/kcmc-workflows-owner-backups')")
    source = once(source, "RELEASE = 'kcmc-minimal-repair-20261014'", "RELEASE = 'kcmc-workflows-owner-20261015'")
    source = once(source, "PATHS = ('lib/timeclock.php', 'member/activate.php', 'member/reset-password.php')", 'PATHS = ' + repr(OWNER_PATHS))
    line = 'FILES = json.loads(' + repr(json.dumps(files, separators=(',', ':'))) + ')'
    source, count = re.subn(r'^FILES = json\.loads\(.*\)$', lambda unused: line, source, flags=re.MULTILINE)
    if count != 1: raise ValueError('Frozen owner inventory line changed')
    start = source.index('def lint(session):\n'); end = source.index('\n\ndef bundle_lease(', start)
    lint = r'''def lint(session):
    version = subprocess.check_output([PHP, '-n', '-v'], stderr=subprocess.STDOUT, timeout=15)
    require(re.match(br'\APHP 8\.2\.[0-9]+\b', version) is not None, 'Fixed PHP8.2 CLI required')
    for index, path in enumerate(PATHS):
        staged = Path(session) / ('stage-' + str(index) + '.code')
        content, info = read(staged)
        require(info['mode'] == 0o600 and info['sha256'] == FILES[path]['after_sha256'] and info['bytes'] == FILES[path]['after_bytes'], 'Pinned stage bytes changed')
        subprocess.check_output([PHP, '-n', '-l', str(staged)], stderr=subprocess.STDOUT, timeout=15)
'''
    source = source[:start] + lint.rstrip('\n') + source[end:]
    if source.count("+ '.php'") != 5: raise ValueError('Frozen suffix inventory changed')
    return source.replace("+ '.php'", "+ '.code'") + '\n\n' + (HERE / 'owner-dependency-extension.py').read_text()


def build():
    raw, manifest, runtime, owner, prerequisite = verify_inputs()
    payload = {}; owner_source = owner_engine(raw, owner)
    payload['owner'] = [owner_source, sha(owner_source.encode('utf-8'))]
    extension = (HERE / 'extension.py').read_text(); paths = tuple(manifest['paths'])
    dependencies = {path: tuple(values) for path, values in manifest['dependencies'].items()}
    for profile in VARIANTS:
        source = raw.decode('utf-8') + '\n\nfrozen_move_code = move_code\n' + extension
        source += '\nAPP = Path(\'/home/bobsome1/public_html/kcmc-connect\')\n'
        source += 'BACKUPS = Path(' + repr('/home/bobsome1/kcmc-workflows-' + profile + '-backups') + ')\n'
        source += 'RELEASE = ' + repr('kcmc-workflows-20261015-' + profile) + '\n'
        source += 'PATHS = ' + repr(paths) + '\n'
        source += 'FILES = json.loads(' + repr(json.dumps(runtime[profile], separators=(',', ':'))) + ')\n'
        source += 'DEPENDENCIES = ' + repr(dependencies) + '\n'
        payload[profile] = [source, sha(source.encode('utf-8'))]
    wrapper = (HERE / 'wrapper.py.in').read_text()
    for marker, value in [('# EMBEDDED_ENGINES', 'EMBEDDED = ' + repr(payload)), ('# EMBEDDED_PREREQUISITE', 'PREREQUISITE = ' + repr(prerequisite))]:
        if wrapper.count(marker) != 1: raise ValueError('Embedding marker changed')
        wrapper = wrapper.replace(marker, value)
    (HERE / 'installer.py').write_text(wrapper)
    proof = {'frozen_engine_sha256': FROZEN_SHA256, 'baseline_commit': BASE_COMMIT, 'source_commit': SOURCE_COMMIT, 'input_sha256': PINS,
        'embedded_engines': {group: value[1] for group, value in payload.items()}, 'installer_sha256': sha(wrapper.encode('utf-8')),
        'groups': {'owner': list(OWNER_PATHS), 'workflows': list(paths)}, 'read_only_prerequisite': prerequisite,
        'owner_policy': 'Frozen existing-file engine with metadata, .code stage suffix, pinned stage lint, and explicit existing-only provider_needed/restore_owned recovery revision; unchanged mover and journal schema.',
        'workflows_policy': 'Explicit finite ten-function absence/dependency extension; frozen existing-file mover retained unchanged. Revised provider_needed/restore_owned revalidate completed consumer leases before each provider rollback and final callback.',
        'original_package_checksums_sha256': '0d74e36e21b117ebbd4bdd73bc60778036b6d416d0cc372c7a129803d6448ee3',
        'result_policy': 'Preserve initially captured common-after leases across no-op; verify journal leases and result files after context exit and at final two-group boundary.',
        'coordination': 'Preflight both independent groups before apply; owner then workflows; preserve/report prior verified group success on a later failure; common after tuple coalesced.'}
    (HERE / 'provenance.json').write_text(json.dumps(proof, indent=2) + '\n')
    print('Derived installer SHA256 ' + sha(wrapper.encode('utf-8')))


if __name__ == '__main__': build()
