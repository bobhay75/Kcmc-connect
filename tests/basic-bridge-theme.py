#!/usr/bin/env python3
"""Verify the bridge-led Core hero and preserved small fish icon."""
from pathlib import Path
import subprocess, sys, tempfile
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kcmc-bridge-release-') as temp:
    target = Path(temp) / 'core'
    subprocess.run([sys.executable, str(root/'tools/basic-handoff/build.py'), str(target)], check=True)
    page = (target/'index.php').read_text(encoding='utf-8')
    css = (target/'bridge-theme.css').read_text(encoding='utf-8')
    worker = (target/'sw.js').read_text(encoding='utf-8')
    assert 'kcmc-bridge-logo-sunset-hero-20261023.webp' in page
    assert 'bridge-theme.css?v=core-bridge-20261106' in page
    assert page.index('home-welcome.css?v=20261023-bridge-gradient') < page.index('bridge-theme.css?v=core-bridge-20261106')
    assert 'bridge-theme.css?v=core-bridge-20261106' in worker
    assert '.fish-menu' in page
    assert 'background:#19382d' in css
    assert '-webkit-text-fill-color:currentColor' in css
    assert (target/'assets/visuals/kcmc-bridge-logo-sunset-hero-20261023.webp').is_file()
    assert not (target/'admin/publication-designer.php').exists()
    print('PASS: bridge hero, neutral Core theme, retained fish icon, cache, and premium separation')
