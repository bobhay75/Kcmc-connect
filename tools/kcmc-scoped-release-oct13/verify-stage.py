#!/usr/bin/env python3
"""Validate the exact reviewed runtime with PHP 8.2; use temporary CI files only."""
import importlib.util
import os
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location('reviewed_stage', str(HERE / 'installer.py'))
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)
INSTALLER.inventory()
stage_parent = os.environ.get('KCMC_CI_STAGE_ROOT')
assert stage_parent and Path(stage_parent).is_dir()
with tempfile.TemporaryDirectory(prefix='kcmc-reviewed-stage-', dir=stage_parent) as directory:
    INSTALLER.BACKUP_ROOT = Path(directory) / 'backups'
    INSTALLER.private_dir(INSTALLER.BACKUP_ROOT)
    stage = INSTALLER.BACKUP_ROOT / 'release-stage'
    INSTALLER.private_dir(stage)
    records = []
    for path, approved in sorted(INSTALLER.FILES.items()):
        raw = (ROOT / 'KCMC-Connect-Phase6-Recreated' / path).read_bytes()
        assert len(raw) == approved['bytes'] and INSTALLER.digest(raw) == approved['sha256']
        INSTALLER.source_hash(path, raw)
        destination = stage / path
        INSTALLER.private_dir(destination.parent)
        INSTALLER.write_private(destination, raw)
        records.append({'path':path, 'staged':str(destination)})
    INSTALLER.lint_staged(records)
print('PASS: exact ten-file target passed actual PHP 8.2 syntax, SVG MIME/XML, 512px PNG/JPEG metadata and JavaScript syntax checks; no host operation.')
