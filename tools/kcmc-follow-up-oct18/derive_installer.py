#!/usr/bin/env python3
"""Derive the fixed six-file follow-up repair from separately reviewed source."""
from __future__ import print_function
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BASE_COMMIT = '4b108316a3865dba8583b30ec0dd8e2eeae6968e'
SOURCE_COMMIT = 'dda594646d834fe8959168a1d0928dfcd62e10bc'
FROZEN_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
EXTENSION_SHA256 = 'a09f1d2e69f20a057be712b7c21bae3ec174e2faea60c9eb1dcbf2fca985d6c2'
LIVE_INDEX_SHA256 = 'fe92b62285e9232f53d459f83d853138f46b3732a4ec12af356da102e9a98f5b'
THEME_PUBLIC_MANIFEST = 'tools/kcmc-app-theme-oct15/public-variants-reviewed.json'
THEME_PUBLIC_MANIFEST_SHA256 = 'db6663eeba6e249f28413a4e74f891b983df4bd41c622befd4bac3d129c401bf'
# The installed livecalendar stylesheet is historical evidence, not canonical main CSS.
# The public script was not changed by the theme release and is common to both bundles.
PUBLIC_BUNDLE_PINS = {
    'main': {
        'public-presentation.css': {'sha256': '640ba99c997867e7d3fec3a36d08f9992bfc295d224523f2a980f0bc57bdc4e2', 'bytes': 17129},
        'public-presentation.js': {'sha256': 'bfc4e7a6ab3cb11bae76a74be5d1cdc0912ae00e32f1d66bedf128ec7aabfcc9', 'bytes': 7250}},
    'livecalendar': {
        'public-presentation.css': {'sha256': 'b08824180406891f3ff784967dc507e62488b4cb9b12f3a81347731be61a5acb', 'bytes': 17233},
        'public-presentation.js': {'sha256': 'bfc4e7a6ab3cb11bae76a74be5d1cdc0912ae00e32f1d66bedf128ec7aabfcc9', 'bytes': 7250}}}
PATHS = ('sw.js', 'member/push-settings.js', 'member/notifications.php', 'admin/push.php', 'index.php', 'admin/operations.php')
DEPENDENCIES = {'member/push-settings.js': ('sw.js',), 'member/notifications.php': ('sw.js', 'member/push-settings.js'), 'admin/push.php': ('member/notifications.php',)}
PINS = {'wrapper.py.in': '272111f75d34ae364890c367df754d1409d681127167d42dabced481de641cc2', 'source-runtime-reviewed.json': '82158e6525bb8e8ca1d6708f5f2a7519149104b5419a718f3eb63064dea905db', 'runtime-reviewed.json': 'b667ea7ae9bef905cd56711dca87e9918e3757243b1cbffd7136b6c1f7813024', 'prerequisites-reviewed.json': 'c454fae8f365e5a3cda22db6842ab647907088fad74e80843ad5e942e6a935e6', 'public-variants-reviewed.json': 'b4260b97a8294ea61060fe489f9cfafe5862e7d592085c6cb5e35e27c70800f8'}


def sha(content): return hashlib.sha256(content).hexdigest()


def metadata(before, after):
    return {'before_sha256': sha(before), 'before_bytes': len(before), 'after_sha256': sha(after), 'after_bytes': len(after)}


def payload(before, after):
    value = metadata(before, after)
    value['replacements'] = [[before.decode('utf-8'), after.decode('utf-8')]]
    return value


def verify_inputs(allow_unapproved=False):
    for name, value in (('base', BASE_COMMIT), ('source', SOURCE_COMMIT)):
        if not (isinstance(value, str) and re.match(r'\A[0-9a-f]{40}\Z', value)):
            if not (allow_unapproved and value is None): raise ValueError('Exact ' + name + ' source commit is not frozen')
    if not PINS: raise ValueError('Reviewed package input pins are not frozen')
    for path, expected in PINS.items():
        if sha((HERE / path).read_bytes()) != expected: raise ValueError('Pinned package input changed: ' + path)
    raw = (HERE / 'frozen-minimal-installer.py').read_bytes(); extension = (HERE / 'extension.py').read_bytes()
    if (sha(raw), sha(extension)) != (FROZEN_SHA256, EXTENSION_SHA256):
        raise ValueError('Reviewed transaction engine or extension changed')
    source = json.loads((HERE / 'source-runtime-reviewed.json').read_text())
    runtime = json.loads((HERE / 'runtime-reviewed.json').read_text())
    guards = json.loads((HERE / 'prerequisites-reviewed.json').read_text())
    variants = json.loads((HERE / 'public-variants-reviewed.json').read_text())
    if (source['baseline_commit'], source['source_commit'], tuple(source['paths'])) != (BASE_COMMIT, SOURCE_COMMIT, PATHS):
        raise ValueError('Exact source anchors or fixed six-file scope changed')
    if tuple(runtime) != PATHS or set(source['files']) != set(PATHS) or not guards or set(guards) & set(PATHS):
        raise ValueError('Fixed target/read-only inventory changed')
    if source['dependencies'] != {key: list(value) for key, value in DEPENDENCIES.items()}:
        raise ValueError('Fixed source dependency graph changed')
    for path in PATHS:
        before = (HERE / 'evidence/before' / path).read_bytes(); after = (HERE / 'evidence/after' / path).read_bytes()
        if before == after or runtime[path] != payload(before, after) or source['files'][path] != metadata(before, after):
            raise ValueError('Exact existing-code images changed: ' + path)
    for path, row in guards.items():
        if path.startswith(('data/', '.git/')) or path in ('config.php', 'config.example.php'):
            raise ValueError('Private/configuration guard is forbidden')
        data = (HERE / 'evidence/prerequisite' / path).read_bytes()
        if (sha(data), len(data)) != (row['sha256'], row['bytes']): raise ValueError('Exact read-only guard changed: ' + path)
    if tuple(variants) != ('main', 'livecalendar'): raise ValueError('Exact public variants changed')
    for name, variant in variants.items():
        before = (HERE / 'evidence/public' / name / 'index-before.php').read_bytes()
        after = (HERE / 'evidence/public' / name / 'index-after.php').read_bytes()
        if before == after or variant['index'] != payload(before, after): raise ValueError('Public index bytes changed: ' + name)
        transformed = before
        for old, new in source['homepage_edits']:
            old, new = old.encode('utf-8'), new.encode('utf-8')
            if transformed.count(old) != 1: raise ValueError('Homepage edit is not unique: ' + name)
            transformed = transformed.replace(old, new, 1)
        if transformed != after: raise ValueError('Variant includes change beyond reviewed homepage edits: ' + name)
        if set(variant['public_prerequisites']) != set(('public-presentation.css', 'public-presentation.js')):
            raise ValueError('Fixed public bundle prerequisite scope changed')
        if variant['public_prerequisites'] != PUBLIC_BUNDLE_PINS[name]:
            raise ValueError('Independent canonical/historical public bundle pins changed: ' + name)
        for path, row in variant['public_prerequisites'].items():
            data = (HERE / 'evidence/public' / name / path).read_bytes()
            if (sha(data), len(data)) != (row['sha256'], row['bytes']): raise ValueError('Public bundle guard changed')
    if variants['main']['index'] != runtime['index.php']: raise ValueError('Canonical main variant changed')
    if variants['livecalendar']['index']['before_sha256'] != LIVE_INDEX_SHA256:
        raise ValueError('Installed livecalendar theme evidence changed')
    return raw, extension, source, runtime, guards, variants


def build(candidate=False):
    raw, extension, source, runtime, guards, variants = verify_inputs(allow_unapproved=candidate)
    engine = raw.decode('utf-8') + '\n\nfrozen_move_code = move_code\n' + extension.decode('utf-8')
    engine += "\nAPP = Path('/home/bobsome1/public_html/kcmc-connect')\n"
    engine += "BACKUPS = Path('/home/bobsome1/kcmc-follow-up-backups')\n"
    engine += "RELEASE = 'kcmc-follow-up-20261018'\n"
    engine += 'PATHS = ' + repr(PATHS) + '\n'
    engine += 'FILES = json.loads(' + repr(json.dumps(runtime, separators=(',', ':'))) + ')\n'
    engine += 'DEPENDENCIES = ' + repr(DEPENDENCIES) + '\n'
    wrapper = (HERE / 'wrapper.py.in').read_text()
    for marker, value in [('# EMBEDDED_ENGINE', 'EMBEDDED = ' + repr((engine, sha(engine.encode('utf-8'))))),
                          ('# EMBEDDED_PREREQUISITES', 'PREREQUISITES = ' + repr(guards)),
                          ('# EMBEDDED_VARIANTS', 'VARIANTS = ' + repr(variants))]:
        if wrapper.count(marker) != 1: raise ValueError('Wrapper embedding marker changed')
        wrapper = wrapper.replace(marker, value)
    prefix = 'candidate-' if candidate else ''
    (HERE / (prefix + 'installer.py')).write_text(wrapper)
    proof = {'baseline_commit': BASE_COMMIT, 'source_commit': SOURCE_COMMIT, 'frozen_engine_sha256': FROZEN_SHA256,
        'corrected_extension_sha256': EXTENSION_SHA256, 'input_sha256': PINS, 'engine_sha256': sha(engine.encode('utf-8')),
        'installer_sha256': sha(wrapper.encode('utf-8')), 'paths': list(PATHS), 'new_paths': [],
        'dependencies': {key: list(value) for key, value in DEPENDENCIES.items()}, 'read_only_prerequisites': guards,
        'public_variant_hashes': {name: {'index_before': row['index']['before_sha256'], 'index_after': row['index']['after_sha256'],
            'read_only': row['public_prerequisites']} for name, row in variants.items()},
        'historical_theme_evidence': {'commit': BASE_COMMIT, 'manifest_path': THEME_PUBLIC_MANIFEST,
            'manifest_sha256': THEME_PUBLIC_MANIFEST_SHA256,
            'stylesheet_path': 'tools/kcmc-app-theme-oct15/evidence/public/livecalendar/public-presentation.css',
            'stylesheet': PUBLIC_BUNDLE_PINS['livecalendar']['public-presentation.css']},
        'preserved': 'Configuration, keys, subscriptions, private/editorial records, time punches, payroll delivery, roles, cron and hosting repository.'}
    if candidate: proof['unpublished_candidate_only'] = True
    (HERE / (prefix + 'provenance.json')).write_text(json.dumps(proof, indent=2) + '\n')
    print(('UNPUBLISHED CANDIDATE ' if candidate else '') + 'Derived follow-up installer SHA256 ' + sha(wrapper.encode('utf-8')))


if __name__ == '__main__': build()
