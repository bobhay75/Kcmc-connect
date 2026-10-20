#!/usr/bin/env python3
"""Isolated acceptance for the observed-live reconciliation; no host access."""
import copy
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NOW = dt.datetime(2026, 10, 20, 15, 0, tzinfo=dt.timezone.utc)
CLASS_ID = 'faith-friends-20261018'
MISSING_CONFLICT = 'missing_known_record:events.' + CLASS_ID


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


reconcile = load_module('observed_live_reconcile', HERE / 'reconcile-observed-live.py')


class ObservedLiveReconciliation(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        capture = contextlib.redirect_stdout(self.output)
        capture.__enter__()
        self.addCleanup(capture.__exit__, None, None, None)
        self.pub = load_module('observed_live_test_publisher', HERE / 'publish.py')
        self.reviewed = self.pub.fixture()
        baseline = subprocess.check_output(
            ['git', 'show', '970564f4d520a7325a3852292404cf33175b9af4'],
            cwd=str(ROOT))
        self.document = json.loads(baseline)
        # The observed host search returned only Hope Keepers' "friendship".
        # This expired historical author event also mentions "Faith", so it
        # cannot be present in a synthetic fixture representing that evidence.
        absent_ids = ('faith-friends-20260927', CLASS_ID, 'meet-the-author-jaffee-20260929')
        self.document['events'] = [item for item in self.document['events']
                                   if item['id'] not in absent_ids]
        self.document['custom'] = {'keep': ['all unrelated values', {'number': 7}]}
        self.document['contact']['office_hours'] = 'Staff-maintained office hours'
        trunk = next(item for item in self.document['events']
                     if item['id'] == 'trunk-or-treat-2026')
        trunk['custom_staff_field'] = 'Preserve this extra field'
        hope = next(item for item in self.document['events']
                    if item['id'] == 'hope-keepers-20261013')
        hope.update(repeat='weekly', repeat_until='', expires_at='',
                    one_time_expires_at='2026-10-14T00:00:00-05:00')
        self.hope = copy.deepcopy(hope)
        self.target = copy.deepcopy(next(change['target'] for change in self.reviewed['records']
                                         if change['section'] == 'events' and change['id'] == CLASS_ID))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'content.json'
        self.backups = self.root / 'private-backups'
        self.patch(self.pub, 'CONTENT', self.path)
        self.patch(self.pub, 'BACKUPS', self.backups)
        self.patch(reconcile, 'UID', os.getuid())
        self.patch(reconcile, 'GID', os.getgid())
        self.patch(reconcile, 'OBSERVED_SHA', '')
        self.refusals = (self.pub.Refusal, getattr(reconcile, 'Refusal', RuntimeError))
        self.store_document(self.document)

    def patch(self, obj, name, value):
        patcher = mock.patch.object(obj, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def store_document(self, document):
        """Bind only this isolated test instance to its synthetic snapshot."""
        self.raw = self.pub.encoded(document)
        self.path.write_bytes(self.raw)
        self.path.chmod(0o640)
        reconcile.OBSERVED_SHA = self.pub.digest(self.raw)

    def assert_refused_without_publication(self, now=NOW):
        before = self.path.read_bytes()
        with self.assertRaises(self.refusals):
            reconcile.apply(self.pub, now)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.backups.exists())

    def test_original_guard_is_reproduced_and_unchanged(self):
        publisher_before = (HERE / 'publish.py').read_bytes()
        fixture_before = (HERE / 'reviewed-content.json').read_bytes()
        unused, unused_actions, conflicts = self.pub.plan(self.document, self.reviewed, NOW)
        self.assertEqual(conflicts, [MISSING_CONFLICT])
        reviewed_before = copy.deepcopy(self.reviewed)
        original_before = copy.deepcopy(self.document)
        candidate, actions = reconcile.plan_reconciliation(self.pub, self.raw, self.reviewed, NOW)
        self.assertEqual(self.document, original_before)
        self.assertEqual(self.reviewed, reviewed_before)
        self.assertEqual((HERE / 'publish.py').read_bytes(), publisher_before)
        self.assertEqual((HERE / 'reviewed-content.json').read_bytes(), fixture_before)
        self.assertEqual(self.pub.plan(self.document, self.reviewed, NOW)[2], [MISSING_CONFLICT])
        self.assertEqual(next(item for item in candidate['events'] if item['id'] == CLASS_ID), self.target)
        self.assertTrue(any(CLASS_ID in action for action in actions))

    def test_check_is_read_only_and_proposes_complete_candidate(self):
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob('*'))
        report = reconcile.check(self.pub, NOW)
        self.assertFalse(report['writes_performed'])
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertEqual(sorted(str(path.relative_to(self.root)) for path in self.root.rglob('*')), before)
        self.assertFalse(self.backups.exists())
        candidate, unused = reconcile.plan_reconciliation(self.pub, self.raw, self.reviewed, NOW)
        self.assertEqual(candidate['bulletin']['date'], '2026-10-20')
        meeting = next(item for item in candidate['events'] if item['id'] == 'way-forward-20261022')
        self.assertEqual(meeting['time'], '1:30 PM')

    def test_one_replacement_publishes_full_release_and_preserves_unrelated_data(self):
        source_before = (HERE / 'publish.py').read_bytes()
        fixture_before = (HERE / 'reviewed-content.json').read_bytes()
        original_replace = self.pub.replace_exact
        def replacement_with_durable_receipt(path, raw, expected, original_info):
            receipts = list(self.backups.glob('*.receipt.json'))
            self.assertEqual(len(receipts), 1)
            receipt = self.pub.decode(receipts[0].read_bytes())
            self.assertEqual(Path(receipt['backup']).read_bytes(), self.raw)
            self.assertEqual(receipt['after_sha256'], self.pub.digest(raw))
            self.assertIn('PRIVATE_RECEIPT=' + str(receipts[0]), self.output.getvalue())
            self.assertEqual(path.read_bytes(), self.raw)
            return original_replace(path, raw, expected, original_info)
        with mock.patch.object(self.pub, 'replace_exact', side_effect=replacement_with_durable_receipt) as replacement:
            report = reconcile.apply(self.pub, NOW)
        self.assertEqual(report['result'], 'published')
        self.assertTrue(report['writes_performed'])
        self.assertEqual(replacement.call_count, 1)
        installed_raw = self.path.read_bytes()
        installed = self.pub.decode(installed_raw)
        self.assertEqual(report['sha256'], self.pub.digest(installed_raw))
        self.assertEqual([item for item in installed['events'] if item['id'] == CLASS_ID], [self.target])
        self.assertEqual(next(item for item in installed['events'] if item['id'] == self.hope['id']), self.hope)
        self.assertEqual(installed['custom'], self.document['custom'])
        self.assertEqual(installed['contact'], self.document['contact'])
        self.assertEqual(installed['bulletin']['services'], self.document['bulletin']['services'])
        self.assertEqual(next(item for item in installed['events'] if item['id'] == 'trunk-or-treat-2026')
                         ['custom_staff_field'], 'Preserve this extra field')
        self.assertNotIn('friends-of-faith-20261018', {item['id'] for item in installed['announcements']})
        self.assertNotIn('front-porch-gospel-20261018', {item['id'] for item in installed['events']})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        final_candidate, unused, conflicts = self.pub.plan(installed, self.reviewed, NOW)
        self.assertEqual(conflicts, [])
        self.assertEqual(final_candidate, installed)
        self.assertEqual((HERE / 'publish.py').read_bytes(), source_before)
        self.assertEqual((HERE / 'reviewed-content.json').read_bytes(), fixture_before)
        backups_before = sorted(path.name for path in self.backups.iterdir())
        no_op = self.pub.publish(self.path, self.backups, self.pub.digest(installed_raw), NOW, self.reviewed)
        self.assertEqual(no_op['result'], 'already_current')
        self.assertFalse(no_op['writes_performed'])
        self.assertEqual(sorted(path.name for path in self.backups.iterdir()), backups_before)

    def test_private_backup_and_standard_rollback_restore_exact_bytes_and_metadata(self):
        before_info = self.path.stat()
        report = reconcile.apply(self.pub, NOW)
        receipt_path = Path(report['receipt'])
        receipt = self.pub.decode(receipt_path.read_bytes())
        backup_path = Path(receipt['backup'])
        self.assertEqual(backup_path.read_bytes(), self.raw)
        self.assertEqual(receipt['before_sha256'], self.pub.digest(self.raw))
        self.assertEqual(receipt['after_sha256'], self.pub.digest(self.path.read_bytes()))
        self.assertEqual(receipt['target'], str(self.path))
        self.assertEqual(self.backups.stat().st_mode & 0o777, 0o700)
        self.assertEqual(backup_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)
        restored = self.pub.rollback(self.path, self.backups, report['receipt'])
        self.assertEqual(restored['result'], 'rolled_back')
        self.assertEqual(self.path.read_bytes(), self.raw)
        after_info = self.path.stat()
        self.assertEqual((after_info.st_uid, after_info.st_gid, after_info.st_mode & 0o777),
                         (before_info.st_uid, before_info.st_gid, before_info.st_mode & 0o777))

    def test_repeat_reconciliation_refuses_without_duplicating_or_backing_up(self):
        reconcile.apply(self.pub, NOW)
        installed = self.path.read_bytes()
        backups_before = sorted(path.name for path in self.backups.iterdir())
        with self.assertRaises(self.refusals):
            reconcile.apply(self.pub, NOW)
        self.assertEqual(self.path.read_bytes(), installed)
        self.assertEqual(sorted(path.name for path in self.backups.iterdir()), backups_before)
        self.assertEqual(sum(item['id'] == CLASS_ID for item in self.pub.decode(installed)['events']), 1)

    def test_stale_snapshot_refuses_before_backup(self):
        self.path.write_bytes(self.raw + b' ')
        self.assert_refused_without_publication()

    def test_aliases_future_starts_and_hidden_or_deleted_classes_refuse(self):
        variants = [
            {'id': 'staff-class', 'date': '2026-10-25'},
            {'id': 'friends_of_faith_20261025', 'title': 'Class', 'date': '2026-10-25',
             'location': 'KCMC', 'description': ''},
            {'id': 'staff-legacy-class', 'title': 'Faith & Friends Adult Bible Study Class',
             'date': '2026-09-27', 'time': '10:15 AM'},
            {'id': 'staff-hidden-class', 'status': 'hidden'},
            {'id': 'staff-deleted-class', 'deleted_at': '2026-10-19T12:00:00-05:00'},
            {'id': 'staff-renamed-class', 'title': 'Sunday class', 'location': 'Classroom',
             'description': 'Becoming Like Jesus by Matt Chandler.'},
            {'id': 'staff-future-renamed', 'title': 'Sunday study', 'date': '2026-11-01',
             'location': 'Pairs & Spares Classroom', 'description': ''},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                document = copy.deepcopy(self.document)
                item = copy.deepcopy(self.target)
                item.update(changes)
                document['events'].append(item)
                self.store_document(document)
                self.assert_refused_without_publication()

    def test_present_exact_id_is_not_treated_as_reviewed_absence(self):
        document = copy.deepcopy(self.document)
        document['events'].append(copy.deepcopy(self.target))
        self.store_document(document)
        self.assert_refused_without_publication()

    def test_additional_editorial_conflicts_refuse_entire_release(self):
        documents = []
        changed_bulletin = copy.deepcopy(self.document)
        changed_bulletin['bulletin']['welcome'] = 'A newer staff-written welcome'
        documents.append(changed_bulletin)
        removed_event = copy.deepcopy(self.document)
        removed_event['events'] = [item for item in removed_event['events']
                                   if item['id'] != 'trunk-or-treat-2026']
        documents.append(removed_event)
        hidden_event = copy.deepcopy(self.document)
        next(item for item in hidden_event['events'] if item['id'] == 'trunk-or-treat-2026')['status'] = 'hidden'
        documents.append(hidden_event)
        for index, document in enumerate(documents):
            with self.subTest(case=index):
                self.store_document(document)
                self.assert_refused_without_publication()

    def test_duplicate_ids_refuse(self):
        document = copy.deepcopy(self.document)
        document['events'].append(copy.deepcopy(document['events'][0]))
        self.store_document(document)
        self.assert_refused_without_publication()

    def test_closed_review_window_refuses_before_backup(self):
        self.assert_refused_without_publication(NOW + dt.timedelta(days=6))

    def test_oversized_candidate_refuses_before_backup(self):
        candidate, unused = reconcile.plan_reconciliation(self.pub, self.raw, self.reviewed, NOW)
        limit = max(len(self.raw), len((HERE / 'reviewed-content.json').read_bytes())) + 1
        self.assertGreater(len(self.pub.encoded(candidate)), limit)
        with mock.patch.object(self.pub, 'MAX_BYTES', limit):
            self.assert_refused_without_publication()

    def test_edit_after_preflight_refuses_before_backup(self):
        real_check = reconcile.check
        def check_then_staff_edit(pub, now):
            report = real_check(pub, now)
            self.path.write_bytes(self.raw + b' ')
            return report
        with mock.patch.object(reconcile, 'check', side_effect=check_then_staff_edit):
            with self.assertRaises(self.refusals):
                reconcile.apply(self.pub, NOW)
        self.assertEqual(self.path.read_bytes(), self.raw + b' ')
        self.assertFalse(self.backups.exists())

    def test_edit_immediately_before_replace_is_preserved(self):
        original_replace = self.pub.replace_exact
        staff_copy = copy.deepcopy(self.document)
        staff_copy['contact']['office_hours'] = 'Concurrent staff change; retain it'
        staff_bytes = self.pub.encoded(staff_copy)
        def edit_before_replace(path, raw, expected, original_info):
            path.write_bytes(staff_bytes)
            return original_replace(path, raw, expected, original_info)
        with mock.patch.object(self.pub, 'replace_exact', side_effect=edit_before_replace):
            with self.assertRaises(self.refusals):
                reconcile.apply(self.pub, NOW)
        self.assertEqual(self.path.read_bytes(), staff_bytes)

    def test_rollback_refuses_new_staff_edit(self):
        report = reconcile.apply(self.pub, NOW)
        edited = self.path.read_bytes() + b' '
        self.path.write_bytes(edited)
        with self.assertRaises(self.pub.Refusal):
            self.pub.rollback(self.path, self.backups, report['receipt'])
        self.assertEqual(self.path.read_bytes(), edited)

    def test_content_symlink_and_symlink_lock_refuse(self):
        link = self.root / 'content-link.json'
        link.symlink_to(self.path)
        with mock.patch.object(self.pub, 'CONTENT', link):
            self.assert_refused_without_publication()
        lock = self.root / 'content.json.lock'
        lock.symlink_to(self.path)
        self.assert_refused_without_publication()

    def test_loader_accepts_only_exact_publisher_and_pinned_fixture(self):
        stage = self.root / 'stage'
        publication = stage / 'content-publication'
        publication.mkdir(parents=True, mode=0o700)
        stage.chmod(0o700)
        for name in ('publish.py', 'reviewed-content.json'):
            shutil.copyfile(str(HERE / name), str(publication / name))
            (publication / name).chmod(0o644)
        with mock.patch.object(reconcile, 'STAGE', stage):
            loaded = reconcile.load_publisher()
            self.assertEqual(loaded.fixture(), self.reviewed)
            publisher = publication / 'publish.py'
            publisher.write_bytes(publisher.read_bytes() + b'\n# tampered\n')
            with self.assertRaises(self.refusals):
                reconcile.load_publisher()
            shutil.copyfile(str(HERE / 'publish.py'), str(publisher))
            fixture = publication / 'reviewed-content.json'
            fixture.write_bytes(fixture.read_bytes() + b' ')
            with self.assertRaisesRegex(RuntimeError, 'checksum_failed:reviewed-content.json'):
                reconcile.load_publisher()


if __name__ == '__main__':
    unittest.main(verbosity=2)
