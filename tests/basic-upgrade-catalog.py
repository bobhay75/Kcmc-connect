#!/usr/bin/env python3
"""Verify optional modules are informational and excluded from the Core package."""
from pathlib import Path
import tempfile, subprocess, sys
root=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='kcmc-upgrade-catalog-') as tmp:
    candidate=Path(tmp)/'core'
    subprocess.run([sys.executable, str(root/'tools/basic-handoff/build.py'), str(candidate)], check=True)
    page=(candidate/'admin/upgrades.php').read_text()
    admin=(candidate/'admin/index.php').read_text()
    assert 'kcmc_require_role' in page and 'kcmc_private_headers()' in page
    assert 'Available upgrades' in page and 'admin/upgrades.php' in admin
    assert 'payment' in page.lower() and 'automatic installation' in page.lower()
    forbidden=['admin/publication-designer.php','admin/payroll-setup.php','member/timeclock.php','member/work.php','api/push-subscription.php','api/team-workspace.php','config.php','data/private']
    for item in forbidden: assert not (candidate/item).exists(), item
    assert len(list(candidate.rglob('*.php'))) > 0
    print('PASS: admin-only optional upgrade catalog, no premium endpoints or private stores')
