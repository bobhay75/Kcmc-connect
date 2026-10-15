"""Fixture-only builder of an explicit reviewed-engine absence/dependency extension.

No production payload, host connection, config reader, CLI, or app execution.
"""
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN_SHA256 = '4df2cdef03853c80c96350398b6a5b92cb78722e202debd3279d535fb9e757d7'
REPLACED_FUNCTIONS = {
    'inventory', 'verify_lease', 'inspect', 'repair', 'load', 'lint',
    'bundle_lease', 'move_code', 'restore_owned', 'apply',
}


def engine():
    raw = (HERE / 'frozen-minimal-installer.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_SHA256:
        raise ValueError('Frozen reviewed engine changed')
    spec = importlib.util.spec_from_file_location('isolated_absence_foundation', str(HERE / 'frozen-minimal-installer.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.APP = Path('/__unconfigured_fixture_only__/app')
    module.BACKUPS = Path('/__unconfigured_fixture_only__/private')
    module.RELEASE = 'fixture-only-absence-dependency-prototype'
    module.FILES = {}; module.PATHS = (); module.DEPENDENCIES = {}
    module.frozen_move_code = module.move_code
    exec(compile((HERE / 'extension.py').read_bytes(), str(HERE / 'extension.py'), 'exec'), module.__dict__)
    return module
