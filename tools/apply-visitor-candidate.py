#!/usr/bin/env python3
"""Apply one pinned source candidate on its isolated review branch; never deploy."""
from pathlib import Path
import hashlib, json, subprocess
r=Path(__file__).resolve().parents[1]
sha='c1063495d8d493eea0fb3561648442f0c9967504193fc27b2e0fcde494c211ab'
fixture=r/'tests/fixtures/visitor-welcome-reviewed.json'
assert hashlib.sha256(fixture.read_bytes()).hexdigest()==sha, 'Fixture mismatch'
data=json.loads(fixture.read_bytes())
app=r/'KCMC-Connect-Phase6-Recreated'
for path,digest in data['new_files'].items():
    assert hashlib.sha256((app/path).read_bytes()).hexdigest()==digest, path
for path,changes in data['replacements'].items():
    p=app/path
    raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==data['baseline_sha256'][path], path
    for old,new in changes:
        assert raw.count(old.encode())==1, path
        raw=raw.replace(old.encode(),new.encode(),1)
    p.write_bytes(raw)
def replace(path,a,b):
 p=r/path;s=p.read_text();assert s.count(a)==1,(path,a[:70],s.count(a));p.write_text(s.replace(a,b,1))
replace('tests/visible-photos-review.py',"count() == 9, f'{width}px nine approved local hero frames'","count() == 8, f'{width}px eight retained local hero frames; rejected stage removed'")
replace('tests/visible-photos-review.py',"                    page.locator('[data-hero-next]').click()\n                    page.locator('[data-hero-next]').click()\n                    check('kcmc-ministry-group.jpg'", "                    page.locator('[data-hero-next]').click()\n                    check('kcmc-ministry-group.jpg'")
replace('tests/visible-photos-review.py',"                    page.locator('[data-hero-previous]').click()\n                    page.locator('[data-hero-previous]').click()\n                    page.locator('[data-hero-previous]').click()\n                    family", "                    page.locator('[data-hero-previous]').click()\n                    page.locator('[data-hero-previous]').click()\n                    family")
p=r/'tests/public-photo-offline-browser.py';s=p.read_text();s=s.replace("check(len(paths) == 9 and MISSING in paths, 'fixture retains all nine real public hero paths')", "expected_count = 9 if site.name == 'stale' else 8\n    check(len(paths) == expected_count and MISSING in paths, 'fixture retains historical nine or current eight real hero paths')\n    if site.name != 'stale':\n        check(not any('stage-2014' in path for path in paths), 'current fixture excludes rejected stage')")
s=s.replace("'fixture retains all nine real public hero paths'", "'fixture retains real public hero paths'")
s=s.replace("public-presentation.css?v=contemporary-bright-20261007", "public-presentation.css?v=visitor-welcome-20261008")
s=s.replace('only the fourth frame from the actual worker cache','only the selected frame from the actual worker cache')
s=s.replace('fixed real worker serves all nine hero images','fixed real worker serves all eight hero images').replace('list(range(1, 9))','list(range(1, 8))').replace("assert_one_photo(page, 8, 'offline Previous", "assert_one_photo(page, 7, 'offline Previous").replace("Photo 9 of 9.","Photo 8 of 8.")
s=s.replace("nth(3).evaluate('(img) => img.naturalWidth') == 0, 'missing-frame", "nth(2).evaluate('(img) => img.naturalWidth') == 0, 'missing-frame")
s=s.replace('for expected in (1, 2, 4):','for expected in (1, 3):').replace("assert_one_photo(page, 2, 'Previous skips missing fourth frame backward')", "assert_one_photo(page, 1, 'Previous skips missing third frame backward')").replace("assert_one_photo(page, 4, 'Next skips missing fourth frame forward')", "assert_one_photo(page, 3, 'Next skips missing third frame forward')").replace('for expected in (5, 6, 7, 8, 0):','for expected in (4, 5, 6, 7, 0):')
p.write_text(s)
p=r/'tests/installed-reconciliation-source.py';s=p.read_text()
anchor='for name, content in expected.items():\n    for old, new in approved.get(name, []):'
assert s.count(anchor)==1
s=s.replace(anchor,'''# Owner-requested visitor welcome scope. The proposed delta is enumerated byte
# for byte against current main; merge and deployment still require approval.
visitor_bytes = (ROOT / 'tests/fixtures/visitor-welcome-reviewed.json').read_bytes()
check(hashlib.sha256(visitor_bytes).hexdigest() == '%s', 'visitor delta fixture remains exact')
visitor = json.loads(visitor_bytes)
check(visitor['source_commit'] == 'b6093050dafe9a8d5b2ad4d958fdae742bc06624', 'visitor baseline remains current reviewed main')
check(set(visitor['replacements']) == {'index.php', 'public-presentation.css', 'sw.js', 'app.js', 'api/connection.php', 'admin/connections.php'}, 'visitor changes are confined to six named existing files')
check(set(visitor['new_files']) == {'lib/visitor-welcome.php'}, 'one independent visitor mail module is introduced')

def apply_visitor(name, content):
    if name not in visitor['replacements']:
        return content
    check(hashlib.sha256(content).hexdigest() == visitor['baseline_sha256'][name], name + ': visitor baseline bytes match')
    for old, new in visitor['replacements'][name]:
        check(content.count(old.encode()) == 1, name + ': visitor replacement anchor is unique')
        content = content.replace(old.encode(), new.encode(), 1)
    return content

for name, content in expected.items():
    for old, new in approved.get(name, []):'''%sha,1)
s=s.replace("    check(actual == content, name + ': exact reviewed runtime plus approved differences only')", "    content = apply_visitor(name, content)\n    check(actual == content, name + ': exact reviewed runtime plus enumerated visitor differences only')",1)
anchor='# Publication Designer changes remain constrained to the same three reviewed'
extra='''for name in set(visitor['replacements']) - set(expected):
    content = apply_visitor(name, source(visitor['source_commit'], PREFIX + name))
    check((ROOT / PREFIX / name).read_bytes() == content, name + ': only exact visitor delta permitted')
for name, sha in visitor['new_files'].items():
    check(hashlib.sha256((ROOT / PREFIX / name).read_bytes()).hexdigest() == sha, name + ': exact separately tested visitor module')
visitor_paths = {PREFIX + p for p in visitor['replacements']} | {PREFIX + p for p in visitor['new_files']}

'''
assert s.count(anchor)==1;s=s.replace(anchor,extra+anchor,1)
s=s.replace('| image_paths | documentation_paths)', '| image_paths | documentation_paths | visitor_paths)')
s=s.replace('application diff is reviewed runtime plus exactly four Publication Designer admin files and the deployment guide','application diff is exact runtime, Publisher, documentation and enumerated visitor scope').replace('post-reconciliation diff is approved runtime deltas plus Publication Designer admin files and the deployment guide','post-reconciliation diff is exact reviewed source plus enumerated visitor scope')
p.write_text(s)

replace('tests/public-photo-offline-source.cjs','assert.equal(heroPaths.length, 9);', "assert.equal(heroPaths.length, 8);\n  assert.ok(heroPaths.every(path => !path.includes('stage-2014')));")
replace('tests/public-photo-offline-source.cjs','all nine real hero paths','all eight retained hero paths')
replace('tests/pwa-cache-privacy.cjs',"assert.ok(h.calls.fetch.some(request=>request.url.endsWith('/app.js?v=3.0.2')));", "assert.ok(h.calls.fetch.some(request=>request.url.endsWith('/app.js?v=visitor-welcome-20261008')));")
replace('tests/security-contract.sh', 'grep -q "app.js?v=3.0.2" "$app_dir/sw.js" || fail "3.0.2 service worker does not precache the resilient client"', 'grep -Fq "app.js?v=visitor-welcome-20261008" "$app_dir/sw.js" || fail "Service worker does not precache the reviewed visitor client"\ngrep -Fq "app.js?v=visitor-welcome-20261008" "$app_dir/index.php" || fail "Homepage and worker client versions differ"')

expected={'tests/installed-reconciliation-source.py': 'ac9a99b0a69a3b2662ea4ebbac93b5dabdf8bf0c78738b599173769a1fe2677a', 'tests/visible-photos-review.py': '2545ee6c106058559476d6318c056d8be71b7172dcd5d81609593052a6b56dd1', 'tests/public-photo-offline-browser.py': '2dea716cff159c4994e40debec562f47e83a77af0317103d8be1dede34ec64ab', 'tests/public-photo-offline-source.cjs': '160a4cbbb9c640d60f020b6f1494c832f047a1a63aefccfe0448474ae91ac55e', 'tests/security-contract.sh': '29b7fac404d78579df132ef89082b0f045c252542b0e47e68d4fcc8c931d5016', 'tests/pwa-cache-privacy.cjs': 'ef85935eb433fb04309f92731f321eced1a6130a75ca6b683fe269282c607df4'}
for path,digest in expected.items():
    assert hashlib.sha256((r/path).read_bytes()).hexdigest()==digest, 'Unexpected delta: '+path
print('Exact visitor candidate applied; no deployment or live data access.')
