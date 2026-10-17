#!/usr/bin/env python3
"""Derive a one-file health UI repair from exact independently reviewed source."""
from __future__ import print_function
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BASE_COMMIT = '8f25cf66b86d9bada85077867bc52436cdaced4f'
SOURCE_COMMIT = '6ca96d7d7531a8a42c497af8d4452e2997d45995'
FROZEN_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
EXTENSION_SHA256 = 'a09f1d2e69f20a057be712b7c21bae3ec174e2faea60c9eb1dcbf2fca985d6c2'
BEFORE_SHA256 = '600c22ea31fc8cd340d819e3356ca5eef42e3d8bd64897500a92aa988364e5a9'
PATHS = ('admin/health.php',)
DEPENDENCIES = {}
PINS = {'wrapper.py.in': 'cd6d5a4121e6950b715f64efaadf8599e13080490853d5877418db7add7ced5d', 'source-runtime-reviewed.json': '1a0222e24af37e8b0ab6fb49be4294d78a7ea064039e5471f49ad0dd7f6caaf7', 'runtime-reviewed.json': '6b8507aed5e061017219c9aeb011fff05c37227b505fcbc28f7fdbb90f42b4d1', 'prerequisites-reviewed.json': '82cd666f5dd1fffc44d6f2494f18afa14522a48af5727978cd8877dde84b11dd'}


def sha(content): return hashlib.sha256(content).hexdigest()


def verify_inputs(allow_unapproved=False):
    for name, value in (('base', BASE_COMMIT), ('source', SOURCE_COMMIT)):
        if not (isinstance(value, str) and re.match(r'\A[0-9a-f]{40}\Z', value)):
            if not (allow_unapproved and value is None):
                raise ValueError('Exact ' + name + ' review commit is not frozen')
    if not PINS: raise ValueError('Reviewed package input pins are not frozen')
    for path, expected in PINS.items():
        if sha((HERE / path).read_bytes()) != expected:
            raise ValueError('Pinned package input changed: ' + path)
    raw = (HERE / 'frozen-minimal-installer.py').read_bytes()
    extension = (HERE / 'extension.py').read_bytes()
    if (sha(raw), sha(extension)) != (FROZEN_SHA256, EXTENSION_SHA256):
        raise ValueError('Reviewed transaction engine or extension changed')
    source = json.loads((HERE / 'source-runtime-reviewed.json').read_text())
    runtime = json.loads((HERE / 'runtime-reviewed.json').read_text())
    guards = json.loads((HERE / 'prerequisites-reviewed.json').read_text())
    if (source['baseline_commit'], source['source_commit'], tuple(source['paths'])) != (BASE_COMMIT, SOURCE_COMMIT, PATHS):
        raise ValueError('Exact source anchors or one-file scope changed')
    if tuple(runtime) != PATHS or set(source['files']) != set(PATHS) or not guards or set(guards) & set(PATHS):
        raise ValueError('Fixed target/read-only inventory changed')
    for path, row in runtime.items():
        if source['files'][path] != {key: row[key] for key in
                ('before_sha256', 'before_bytes', 'after_sha256', 'after_bytes')}:
            raise ValueError('Canonical target metadata changed: ' + path)
        before = (HERE / 'evidence/before' / path).read_bytes()
        after = (HERE / 'evidence/after' / path).read_bytes()
        if (sha(before), len(before), sha(after), len(after)) != tuple(row[key] for key in
                ('before_sha256', 'before_bytes', 'after_sha256', 'after_bytes')):
            raise ValueError('Exact existing-code images changed: ' + path)
        if sha(before) != BEFORE_SHA256 or before == after or row['replacements'] != [[before.decode('utf-8'), after.decode('utf-8')]]:
            raise ValueError('Exact installed preimage or reviewed replacement changed')
    for path, row in guards.items():
        if path.startswith(('data/', '.git/')) or path in ('config.php', 'config.example.php'):
            raise ValueError('Private/configuration guard is forbidden')
        data = (HERE / 'evidence/prerequisite' / path).read_bytes()
        if (sha(data), len(data)) != (row['sha256'], row['bytes']):
            raise ValueError('Exact read-only guard changed: ' + path)
    return raw, extension, source, runtime, guards


def build(candidate=False):
    raw, extension, source, runtime, guards = verify_inputs(allow_unapproved=candidate)
    engine = raw.decode('utf-8') + '\n\nfrozen_move_code = move_code\n' + extension.decode('utf-8')
    engine += "\nAPP = Path('/home/bobsome1/public_html/kcmc-connect')\n"
    engine += "BACKUPS = Path('/home/bobsome1/kcmc-health-actions-backups')\n"
    engine += "RELEASE = 'kcmc-health-actions-20261017'\n"
    engine += 'PATHS = ' + repr(PATHS) + '\n'
    engine += 'FILES = json.loads(' + repr(json.dumps(runtime, separators=(',', ':'))) + ')\n'
    engine += 'DEPENDENCIES = {}\n'
    wrapper = (HERE / 'wrapper.py.in').read_text()
    for marker, value in [('# EMBEDDED_ENGINE', 'EMBEDDED = ' + repr((engine, sha(engine.encode('utf-8'))))),
                          ('# EMBEDDED_PREREQUISITES', 'PREREQUISITES = ' + repr(guards))]:
        if wrapper.count(marker) != 1: raise ValueError('Exact wrapper embedding marker changed')
        wrapper = wrapper.replace(marker, value)
    (HERE / ('candidate-installer.py' if candidate else 'installer.py')).write_text(wrapper)
    proof = {'baseline_commit': BASE_COMMIT, 'source_commit': SOURCE_COMMIT,
        'frozen_engine_sha256': FROZEN_SHA256, 'corrected_extension_sha256': EXTENSION_SHA256,
        'input_sha256': PINS, 'engine_sha256': sha(engine.encode('utf-8')),
        'installer_sha256': sha(wrapper.encode('utf-8')), 'paths': list(PATHS), 'dependencies': {},
        'new_paths': [], 'read_only_prerequisites': guards,
        'preserved': 'Configuration, private/editorial records, time punches, payroll delivery, roles and hosting repository.'}
    if candidate: proof['unpublished_candidate_only'] = True
    (HERE / ('candidate-provenance.json' if candidate else 'provenance.json')).write_text(json.dumps(proof, indent=2) + '\n')
    print(('UNPUBLISHED CANDIDATE ' if candidate else '') + 'Derived one-file health actions installer SHA256 ' + sha(wrapper.encode('utf-8')))


if __name__ == '__main__': build()
