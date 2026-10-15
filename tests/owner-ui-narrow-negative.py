#!/usr/bin/env python3
"""Require meaningful A7/A5 failures against their exact reversed route sources."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    'push-owner-link-reviewed.json': 'b6ca2c3e1e218627643aa9d5962ccc11b535242bb7e4e5c25303afd776f32042',
    'owner-account-guard-reviewed.json': 'd872e4deb60baca4cade936412c9706294a3e8a5a2e671acddc59493ca52e527',
}
CASES = {
    'test_send_update_link_matches_existing_owner_route_for_every_role_and_config':
        'Only the exact configured active administrator gets Send update',
    'test_crafted_post_cannot_disable_the_designated_owner':
        'A recovery administrator cannot disable the configured owner with a valid-CSRF crafted POST',
    'test_crafted_post_cannot_issue_a_password_reset_for_the_designated_owner':
        'A recovery administrator cannot obtain an owner reset link with a valid-CSRF crafted POST',
}


def run():
    with tempfile.TemporaryDirectory(prefix='kcmc-owner-ui-negative-') as directory:
        app = Path(directory) / 'app'
        shutil.copytree(ROOT / 'KCMC-Connect-Phase6-Recreated', app)
        for name, sha in PINS.items():
            raw = (ROOT / 'tests/fixtures' / name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == sha, 'Exact fixture required: ' + name
            fixture = json.loads(raw)
            for path, entry in fixture['files'].items():
                content = (app / path).read_bytes()
                assert hashlib.sha256(content).hexdigest() == entry['after_sha256'], 'Exact target required: ' + path
                for old, new in reversed(entry['replacements']):
                    assert content.count(new.encode()) == 1, 'Unique reverse anchor required: ' + path
                    content = content.replace(new.encode(), old.encode(), 1)
                assert hashlib.sha256(content).hexdigest() == entry['before_sha256'], 'Exact preimage required: ' + path
                (app / path).write_bytes(content)
        for case, expected_failure in CASES.items():
            result = subprocess.run([sys.executable, str(ROOT / 'tests/owner-ui-narrow-routes.py'),
                '--app', str(app), '--case', case], capture_output=True, text=True, timeout=60)
            output = result.stdout + result.stderr
            assert result.returncode != 0 and 'FAIL:' in output and expected_failure in output, (
                'Prior source must fail the specific behavior assertion: ' + case + '\n' + output)
            assert not any(message in output for message in ['Fatal error:', 'headers already sent', 'PHP Warning:']), (
                'A PHP harness error cannot satisfy a negative control: ' + case)
            print('PASS: prior source fails the intended assertion:', case)
    print('Three exact prior-source owner UI/account negative controls passed.')


if __name__ == '__main__': run()
