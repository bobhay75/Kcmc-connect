#!/usr/bin/env python3
"""Reproduce the fixed theme/navigation installer from separately reviewed bytes."""
from __future__ import print_function
import base64
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BASE_COMMIT = 'b0c257edb8a42fc89fd6371c1bce7ee3efbd5ed9'
# Freeze only after the source review has a concrete, verified Git commit.
SOURCE_COMMIT = '091fdc0fab45654037a4ed09ce90c3443cb88db5'
FROZEN_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
EXTENSION_SHA256 = 'a09f1d2e69f20a057be712b7c21bae3ec174e2faea60c9eb1dcbf2fca985d6c2'
STYLES_SHA256 = '9941c7da64ae5f2a3eb3a45f97081a2af160e8a8fa50bc17f1b6eb8a8fbd4476'
PINS = {'wrapper.py.in': '868b285920d6a20aa78eb7360069a83ea47e613cd1b12a99c00919ce32b158dd', 'source-runtime-reviewed.json': 'c308519fb5e8e34c1dbc0bf6ef1cf66ab1c0f26d14d26d7fba2da5b2d3a4256c', 'runtime-reviewed.json': 'eefdcfcd3cb3b7436cd6ce63d38da6e0f7229c2a55d6f5ff525409843710b34a', 'prerequisites-reviewed.json': '4f39f972bd410300177d674872b6d18f61849e08bb1a159bdb0a7743daff7d4a', 'public-variants-reviewed.json': 'db6663eeba6e249f28413a4e74f891b983df4bd41c622befd4bac3d129c401bf'}
PROVIDERS = ('app-theme.css', 'app-navigation.js', 'lib/screen-navigation.php')
FORBIDDEN = ('config.php', 'config.example.php', '.htaccess', 'styles.css',
             'public-presentation.css', 'public-presentation.js', 'sw.js')


def sha(content): return hashlib.sha256(content).hexdigest()


def safe_target(path):
    return (isinstance(path, str) and not path.startswith('/') and '\\' not in path
            and all(part not in ('', '.', '..') for part in path.split('/'))
            and path not in FORBIDDEN and not path.startswith(('data/', 'assets/', '.git/'))
            and (path in PROVIDERS or path.endswith('.php')))


def verify_inputs(allow_unapproved=False):
    approved = isinstance(SOURCE_COMMIT, str) and re.match(r'\A[0-9a-f]{40}\Z', SOURCE_COMMIT) is not None
    if (not approved and not (allow_unapproved and SOURCE_COMMIT is None)) or not PINS:
        raise ValueError('Source review and exact input pins are not frozen; no release installer generated')
    for path, expected in PINS.items():
        if sha((HERE / path).read_bytes()) != expected:
            raise ValueError('Pinned package input changed: ' + path)
    raw = (HERE / 'frozen-minimal-installer.py').read_bytes()
    extension = (HERE / 'extension.py').read_bytes()
    if sha(raw) != FROZEN_SHA256 or sha(extension) != EXTENSION_SHA256:
        raise ValueError('Reviewed existing/absence/dependency transaction policy changed')
    source = json.loads((HERE / 'source-runtime-reviewed.json').read_text())
    runtime = json.loads((HERE / 'runtime-reviewed.json').read_text())
    prerequisites = json.loads((HERE / 'prerequisites-reviewed.json').read_text())
    variants = json.loads((HERE / 'public-variants-reviewed.json').read_text())
    if source['baseline_commit'] != BASE_COMMIT or source['source_commit'] != SOURCE_COMMIT:
        raise ValueError('Canonical source anchors changed')
    paths = tuple(source['paths'])
    if len(set(paths)) != len(paths) or tuple(runtime) != paths or set(source['files']) != set(paths):
        raise ValueError('Exact live target inventory changed')
    if paths[:3] != PROVIDERS or set(prerequisites) & set(paths):
        raise ValueError('Providers/prerequisites are not the fixed disjoint inventory')
    if not prerequisites or any(not safe_target(path) for path in paths):
        raise ValueError('Forbidden or empty release target scope')
    if prerequisites.get('styles.css', {}).get('sha256') != STYLES_SHA256:
        raise ValueError('Existing approved base stylesheet must remain a fixed read-only prerequisite')
    for path in paths:
        row = runtime[path]; canonical = source['files'][path]
        target = (HERE / 'evidence/after' / path).read_bytes()
        if sha(target) != row['after_sha256'] or len(target) != row['after_bytes']:
            raise ValueError('Target code bytes changed: ' + path)
        if any(row[key] != canonical[key] for key in ('before_sha256', 'before_bytes', 'after_sha256', 'after_bytes')):
            raise ValueError('Canonical target metadata changed: ' + path)
        if row['before_sha256'] is None:
            if path not in PROVIDERS or row['before_bytes'] != 0 or row['replacements'] != []:
                raise ValueError('Unexpected absent target: ' + path)
            if base64.b64decode(row['after_base64'].encode('ascii'), validate=True) != target:
                raise ValueError('Exact new-file payload changed: ' + path)
        else:
            before = (HERE / 'evidence/before' / path).read_bytes()
            if sha(before) != row['before_sha256'] or len(before) != row['before_bytes']:
                raise ValueError('Existing code preimage changed: ' + path)
            if before == target or row['replacements'] != [[before.decode('utf-8'), target.decode('utf-8')]]:
                raise ValueError('Exact existing-source delta changed: ' + path)
    if sum(row['before_sha256'] is None for row in runtime.values()) != len(PROVIDERS):
        raise ValueError('Only the three theme/navigation providers may be new')
    for path, row in prerequisites.items():
        if path in ('config.php', 'config.example.php') or path.startswith(('data/', '.git/')):
            raise ValueError('Private/configuration prerequisite is forbidden')
        content = (HERE / 'evidence/prerequisite' / path).read_bytes()
        if sha(content) != row['sha256'] or len(content) != row['bytes']:
            raise ValueError('Read-only code prerequisite changed: ' + path)
    if tuple(variants) != ('main', 'livecalendar'):
        raise ValueError('Exact recognized public variants changed')
    for name, variant in variants.items():
        row = variant['index']
        before = (HERE / 'evidence/public' / name / 'index-before.php').read_bytes()
        after = (HERE / 'evidence/public' / name / 'index-after.php').read_bytes()
        if row['before_sha256'] != sha(before) or row['before_bytes'] != len(before):
            raise ValueError('Public variant preimage changed: ' + name)
        if row['after_sha256'] != sha(after) or row['after_bytes'] != len(after):
            raise ValueError('Public variant afterimage changed: ' + name)
        if row['replacements'] != [[before.decode('utf-8'), after.decode('utf-8')]]:
            raise ValueError('Public variant exact replacement changed: ' + name)
        transformed = before
        for old, new in source['homepage_navigation_edits']:
            old = old.encode('utf-8'); new = new.encode('utf-8')
            if transformed.count(old) != 1: raise ValueError('Public navigation edit is not unique: ' + name)
            transformed = transformed.replace(old, new, 1)
        if transformed != after:
            raise ValueError('Public variant includes a change beyond reviewed navigation edits: ' + name)
        if set(variant['public_prerequisites']) != set(('public-presentation.css', 'sw.js')):
            raise ValueError('Complete public bundle prerequisite scope changed')
        for path, approved in variant['public_prerequisites'].items():
            content = (HERE / 'evidence/public' / name / path).read_bytes()
            if sha(content) != approved['sha256'] or len(content) != approved['bytes']:
                raise ValueError('Read-only public bundle bytes changed: ' + name + '/' + path)
    fish_bytes = (HERE / 'provenance/fish-livecalendar-reviewed.json').read_bytes()
    if sha(fish_bytes) != '5746e5f5c97cee32c0380ddae1de763c4b5bcd6f20da7c18c4e13325d6bfec3c':
        raise ValueError('Historical livecalendar source manifest changed')
    fish = json.loads(fish_bytes)['livecalendar']
    for path in ('index.php', 'public-presentation.css', 'sw.js'):
        before = (HERE / 'provenance/fish-before' / path).read_bytes(); row = fish[path]
        if sha(before) != row['before_sha256'] or len(before) != row['before_bytes']:
            raise ValueError('Historical public source preimage changed: ' + path)
        reconstructed = before
        for old, new in row['replacements']:
            old = old.encode('utf-8'); new = new.encode('utf-8')
            if reconstructed.count(old) != 1: raise ValueError('Historical public source edit is not unique')
            reconstructed = reconstructed.replace(old, new, 1)
        if sha(reconstructed) != row['after_sha256'] or len(reconstructed) != row['after_bytes']:
            raise ValueError('Historical livecalendar reconstruction changed: ' + path)
        current = (HERE / 'evidence/public/livecalendar' / ('index-before.php' if path == 'index.php' else path)).read_bytes()
        if current != reconstructed:
            raise ValueError('Known livecalendar baseline is not the exact historical installed tuple: ' + path)
    if variants['main']['index'] != runtime['index.php']:
        raise ValueError('Main public variant must equal the canonical source delta')
    dependencies = source['dependencies']
    if set(dependencies) != set(paths[2:]) or dependencies[PROVIDERS[2]] != list(PROVIDERS[:2]):
        raise ValueError('Navigation helper dependency scope changed')
    for path in paths[3:]:
        if dependencies[path] != list(PROVIDERS):
            raise ValueError('Every route must retain its complete provider set')
    return raw, extension, source, runtime, prerequisites, variants


def build(candidate=False):
    raw, extension, source, runtime, prerequisites, variants = verify_inputs(allow_unapproved=candidate)
    engine = raw.decode('utf-8') + '\n\nfrozen_move_code = move_code\n' + extension.decode('utf-8')
    engine += "\nAPP = Path('/home/bobsome1/public_html/kcmc-connect')\n"
    engine += "BACKUPS = Path('/home/bobsome1/kcmc-app-theme-backups')\n"
    engine += "RELEASE = 'kcmc-app-theme-20261015'\n"
    engine += 'PATHS = ' + repr(tuple(source['paths'])) + '\n'
    engine += 'FILES = json.loads(' + repr(json.dumps(runtime, separators=(',', ':'))) + ')\n'
    engine += 'DEPENDENCIES = ' + repr({path: tuple(values) for path, values in source['dependencies'].items()}) + '\n'
    wrapper = (HERE / 'wrapper.py.in').read_text()
    for marker, value in [('# EMBEDDED_ENGINE', 'EMBEDDED = ' + repr((engine, sha(engine.encode('utf-8'))))),
                          ('# EMBEDDED_PREREQUISITES', 'PREREQUISITES = ' + repr(prerequisites)),
                          ('# EMBEDDED_VARIANTS', 'VARIANTS = ' + repr(variants))]:
        if wrapper.count(marker) != 1: raise ValueError('Exact wrapper embedding marker changed')
        wrapper = wrapper.replace(marker, value)
    installer_name = 'candidate-installer.py' if candidate else 'installer.py'
    provenance_name = 'candidate-provenance.json' if candidate else 'provenance.json'
    (HERE / installer_name).write_text(wrapper)
    proof = {'baseline_commit': BASE_COMMIT, 'source_commit': SOURCE_COMMIT,
        'frozen_engine_sha256': FROZEN_SHA256, 'corrected_extension_sha256': EXTENSION_SHA256,
        'input_sha256': PINS, 'engine_sha256': sha(engine.encode('utf-8')),
        'installer_sha256': sha(wrapper.encode('utf-8')), 'paths': source['paths'],
        'new_paths': list(PROVIDERS), 'read_only_prerequisites': prerequisites,
        'public_variant_hashes': {name: {'index_before': row['index']['before_sha256'],
            'index_after': row['index']['after_sha256'], 'read_only': row['public_prerequisites']}
            for name, row in variants.items()},
        'transaction_policy': 'Exact complete tuple, unchanged frozen existing-file mover and corrected absent-file/dependency engine; providers first, consumers restored first; uncertain consumer retains all potentially needed providers.',
        'preserved': 'Configuration, private/editorial data, homepage, photos, original stylesheet, worker, hosting repository, schedule, payroll and role settings.'}
    if candidate: proof['unpublished_candidate_only'] = True
    (HERE / provenance_name).write_text(json.dumps(proof, indent=2) + '\n')
    print(('UNPUBLISHED CANDIDATE ' if candidate else '') + 'Derived installer SHA256 ' + sha(wrapper.encode('utf-8')))


if __name__ == '__main__': build()
