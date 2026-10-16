#!/usr/bin/env python3
"""Derive only from an exact separately reviewed five-file Git delta."""
from __future__ import print_function
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BASE_COMMIT = 'b0321c38d9750314c7d56896d3a818b6d7680228'
SOURCE_COMMIT = '05cb55e87f3157c9f0cdf0051da19bd5361e7c99'
THEME_COMMIT = '8f03172354f6bc342c6090a186a440cc63d73c8d'
THEME_SHA256 = '5a180d96ed045ea3a1bca541865ba0b2d3ae2e4175fde14ecd02dba7a72d3f7b'
FROZEN_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
EXTENSION_SHA256 = 'a09f1d2e69f20a057be712b7c21bae3ec174e2faea60c9eb1dcbf2fca985d6c2'
PATHS = ('lib/timeclock.php', 'member/timeclock.php', 'admin/timecards.php',
         'admin/timecards-export.php', 'admin/timecards-print.php')
DEPENDENCIES = {path: ('lib/timeclock.php',) for path in PATHS[1:]}
PINS = {'wrapper.py.in': '202f14e248d35d1a33890a512bc85826b606581ff06745e8aec9bb41050bb101', 'coordinator.py.in': '9461f4649070cdbf36a79f7c3aa41661a9a631609aa2f4da3dbbff7d405206b7', 'source-runtime-reviewed.json': 'deea6aa57c73bfde52882774f6f66fdcfcf195a0d2a1cff1a0c9719a3deea1f3', 'runtime-reviewed.json': 'c1c60ae63706c9880817ce865d7cdb18e86a15642dff2b48699a0fd9e05d3036', 'prerequisites-reviewed.json': '9bfee4e66e64e3e3ecb936f112a58abd8ce2b9323530cc473da85daf697ae2f1', 'public-variants-reviewed.json': '2ae894b5798f9a06a82a62e53675170057da0d4ff6cbb3fcd271a78091f65c61', 'pretheme-targets-reviewed.json': '8211663e1b813b1ee4b6af67e14c2e7ef4e27737620a7f59a7fb237700881fc8'}


def sha(content): return hashlib.sha256(content).hexdigest()


def verify_inputs(allow_unapproved=False):
    approved = isinstance(SOURCE_COMMIT, str) and re.match(r'\A[0-9a-f]{40}\Z', SOURCE_COMMIT)
    if (not approved and not (allow_unapproved and SOURCE_COMMIT is None)) or not PINS:
        raise ValueError('Exact source review and input pins are not frozen; no installer generated')
    for path, expected in PINS.items():
        if sha((HERE / path).read_bytes()) != expected: raise ValueError('Pinned package input changed: ' + path)
    raw = (HERE / 'frozen-minimal-installer.py').read_bytes()
    extension = (HERE / 'extension.py').read_bytes()
    if sha(raw) != FROZEN_SHA256 or sha(extension) != EXTENSION_SHA256:
        raise ValueError('Reviewed transaction engine or extension changed')
    source = json.loads((HERE / 'source-runtime-reviewed.json').read_text())
    runtime = json.loads((HERE / 'runtime-reviewed.json').read_text())
    guards = json.loads((HERE / 'prerequisites-reviewed.json').read_text())
    variants = json.loads((HERE / 'public-variants-reviewed.json').read_text())
    pretheme = json.loads((HERE / 'pretheme-targets-reviewed.json').read_text())
    if (source['baseline_commit'], source['source_commit'], tuple(source['paths'])) != (BASE_COMMIT, SOURCE_COMMIT, PATHS):
        raise ValueError('Exact source anchors or five-file scope changed')
    if tuple(runtime) != PATHS or set(pretheme) != set(PATHS) or set(guards) & set(PATHS):
        raise ValueError('Target/read-only/pre-theme inventory changed')
    if set(source['files']) != set(PATHS) or len(guards) != 57:
        raise ValueError('Canonical target metadata or complete read-only inventory changed')
    if tuple(variants) != ('main', 'livecalendar') or not guards:
        raise ValueError('Finite themed public variants and complete guards required')
    for path, row in runtime.items():
        if source['files'][path] != {key: row[key] for key in
                ('before_sha256', 'before_bytes', 'after_sha256', 'after_bytes')}:
            raise ValueError('Canonical target metadata changed: ' + path)
        before = (HERE / 'evidence/before' / path).read_bytes()
        after = (HERE / 'evidence/after' / path).read_bytes()
        if (sha(before), len(before), sha(after), len(after)) != tuple(row[key] for key in
                ('before_sha256', 'before_bytes', 'after_sha256', 'after_bytes')):
            raise ValueError('Exact existing-code images changed: ' + path)
        if before == after or row['replacements'] != [[before.decode('utf-8'), after.decode('utf-8')]]:
            raise ValueError('Exact existing-code replacement changed: ' + path)
        old = (HERE / 'evidence/pretheme' / path).read_bytes()
        if (sha(old), len(old)) != (pretheme[path]['sha256'], pretheme[path]['bytes']):
            raise ValueError('Fixed pre-theme classification image changed: ' + path)
    all_guards = [('', guards)] + [(name, row['guards']) for name, row in variants.items()]
    for name, rows in all_guards:
        if set(rows) & set(PATHS): raise ValueError('A read-only guard overlaps write inventory')
        for path, row in rows.items():
            if path.startswith(('data/', '.git/')) or path in ('config.php', 'config.example.php'):
                raise ValueError('Private/configuration guard is forbidden')
            data = (HERE / ('evidence/public/' + name if name else 'evidence/prerequisite') / path).read_bytes()
            if (sha(data), len(data)) != (row['sha256'], row['bytes']):
                raise ValueError('Exact read-only guard changed: ' + path)
    for row in variants.values():
        if set(row['guards']) != set(('index.php', 'public-presentation.css', 'sw.js')) or set(row['guards']) & set(guards):
            raise ValueError('Exact public read-only bundle changed')
    return raw, extension, source, runtime, guards, variants, pretheme


def build(candidate=False):
    raw, extension, source, runtime, guards, variants, pretheme = verify_inputs(allow_unapproved=candidate)
    engine = raw.decode('utf-8') + '\n\nfrozen_move_code = move_code\n' + extension.decode('utf-8')
    engine += "\nAPP = Path('/home/bobsome1/public_html/kcmc-connect')\n"
    engine += "BACKUPS = Path('/home/bobsome1/kcmc-manual-timeclock-backups')\n"
    engine += "RELEASE = 'kcmc-manual-timeclock-20261016'\n"
    engine += 'PATHS = ' + repr(PATHS) + '\n'
    engine += 'FILES = json.loads(' + repr(json.dumps(runtime, separators=(',', ':'))) + ')\n'
    engine += 'DEPENDENCIES = ' + repr(DEPENDENCIES) + '\n'
    wrapper = (HERE / 'wrapper.py.in').read_text()
    for marker, value in [('# EMBEDDED_ENGINE', 'EMBEDDED = ' + repr((engine, sha(engine.encode('utf-8'))))),
                          ('# EMBEDDED_PREREQUISITES', 'PREREQUISITES = ' + repr(guards)),
                          ('# EMBEDDED_VARIANTS', 'VARIANTS = ' + repr(variants)),
                          ('# EMBEDDED_PRETHEME_TARGETS', 'PRETHEME_TARGETS = ' + repr(pretheme))]:
        if wrapper.count(marker) != 1: raise ValueError('Exact wrapper embedding marker changed')
        wrapper = wrapper.replace(marker, value)
    (HERE / ('candidate-installer.py' if candidate else 'installer.py')).write_text(wrapper)
    coordinator = (HERE / 'coordinator.py.in').read_text()
    if coordinator.count('# MANUAL_INSTALLER_SHA256') != 1:
        raise ValueError('Coordinator embedding marker changed')
    coordinator = coordinator.replace('# MANUAL_INSTALLER_SHA256',
        'MANUAL_SHA256 = ' + repr(sha(wrapper.encode('utf-8'))))
    (HERE / ('candidate-coordinator.py' if candidate else 'coordinator.py')).write_text(coordinator)
    proof = {'baseline_commit': BASE_COMMIT, 'source_commit': SOURCE_COMMIT,
        'prerequisite_theme_commit': THEME_COMMIT, 'prerequisite_theme_installer_sha256': THEME_SHA256,
        'frozen_engine_sha256': FROZEN_SHA256, 'corrected_extension_sha256': EXTENSION_SHA256,
        'input_sha256': PINS, 'engine_sha256': sha(engine.encode('utf-8')),
        'installer_sha256': sha(wrapper.encode('utf-8')), 'coordinator_sha256': sha(coordinator.encode('utf-8')),
        'paths': list(PATHS), 'dependencies': {path: list(providers) for path, providers in DEPENDENCIES.items()},
        'new_paths': [], 'read_only_prerequisites': guards, 'public_variants': variants,
        'preserved': 'Configuration, private/editorial records, actual punches, schedule, payroll delivery, roles and hosting repository.'}
    if candidate: proof['unpublished_candidate_only'] = True
    (HERE / ('candidate-provenance.json' if candidate else 'provenance.json')).write_text(json.dumps(proof, indent=2) + '\n')
    print(('UNPUBLISHED CANDIDATE ' if candidate else '') + 'Derived manual time clock installer SHA256 ' + sha(wrapper.encode('utf-8')))


if __name__ == '__main__': build()
