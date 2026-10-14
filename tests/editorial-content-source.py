#!/usr/bin/env python3
"""Verify the bounded October 14 public editorial delta; no host or writes."""
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
    candidate_bytes = (ROOT / PATH).read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(candidate_bytes)).encode() + b'\0' + candidate_bytes).hexdigest()
    require(blob == fixture['target_git_blob'], 'public content bytes match the reviewed draft')
    validate(json.loads(candidate_bytes), baseline, fixture)
    negative_controls(baseline, fixture)
    print('PASS: exact October 14 editorial delta; historical content and protected fields preserved')

if __name__ == '__main__':
    main()
