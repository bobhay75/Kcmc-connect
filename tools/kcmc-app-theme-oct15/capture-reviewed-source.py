#!/usr/bin/env python3
"""Development-only capture of the exact Git source delta; never a host installer.

Capture must be reviewed and its hashes frozen in derive_installer.py separately.
--candidate reads the current working files and labels their source unapproved.
"""
from __future__ import print_function
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import derive_installer as derive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APP = ROOT / 'KCMC-Connect-Phase6-Recreated'
PREFIX = 'KCMC-Connect-Phase6-Recreated/'


def sha(content): return hashlib.sha256(content).hexdigest()


def git_bytes(reference, path, absent=False):
    object_name = reference + ':' + PREFIX + path
    exists = subprocess.call(['git', 'cat-file', '-e', object_name], cwd=str(ROOT),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    if not exists:
        if absent: return None
        raise ValueError('Expected canonical Git file is missing: ' + path)
    return subprocess.check_output(['git', 'show', object_name], cwd=str(ROOT))


def payload(before, after):
    row = {'before_sha256': sha(before) if before is not None else None,
           'before_bytes': len(before) if before is not None else 0,
           'after_sha256': sha(after), 'after_bytes': len(after),
           'replacements': [[before.decode('utf-8'), after.decode('utf-8')]] if before is not None else []}
    if before is None: row['after_base64'] = base64.b64encode(after).decode('ascii')
    return row


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--source-ref'); group.add_argument('--candidate', action='store_true')
    parser.add_argument('--homepage-edits', required=True)
    args = parser.parse_args()
    if args.source_ref and not re.match(r'\A[0-9a-f]{40}\Z', args.source_ref):
        raise ValueError('Source must be one exact reviewed commit')
    source_ref = args.source_ref
    edits = json.loads(Path(args.homepage_edits).read_text())
    if isinstance(edits, list) and edits and all(isinstance(pair, dict) and set(pair) == set(('before', 'after')) for pair in edits):
        edits = [[pair['before'], pair['after']] for pair in edits]
    if not isinstance(edits, list) or not edits or any(not isinstance(pair, list) or len(pair) != 2
            or not all(isinstance(value, str) and value for value in pair) for pair in edits):
        raise ValueError('Homepage edits must be reviewed nonempty unique old/new pairs')
    command = ['git', 'diff', '--name-only', derive.BASE_COMMIT]
    if source_ref: command.append(source_ref)
    command += ['--', PREFIX]
    changed = [path[len(PREFIX):] for path in subprocess.check_output(command, cwd=str(ROOT)).decode().splitlines()]
    paths = list(derive.PROVIDERS) + sorted(set(changed) - set(derive.PROVIDERS))
    if 'index.php' not in paths or any(not derive.safe_target(path) for path in paths):
        raise ValueError('Unexpected runtime write scope; review before capture')
    evidence = HERE / 'evidence'
    if evidence.exists(): shutil.rmtree(str(evidence))
    runtime = {}; canonical = {}
    for path in paths:
        before = git_bytes(derive.BASE_COMMIT, path, absent=True)
        after = git_bytes(source_ref, path) if source_ref else (APP / path).read_bytes()
        if before == after: raise ValueError('Unchanged target is not a release delta: ' + path)
        runtime[path] = payload(before, after)
        canonical[path] = {key: runtime[path][key] for key in ('before_sha256', 'before_bytes', 'after_sha256', 'after_bytes')}
        if before is not None: write(evidence / 'before' / path, before)
        write(evidence / 'after' / path, after)
    # These known current functional paths are read-only when absent from this
    # visual write inventory. They are never adopted from live private records.
    previous = ROOT / 'tools/kcmc-team-payroll-repair-oct15'
    core = json.loads((previous / 'core-after-reviewed.json').read_text())
    team = json.loads((previous / 'runtime-reviewed.json').read_text())
    functional_paths = set(core) | set(team) | set(('styles.css',))
    prerequisites = {}
    for path in sorted(functional_paths - set(paths)):
        before = git_bytes(derive.BASE_COMMIT, path)
        after = git_bytes(source_ref, path) if source_ref else (APP / path).read_bytes()
        if before != after: raise ValueError('Read-only baseline code changed unexpectedly: ' + path)
        prerequisites[path] = {'sha256': sha(before), 'bytes': len(before)}
        write(evidence / 'prerequisite' / path, before)
    fish_package = ROOT / 'tools/kcmc-fish-home-oct15'
    fish_manifest_bytes = (fish_package / 'runtime-reviewed.json').read_bytes()
    if sha(fish_manifest_bytes) != '5746e5f5c97cee32c0380ddae1de763c4b5bcd6f20da7c18c4e13325d6bfec3c':
        raise ValueError('Historical known livecalendar package changed')
    fish = json.loads(fish_manifest_bytes)['livecalendar']
    write(HERE / 'provenance/fish-livecalendar-reviewed.json', fish_manifest_bytes)
    variants = {}
    for name in ('main', 'livecalendar'):
        prior = {}
        for path in ('index.php', 'public-presentation.css', 'sw.js'):
            content = git_bytes(derive.BASE_COMMIT, path)
            if name == 'livecalendar':
                row = fish[path]; original = (fish_package / 'evidence/livecalendar' / path).read_bytes()
                write(HERE / 'provenance/fish-before' / path, original)
                if sha(original) != row['before_sha256'] or len(original) != row['before_bytes']:
                    raise ValueError('Historical source preimage changed: ' + path)
                content = original
                for old, new in row['replacements']:
                    old = old.encode('utf-8'); new = new.encode('utf-8')
                    if content.count(old) != 1: raise ValueError('Historical source edit is not unique: ' + path)
                    content = content.replace(old, new, 1)
                if sha(content) != row['after_sha256'] or len(content) != row['after_bytes']:
                    raise ValueError('Historical livecalendar reconstruction failed: ' + path)
            prior[path] = content
        transformed = prior['index.php']
        for old, new in edits:
            old = old.encode('utf-8'); new = new.encode('utf-8')
            if transformed.count(old) != 1: raise ValueError('Nonunique reviewed homepage edit: ' + name)
            transformed = transformed.replace(old, new, 1)
        if name == 'main' and transformed != (evidence / 'after/index.php').read_bytes():
            raise ValueError('Reviewed homepage edits do not reproduce the exact canonical source')
        write(evidence / 'public' / name / 'index-before.php', prior['index.php'])
        write(evidence / 'public' / name / 'index-after.php', transformed)
        public = {}
        for path in ('public-presentation.css', 'sw.js'):
            write(evidence / 'public' / name / path, prior[path])
            public[path] = {'sha256': sha(prior[path]), 'bytes': len(prior[path])}
        variants[name] = {'index': payload(prior['index.php'], transformed), 'public_prerequisites': public}
    dependencies = {derive.PROVIDERS[2]: list(derive.PROVIDERS[:2])}
    dependencies.update({path: list(derive.PROVIDERS) for path in paths[3:]})
    source = {'baseline_commit': derive.BASE_COMMIT, 'source_commit': source_ref,
              'paths': paths, 'files': canonical, 'dependencies': dependencies,
              'homepage_navigation_edits': edits}
    for name, value in [('source-runtime-reviewed.json', source), ('runtime-reviewed.json', runtime),
                        ('prerequisites-reviewed.json', prerequisites), ('public-variants-reviewed.json', variants)]:
        (HERE / name).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'candidate_only': args.candidate, 'source_commit': source_ref,
                      'targets': len(paths), 'new_providers': len(derive.PROVIDERS),
                      'read_only_functional_prerequisites': len(prerequisites),
                      'variant_after_sha256': {name: row['index']['after_sha256'] for name, row in variants.items()}}, indent=2))
    return 0


if __name__ == '__main__': raise SystemExit(main())
