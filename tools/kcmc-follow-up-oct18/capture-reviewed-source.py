#!/usr/bin/env python3
"""Capture exact approved Git source and preserve the installed public variant."""
from __future__ import print_function
import argparse
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PREFIX = 'KCMC-Connect-Phase6-Recreated/'
GUARDS = ('lib/bootstrap.php', 'lib/operations-owner.php', 'lib/push-subscriptions.php',
    'lib/screen-navigation.php', 'app-theme.css', 'app-navigation.js', 'styles.css',
    'api/push-subscription.php', 'admin/health.php', 'admin/home.php', 'member/index.php', 'app.js', 'manifest.webmanifest')


def git(*args): return subprocess.check_output(['git'] + list(args), cwd=str(ROOT))
def sha(data): return hashlib.sha256(data).hexdigest()
def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
def dump(path, value): write(path, (json.dumps(value, indent=2) + '\n').encode('utf-8'))


def homepage_edits(before, after):
    prior = before.decode('utf-8').splitlines(True); final = after.decode('utf-8').splitlines(True); edits = []
    groups = difflib.SequenceMatcher(a=prior, b=final, autojunk=False).get_grouped_opcodes(3)
    for group in groups:
        first, last = group[0], group[-1]
        old = ''.join(prior[first[1]:last[2]]); new = ''.join(final[first[3]:last[4]])
        if not old or before.decode('utf-8').count(old) != 1: raise ValueError('Nonunique homepage review anchor')
        edits.append([old, new])
    if not edits: raise ValueError('Missing homepage edits')
    return edits


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--source', required=True)
    parser.add_argument('--candidate',action='store_true',help='Capture unpublished bytes without freezing a release source')
    args = parser.parse_args(); source = args.source
    if not re.match(r'\A[0-9a-f]{40}\Z', source): raise ValueError('Exact source commit required')
    spec = importlib.util.spec_from_file_location('capture_derive', str(HERE/'derive_installer.py'))
    derive = importlib.util.module_from_spec(spec); spec.loader.exec_module(derive)
    if derive.SOURCE_COMMIT not in (None, source): raise ValueError('Frozen source changed')
    changed = git('diff','--name-only',derive.BASE_COMMIT,source,'--',PREFIX).decode().splitlines()
    if changed != sorted(PREFIX + path for path in derive.PATHS): raise ValueError('Source is not exactly six reviewed runtime files: ' + repr(changed))
    runtime = {}; files = {}
    for path in derive.PATHS:
        before, after = (git('show', ref + ':' + PREFIX + path) for ref in (derive.BASE_COMMIT, source))
        if before == after: raise ValueError('Unchanged write target')
        for ref in (derive.BASE_COMMIT, source):
            if git('ls-tree', ref, '--', PREFIX + path).split()[0] != b'100644': raise ValueError('Runtime mode changed')
        write(HERE/'evidence/before'/path,before); write(HERE/'evidence/after'/path,after)
        runtime[path] = derive.payload(before,after); files[path] = derive.metadata(before,after)
    guards = {}
    for path in GUARDS:
        before, after = (git('show', ref + ':' + PREFIX + path) for ref in (derive.BASE_COMMIT, source))
        if before != after: raise ValueError('Read-only dependency changed: ' + path)
        write(HERE/'evidence/prerequisite'/path,before); guards[path] = {'sha256':sha(before),'bytes':len(before)}
    variants = {}; edits = homepage_edits((HERE/'evidence/before/index.php').read_bytes(), (HERE/'evidence/after/index.php').read_bytes())
    installed = ROOT/'tools/kcmc-app-theme-oct15/evidence/public/livecalendar/index-after.php'
    if sha(installed.read_bytes()) != derive.LIVE_INDEX_SHA256: raise ValueError('Installed livecalendar source evidence changed')
    for name in ('main','livecalendar'):
        before = (HERE/'evidence/before/index.php').read_bytes() if name == 'main' else installed.read_bytes()
        after = before
        for old,new in edits:
            old,new = old.encode('utf-8'),new.encode('utf-8')
            if after.count(old) != 1: raise ValueError('Public variant anchor not unique: '+name)
            after = after.replace(old,new,1)
        write(HERE/'evidence/public'/name/'index-before.php',before); write(HERE/'evidence/public'/name/'index-after.php',after)
        public = {}
        for path in ('public-presentation.css','public-presentation.js'):
            data = git('show',derive.BASE_COMMIT+':'+PREFIX+path)
            write(HERE/'evidence/public'/name/path,data); public[path] = {'sha256':sha(data),'bytes':len(data)}
        variants[name] = {'index':derive.payload(before,after),'public_prerequisites':public}
    source_manifest = {'baseline_commit':derive.BASE_COMMIT,'source_commit':None if args.candidate else source,'paths':list(derive.PATHS),'files':files,
        'dependencies':{key:list(value) for key,value in derive.DEPENDENCIES.items()},'homepage_edits':edits}
    for name,value in (('runtime-reviewed.json',runtime),('source-runtime-reviewed.json',source_manifest),
                       ('prerequisites-reviewed.json',guards),('public-variants-reviewed.json',variants)):
        dump(HERE/name,value)
    pins = {name:sha((HERE/name).read_bytes()) for name in ('wrapper.py.in','source-runtime-reviewed.json',
        'runtime-reviewed.json','prerequisites-reviewed.json','public-variants-reviewed.json')}
    script=(HERE/'derive_installer.py').read_text();script=re.sub(r'^SOURCE_COMMIT = .*$', 'SOURCE_COMMIT = '+repr(None if args.candidate else source),script,flags=re.M)
    script=re.sub(r'^PINS = .*$', 'PINS = '+repr(pins),script,flags=re.M);(HERE/'derive_installer.py').write_text(script)
    print('CAPTURED exact six-file source '+source+'; main and livecalendar index variants preserved')


if __name__ == '__main__': main()
