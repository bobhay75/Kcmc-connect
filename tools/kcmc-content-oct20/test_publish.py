#!/usr/bin/env python3
"""Isolated publication and rollback acceptance; never opens the host paths."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('editorial_publish', HERE/'publish.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = dt.datetime(2026, 10, 20, 5, 30, tzinfo=dt.timezone.utc)


class ContentPublication(unittest.TestCase):
    def setUp(self):
        self.raw = subprocess.check_output(['git','show','970564f4d520a7325a3852292404cf33175b9af4'],cwd=str(ROOT))
        self.document = json.loads(self.raw)
        self.reviewed = module.fixture()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root/'content.json'
        self.path.write_bytes(self.raw)
        self.path.chmod(0o640)
        self.backups = self.root/'private-backups'

    def run_plan(self, document=None, now=NOW):
        return module.plan(document or self.document, self.reviewed, now)

    def test_current_meeting_and_confirmed_weekly_class(self):
        result,actions,conflicts = self.run_plan()
        self.assertEqual(conflicts,[])
        meeting=next(x for x in result['events'] if x['id']=='way-forward-20261022')
        self.assertEqual(meeting['time'],'1:30 PM')
        study=next(x for x in result['events'] if x['id']=='faith-friends-20261018')
        self.assertEqual((study['time'],study['repeat'],study['expires_at']),('10:20 AM','weekly',''))
        self.assertEqual(result['bulletin']['date'],'2026-10-20')
        self.assertNotIn('this Sunday',next(x for x in result['events'] if x['id']=='trunk-or-treat-2026')['description'])

    def test_does_not_publish_expired_sunday_records(self):
        result,actions,conflicts=self.run_plan()
        ids={x['id'] for x in result['events']}
        self.assertNotIn('front-porch-gospel-20261018',ids)
        self.assertNotIn('friends-of-faith-20261018',{x['id'] for x in result['announcements']})
        self.assertTrue(any(x.startswith('skip_expired:') for x in actions))

    def test_unrelated_content_and_extra_record_fields_survive(self):
        self.document['custom']={'keep':'all values'}
        self.document['contact']['office_hours']='Special office hours'
        trunk=next(x for x in self.document['events'] if x['id']=='trunk-or-treat-2026')
        trunk['custom']='keep this too'
        result,unused,conflicts=self.run_plan()
        self.assertEqual(conflicts,[])
        self.assertEqual(result['custom'],self.document['custom'])
        self.assertEqual(result['contact'],self.document['contact'])
        self.assertEqual(next(x for x in result['events'] if x['id']==trunk['id'])['custom'],'keep this too')
        self.assertEqual(result['bulletin']['services'],self.document['bulletin']['services'])

    def test_unknown_field_edit_conflicts(self):
        next(x for x in self.document['events'] if x['id']=='trunk-or-treat-2026')['description']='Staff has revised the plan'
        self.assertTrue(self.run_plan()[2])

    def test_unknown_event_time_conflicts(self):
        next(x for x in self.document['events'] if x['id']=='faith-friends-20261018')['time']='10:15 AM'
        self.assertIn('event_identity_changed:faith-friends-20261018',self.run_plan()[2])

    def test_hidden_record_is_not_republished(self):
        next(x for x in self.document['events'] if x['id']=='trunk-or-treat-2026')['status']='hidden'
        self.assertTrue(self.run_plan()[2])

    def test_possible_duplicate_conflicts(self):
        item=copy.deepcopy(next(x['target'] for x in self.reviewed['records'] if x['id']=='way-forward-20261022' and x['section']=='events'))
        item['id']='manually-created-way-forward'
        self.document['events'].append(item)
        self.assertIn('possible_duplicate:events.way-forward-20261022',self.run_plan()[2])

    def test_existing_weekly_occurrence_is_not_duplicated(self):
        item=next(x for x in self.document['events'] if x['id']=='griefshare-20261014')
        item['repeat']='weekly';item['expires_at']=''
        result,actions,conflicts=self.run_plan()
        self.assertEqual(conflicts,[])
        self.assertNotIn('griefshare-20261021',{x['id'] for x in result['events']})
        self.assertIn('keep_existing_weekly:griefshare-20261021',actions)

    def test_removed_known_record_is_not_recreated(self):
        self.document['events']=[x for x in self.document['events'] if x['id']!='trunk-or-treat-2026']
        result,actions,conflicts=self.run_plan()
        self.assertIn('missing_known_record:events.trunk-or-treat-2026',conflicts)
        self.assertNotIn('trunk-or-treat-2026',{x['id'] for x in result['events']})

    def test_changed_weekly_time_requires_review_without_duplicate(self):
        item=next(x for x in self.document['events'] if x['id']=='griefshare-20261014')
        item.update(repeat='weekly',expires_at='',time='9:45 AM')
        result,unused,conflicts=self.run_plan()
        self.assertIn('possible_duplicate:events.griefshare-20261021',conflicts)
        self.assertNotIn('griefshare-20261021',{x['id'] for x in result['events']})
        self.assertEqual(next(x for x in result['events'] if x['id']==item['id'])['time'],'9:45 AM')

    def test_duplicate_ids_refuse(self):
        self.document['events'].append(copy.deepcopy(self.document['events'][0]))
        with self.assertRaises(module.Refusal): self.run_plan()

    def test_duplicate_json_keys_refuse(self):
        with self.assertRaises(module.Refusal): module.decode(b'{"a":1,"a":2}')

    def test_legacy_release_refuses(self):
        self.document['meta']['content_release']='old'
        with self.assertRaises(module.Refusal): self.run_plan()

    def test_expired_package_refuses(self):
        with self.assertRaises(module.Refusal): self.run_plan(now=NOW+dt.timedelta(days=6))

    def test_past_midweek_events_are_not_added(self):
        result,unused,conflicts=self.run_plan(now=NOW+dt.timedelta(days=3))
        self.assertEqual(conflicts,[])
        self.assertNotIn('way-forward-20261022',{x['id'] for x in result['events']})

    def test_read_only_plan_does_not_change_files(self):
        before=list(self.root.iterdir())
        self.run_plan()
        self.assertEqual(list(self.root.iterdir()),before)
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_hash_change_prevents_write(self):
        with self.assertRaises(module.Refusal): module.publish(self.path,self.backups,'0'*64,NOW,self.reviewed)
        self.assertEqual(self.path.read_bytes(),self.raw)
        self.assertFalse(self.backups.exists())

    def test_oversized_candidate_refuses_before_backup_or_replace(self):
        previous_limit=module.MAX_BYTES
        try:
            module.MAX_BYTES=len(self.raw)+512
            with self.assertRaisesRegex(module.Refusal,'oversized_candidate'):
                module.publish(self.path,self.backups,module.digest(self.raw),NOW,self.reviewed)
        finally:
            module.MAX_BYTES=previous_limit
        self.assertEqual(self.path.read_bytes(),self.raw)
        self.assertFalse(self.backups.exists())

    def test_full_transaction_idempotency_and_exact_rollback(self):
        report=module.publish(self.path,self.backups,module.digest(self.raw),NOW,self.reviewed)
        self.assertEqual(report['result'],'published')
        after=self.path.read_bytes()
        self.assertEqual(self.path.stat().st_mode&0o777,0o640)
        self.assertEqual(self.backups.stat().st_mode&0o777,0o700)
        self.assertEqual(module.publish(self.path,self.backups,module.digest(after),NOW,self.reviewed)['result'],'already_current')
        restored=module.rollback(self.path,self.backups,report['receipt'])
        self.assertEqual(restored['result'],'rolled_back')
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_rollback_refuses_concurrent_edit(self):
        report=module.publish(self.path,self.backups,module.digest(self.raw),NOW,self.reviewed)
        self.path.write_bytes(self.path.read_bytes()+b' ')
        with self.assertRaises(module.Refusal): module.rollback(self.path,self.backups,report['receipt'])

    def test_symbolic_content_refuses(self):
        link=self.root/'linked.json';link.symlink_to(self.path)
        with self.assertRaises(module.Refusal): module.publish(link,self.backups,module.digest(self.raw),NOW,self.reviewed)

    def test_symlink_lock_refuses(self):
        (self.root/'content.json.lock').symlink_to(self.path)
        with self.assertRaises(module.Refusal): module.publish(self.path,self.backups,module.digest(self.raw),NOW,self.reviewed)

    def test_shared_backup_directory_refuses(self):
        self.backups.mkdir(mode=0o755)
        with self.assertRaises(module.Refusal): module.publish(self.path,self.backups,module.digest(self.raw),NOW,self.reviewed)
        self.assertEqual(self.path.read_bytes(),self.raw)


if __name__=='__main__':
    unittest.main(verbosity=2)
