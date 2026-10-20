#!/usr/bin/env python3
"""Verify the historical editorial delta and reviewed October 18 overlay."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATH = 'KCMC-Connect-Phase6-Recreated/data/content.json'
FIXTURE_SHA256 = 'a80566cab457676c2309434ce077e3ed64174e12cd440f84ff7f7e88e4563000'
EVENT_IDS = {
    'griefshare-20261014', 'salt-light-bible-study-20261014',
    'launchpad-kids-20261014', 'rooted-youth-20261014', 'chancel-choir-20261014',
    'quest-preschool-20261015', 'coffee-bible-study-20261015',
    'gathering-place-20261015', 'methodist-women-20261015',
    'beginners-line-dancing-20261015', 'intermediate-line-dancing-20261015',
    'friday-night-freedom-20261016', 'richard-french-lasagna-20261114', 'pll-bottle-return-20261025',
}
ANNOUNCEMENT_IDS = {'trunk-volunteers-20261014', 'pll-bottles-20261025'}

def require(ok, message):
    if not ok:
        raise AssertionError(message)

def expected_content(baseline, fixture):
    require(set(fixture) == {'baseline_commit', 'target_git_blob', 'office_hours', 'bulletin', 'append_events', 'append_announcements'}, 'editorial fixture scope')
    require(fixture['baseline_commit'] == '2146af219d2fd23136eae1685f91a2a2caec030e', 'historical baseline retained')
    require(fixture['target_git_blob'] == '141cff3397171c08e79e7e11c1b18e47633f1e4f', 'reviewed public content blob retained')
    require(fixture['office_hours'] == 'Tue–Thu • 8:00 AM–4:00 PM', 'reviewed office hours')
    require(set(fixture['bulletin']) == {'title', 'date', 'welcome', 'notes'}, 'only four bulletin fields')
    require(len(fixture['append_events']) == 14 and {e['id'] for e in fixture['append_events']} == EVENT_IDS, 'exact dated event additions')
    require(len(fixture['append_announcements']) == 2 and {e['id'] for e in fixture['append_announcements']} == ANNOUNCEMENT_IDS, 'exact announcement additions')
    expected = copy.deepcopy(baseline)
    expected['contact']['office_hours'] = fixture['office_hours']
    expected['bulletin'].update(fixture['bulletin'])
    expected['events'].extend(fixture['append_events'])
    expected['announcements'].extend(fixture['append_announcements'])
    # Owner confirmed October 17: one class, Friends of Faith at 10:20 AM.
    expected['events'].append({"id":"faith-friends-20261018","title":"Friends of Faith Sunday Bible Study","date":"2026-10-18","time":"10:20 AM","location":"KCMC — Pairs & Spares Classroom","description":"Becoming Like Jesus by Matt Chandler. Beginning October 18, 2026.","status":"published","rsvp":False,"expires_at":"2026-10-18T23:59:59-05:00"})
    return expected

def validate(candidate, baseline, fixture):
    require(candidate == expected_content(baseline, fixture), 'content must equal only the reviewed field changes and appended records')
    require(candidate['contact']['email'] == baseline['contact']['email'], 'office email unchanged')
    require(candidate['bulletin']['services'] == baseline['bulletin']['services'], 'services unchanged')
    for section in ('events', 'announcements'):
        require(candidate[section][:len(baseline[section])] == baseline[section], 'all historical records preserved')
        require(len({item['id'] for item in candidate[section]}) == len(candidate[section]), 'unique record IDs')
    require([e for e in candidate['events'] if e['id'] == 'trunk-or-treat-2026'] == [e for e in baseline['events'] if e['id'] == 'trunk-or-treat-2026'], 'entire Trunk record unchanged')

def negative_controls(baseline, fixture):
    good = expected_content(baseline, fixture)
    mutations = []
    changed = copy.deepcopy(good); changed['contact']['email'] = 'unapproved@example.invalid'; mutations.append(changed)
    changed = copy.deepcopy(good); changed['contact']['office_hours'] = baseline['contact']['office_hours']; mutations.append(changed)
    for field in ('time', 'end_time'):
        changed = copy.deepcopy(good)
        next(e for e in changed['events'] if e['id'] == 'trunk-or-treat-2026')[field] = '8:00 PM'
        mutations.append(changed)
    changed = copy.deepcopy(good); changed['events'][0]['title'] = 'Unreviewed history edit'; mutations.append(changed)
    changed = copy.deepcopy(good); changed['events'].append(copy.deepcopy(changed['events'][-1])); mutations.append(changed)
    changed = copy.deepcopy(good); changed['bulletin']['services'][0]['time'] = '7:00 AM'; mutations.append(changed)
    changed = copy.deepcopy(good); changed['bulletin']['notes'].append('Synthetic private prayer detail'); mutations.append(changed)
    changed = copy.deepcopy(good); changed['contact']['address'] = 'Unreviewed address'; mutations.append(changed)
    changed = copy.deepcopy(good); changed['news'] = {}; mutations.append(changed)
    mutations.append(copy.deepcopy(baseline))
    for candidate in mutations:
        try:
            validate(candidate, baseline, fixture)
        except AssertionError:
            continue
        raise AssertionError('unreviewed mutation was accepted')
    print('PASS: 11 negative controls reject time, email, private-detail, history and other unreviewed changes')

def main():
    fixture_bytes = (ROOT / 'tests/fixtures/editorial-content-20261014-reviewed.json').read_bytes()
    require(hashlib.sha256(fixture_bytes).hexdigest() == FIXTURE_SHA256, 'editorial fixture remains exact')
    fixture = json.loads(fixture_bytes)
    baseline_bytes = subprocess.check_output(['git', 'show', fixture['baseline_commit'] + ':' + PATH], cwd=ROOT)
    baseline = json.loads(baseline_bytes)
    # Keep the previous reviewed snapshot and its negative controls intact.
    # Reconstruct from the pinned baseline and hash-verified review fixture.
    # A shallow CI checkout need not contain the previous content blob.
    historical = expected_content(baseline, fixture)
    validate(historical, baseline, fixture)
    negative_controls(baseline, fixture)
    release_bytes = (ROOT / 'tests/fixtures/editorial-content-20261018-reviewed.json').read_bytes()
    require(hashlib.sha256(release_bytes).hexdigest() == '028d58fff94280e658aa6fb9dfbb11b55ae5dbf6e3fe878cbebda1f374055126', 'October 18 reviewed fixture remains exact')
    release = json.loads(release_bytes)
    require(release['baseline_git_blob'] == '970564f4d520a7325a3852292404cf33175b9af4', 'October 18 starts at the previously reviewed content')
    expected = copy.deepcopy(historical)
    expected['bulletin'].update(release['bulletin'])
    for section in ('events', 'announcements'):
        updates = release['update_' + section]
        require(set(updates) <= {item['id'] for item in historical[section]}, 'update IDs must exist')
        for item in expected[section]:
            item.update(updates.get(item['id'], {}))
        expected[section].extend(release['append_' + section])
    current_bytes = (ROOT / 'tests/fixtures/editorial-content-20261020-reviewed.json').read_bytes()
    require(hashlib.sha256(current_bytes).hexdigest() == '4027b8d12c3d7f3faf06bb79b6215ae92e04e1f039d50fa81c16a6a2cb58846b', 'October 20 reviewed fixture remains exact')
    current = json.loads(current_bytes)
    require(set(current) == {'baseline_git_blob','baseline_utf8','bulletin','update_events','update_announcements'}, 'October 20 scope stays bounded')
    require(current['baseline_git_blob'] == 'efee40e1152857a391491df7c4db2c1e11cc3228', 'October 20 exact baseline retained')
    baseline_raw = current['baseline_utf8'].encode('utf-8')
    require(hashlib.sha1(b'blob '+str(len(baseline_raw)).encode('ascii')+b'\0'+baseline_raw).hexdigest() == current['baseline_git_blob'], 'October 18 bytes remain independently pinned for shallow CI')
    require(json.loads(baseline_raw) == expected, 'exact October 18 projection retained')
    require(set(current['update_events']) == {'faith-friends-20261018','trunk-or-treat-2026'}, 'only the confirmed class recurrence and dated trunk wording change')
    require(set(current['update_announcements']) == {'trunk-volunteers-20261014'}, 'only expired relative signup wording changes')
    expected['bulletin'].update(current['bulletin'])
    for section in ('events', 'announcements'):
        for item in expected[section]:
            item.update(current['update_' + section].get(item['id'], {}))
    candidate = json.loads((ROOT / PATH).read_bytes())
    require(candidate == expected, 'only the exact October 18 and October 20 reviewed content deltas are permitted')
    for section in ('events', 'announcements'):
        require(len({item['id'] for item in candidate[section]}) == len(candidate[section]), 'unique content IDs')
    require(candidate['contact'] == historical['contact'], 'contact fields stay unchanged')
    require(candidate['bulletin']['services'] == historical['bulletin']['services'], 'service definitions stay unchanged')
    for key in ('meta', 'news', 'sponsors'):
        require(candidate[key] == historical[key], key + ' remains unchanged')
    bottle = next(e for e in candidate['events'] if e['id'] == 'pll-bottle-return-20261025')
    require(bottle['time'] == '' and 'end_time' not in bottle, 'bottle deadline remains date only')
    trunk = next(e for e in candidate['events'] if e['id'] == 'trunk-or-treat-2026')
    require(trunk['time'] == '4:30 PM' and trunk['end_time'] == '6:30 PM', 'confirmed Trunk hours preserved')
    study = [e for e in candidate['events'] if e['date'] == '2026-10-18' and ('Faith' in e['title'] or 'Friends' in e['title'])]
    require(len(study) == 1 and study[0]['time'] == '10:20 AM', 'one owner-corrected Bible study')
    require(study[0]['repeat'] == 'weekly' and study[0]['repeat_until'] == '' and study[0]['expires_at'] == '', 'owner-confirmed Sundays remain visible without invented end date')
    require('this Sunday' not in trunk['description'], 'relative October 18 signup wording has expired')
    require(len(release['append_events']) == 17 and len(release['append_announcements']) == 3, 'complete newsletter delta')
    print('PASS: October 18 newsletter delta, unique IDs, corrected class, date-only deadline and protected sections')

if __name__ == '__main__':
    main()
