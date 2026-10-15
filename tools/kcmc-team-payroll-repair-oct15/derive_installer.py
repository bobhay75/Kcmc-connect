#!/usr/bin/env python3
"""Reproduce the single fixed team/payroll hosting installer from reviewed bytes."""
from __future__ import print_function
import base64
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
FROZEN_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
FROZEN_EXTENSION_SHA256 = '78eb5ffa7cb36ce34dfa6cdf8af80bc11c304f0b7b25bcf75536f893952d0648'
EXTENSION_SHA256 = 'a09f1d2e69f20a057be712b7c21bae3ec174e2faea60c9eb1dcbf2fca985d6c2'
BASE_COMMIT = '3317aed0c4b6a1619f8f68cced6a73fc4a245055'
CORE_SOURCE_COMMIT = 'ba7b5df314e1be604d46443025d41b1c8fe732a4'
SOURCE_COMMIT = '131071542f7985eb5d483d8123764df9319a7e37'
PINS = {'wrapper.py.in': '7ff2ca7dbc19a8a0ef5d480928248f205500bfaa99b60664694f81672f11683b', 'extension.py': 'a09f1d2e69f20a057be712b7c21bae3ec174e2faea60c9eb1dcbf2fca985d6c2', 'frozen-workflows-extension.py': '78eb5ffa7cb36ce34dfa6cdf8af80bc11c304f0b7b25bcf75536f893952d0648', 'runtime-reviewed.json': 'c0aaf002e6e45c7cf5a9d711dd26d28376949eb1688af3eb8fd7a6eb3d64e5a5', 'source-runtime-reviewed.json': '3a86a5bdab7a1bad85ab56a572973da9474fa13ad3ec88732f322954d3530fa5', 'prerequisites-reviewed.json': 'acd213f2bbf57e54f0e2e03635423aadbbb62750d6221a2f0025949a84e13c11', 'core-after-reviewed.json': '5815a392c8cf255e47e4adb25663d32a3139ffeb559ec0f6851e8a2e7cb1a3a8'}
BOOTSTRAP_BEFORE_SHA256 = 'd4eecc7375f6e678632b8b88fb8c64faaba6ac43513a59bae42fe673505bc263'


def sha(content): return hashlib.sha256(content).hexdigest()


def verify_inputs(allow_unapproved=False):
    approved = isinstance(SOURCE_COMMIT,str) and re.match(r'\A[0-9a-f]{40}\Z',SOURCE_COMMIT) is not None
    if (not approved and not (allow_unapproved and SOURCE_COMMIT is None)) or not PINS:
        raise ValueError('The source commit and reviewed inputs have not been frozen; no installer generated')
    for path, expected in PINS.items():
        if sha((HERE / path).read_bytes()) != expected: raise ValueError('Pinned package input changed: ' + path)
    raw = (HERE / 'frozen-minimal-installer.py').read_bytes()
    if sha(raw) != FROZEN_SHA256: raise ValueError('Frozen existing-file engine changed')
    extension = (HERE / 'extension.py').read_bytes()
    frozen_extension = (HERE / 'frozen-workflows-extension.py').read_bytes()
    if sha(frozen_extension) != FROZEN_EXTENSION_SHA256 or sha(extension) != EXTENSION_SHA256:
        raise ValueError('Reviewed absence/dependency extension or its frozen predecessor changed')
    old_ast = ast.parse(frozen_extension.decode('utf-8')); new_ast = ast.parse(extension.decode('utf-8'))
    if len(old_ast.body) != len(new_ast.body): raise ValueError('Finite extension revision scope changed')
    changed = []
    for before, after in zip(old_ast.body, new_ast.body):
        if ast.dump(before) != ast.dump(after):
            if not isinstance(before,ast.FunctionDef) or not isinstance(after,ast.FunctionDef) or before.name != after.name:
                raise ValueError('Finite extension nonfunction policy changed')
            changed.append(before.name)
    if changed != ['provider_needed','restore_owned']: raise ValueError('Finite extension override scope changed')
    source = json.loads((HERE / 'source-runtime-reviewed.json').read_text())
    runtime = json.loads((HERE / 'runtime-reviewed.json').read_text())
    prerequisites = json.loads((HERE / 'prerequisites-reviewed.json').read_text())
    core = json.loads((HERE / 'core-after-reviewed.json').read_text())
    if source['baseline_commit'] != BASE_COMMIT or source['source_commit'] != SOURCE_COMMIT:
        raise ValueError('Source membership anchors changed')
    paths = tuple(source['paths'])
    if len(paths) != 23 or len(set(paths)) != 23 or tuple(runtime) != paths or set(source['files']) != set(paths):
        raise ValueError('Exact live target inventory changed')
    if len(core) != 21 or len(prerequisites) != 15 or set(core) != set(prerequisites) | (set(core) & set(paths)):
        raise ValueError('Complete core-after prerequisite coverage changed')
    if set(prerequisites) & set(paths) or len(set(core) & set(paths)) != 6:
        raise ValueError('Read-only and normal leased target scopes changed')
    if paths[0] != 'lib/bootstrap.php' or runtime[paths[0]]['before_sha256'] != BOOTSTRAP_BEFORE_SHA256:
        raise ValueError('Bootstrap must be a known existing transaction provider')
    for path in paths:
        if path in ('config.php', 'config.example.php', 'index.php', 'public-presentation.css', 'sw.js') or path.startswith(('data/', '.git/')):
            raise ValueError('Forbidden live write target')
        row = runtime[path]; canonical = source['files'][path]
        target = (HERE / 'evidence/after' / path).read_bytes()
        if sha(target) != row['after_sha256'] or len(target) != row['after_bytes']:
            raise ValueError('Target code bytes changed: ' + path)
        if any(row[key] != canonical[key] for key in ('before_sha256','before_bytes','after_sha256','after_bytes')):
            raise ValueError('Canonical target metadata changed: ' + path)
        if row['before_sha256'] is None:
            if row['before_bytes'] != 0 or row['replacements'] != [] or base64.b64decode(row['after_base64'].encode('ascii'),validate=True) != target:
                raise ValueError('Exact new-file payload changed: ' + path)
        else:
            before = (HERE / 'evidence/before' / path).read_bytes()
            if sha(before) != row['before_sha256'] or len(before) != row['before_bytes'] or row['replacements'] != [[before.decode('utf-8'),target.decode('utf-8')]]:
                raise ValueError('Exact existing source delta changed: ' + path)
        if path in core and (row['before_sha256'] != core[path]['sha256'] or row['before_bytes'] != core[path]['bytes']):
            raise ValueError('An overlapping core path no longer proves core-after: ' + path)
    if sum(row['before_sha256'] is None for row in runtime.values()) != 9:
        raise ValueError('Expected exactly nine new runtime paths')
    for path, row in prerequisites.items():
        content = (HERE / 'evidence/prerequisite' / path).read_bytes()
        if row != core[path] or sha(content) != row['sha256'] or len(content) != row['bytes']:
            raise ValueError('Read-only core prerequisite changed: ' + path)
    dependencies = source['dependencies']
    if not set(dependencies).issubset(set(paths)):
        raise ValueError('Dependency consumer scope changed')
    for path, providers in dependencies.items():
        if len(set(providers)) != len(providers) or any(parent not in paths or paths.index(parent) >= paths.index(path) for parent in providers):
            raise ValueError('Providers must precede consumers in exact order')
    return raw, extension, source, runtime, prerequisites, core


def build(candidate=False):
    raw, extension, source, runtime, prerequisites, core = verify_inputs(allow_unapproved=candidate)
    engine = raw.decode('utf-8') + '\n\nfrozen_move_code = move_code\n' + extension.decode('utf-8')
    engine += '\nAPP = Path(\'/home/bobsome1/public_html/kcmc-connect\')\n'
    engine += "BACKUPS = Path('/home/bobsome1/kcmc-team-payroll-backups')\n"
    engine += "RELEASE = 'kcmc-team-payroll-20261015'\n"
    engine += 'PATHS = ' + repr(tuple(source['paths'])) + '\n'
    engine += 'FILES = json.loads(' + repr(json.dumps(runtime,separators=(',',':'))) + ')\n'
    engine += 'DEPENDENCIES = ' + repr({path:tuple(values) for path,values in source['dependencies'].items()}) + '\n'
    wrapper = (HERE / 'wrapper.py.in').read_text()
    for marker,value in [('# EMBEDDED_ENGINE','EMBEDDED = ' + repr((engine,sha(engine.encode('utf-8'))))),
                         ('# EMBEDDED_PREREQUISITES','PREREQUISITES = ' + repr(prerequisites))]:
        if wrapper.count(marker) != 1: raise ValueError('Exact wrapper embedding marker changed')
        wrapper = wrapper.replace(marker,value)
    installer_name = 'candidate-installer.py' if candidate else 'installer.py'
    provenance_name = 'candidate-provenance.json' if candidate else 'provenance.json'
    (HERE / installer_name).write_text(wrapper)
    proof = {'baseline_commit':BASE_COMMIT,'source_commit':SOURCE_COMMIT,'core_source_commit':CORE_SOURCE_COMMIT,
        'frozen_engine_sha256':FROZEN_SHA256,'frozen_previous_extension_sha256':FROZEN_EXTENSION_SHA256,
        'finite_extension_sha256':EXTENSION_SHA256,'extension_revision_functions':['provider_needed','restore_owned'],'input_sha256':PINS,
        'engine_sha256':sha(engine.encode('utf-8')),'installer_sha256':sha(wrapper.encode('utf-8')),
        'paths':source['paths'],'new_paths':[path for path,row in runtime.items() if row['before_sha256'] is None],
        'read_only_prerequisites':prerequisites,'core_overlap':[path for path in source['paths'] if path in core],
        'bootstrap_policy':'Known existing target, normal installed/original lease, provider installed first; never a fixed read-only prerequisite.',
        'transaction_policy':'One complete bundle. Frozen existing-file mover and finite ten-function absence/dependency extension; explicit two-function recovery revision checks dependent original/installed/absent leases through provider rollback boundaries.',
        'prerequisite_policy':'15 unaffected core-after paths retain captured full identity/metadata leases through transaction, recovery and result boundaries. Six overlapping paths require exact core-after preimages.'}
    if candidate: proof['unpublished_candidate_only'] = True
    (HERE / provenance_name).write_text(json.dumps(proof,indent=2)+'\n')
    print(('UNPUBLISHED CANDIDATE ' if candidate else '') + 'Derived installer SHA256 ' + sha(wrapper.encode('utf-8')))


if __name__ == '__main__': build()
