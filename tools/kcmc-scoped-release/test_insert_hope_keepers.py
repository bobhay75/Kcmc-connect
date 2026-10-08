"""Isolated fixture acceptance for the single-event host repair helper."""
import copy
import contextlib
import datetime
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import signal
import stat
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "insert_hope_keepers", os.path.join(os.path.dirname(__file__), "insert-hope-keepers.py"))
INSERT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSERT)
NOW = datetime.datetime(2026, 10, 8, 3, 0, 0, tzinfo=datetime.timezone.utc)


class InsertHopeKeepersTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = os.path.join(self.temp.name, "app", "data")
        os.makedirs(self.data_dir)
        self.path = os.path.join(self.data_dir, "content.json")
        self.backup_dir = os.path.join(self.temp.name, "private-backups")
        self.document = {
            "meta": {"content_release": "3.0.0", "updated_by": "PRIVATE_EDITOR", "updated_at": "PRIVATE_TIME"},
            "bulletin": {"date": "2026-09-27", "notes": ["", "  PRIVATE_NOTE \n", "________"]},
            "stats": {"value": "PRIVATE_STAT", "ratio": 0.123},
            "private": {"name": "PRIVATE_STAFF_NAME"},
            "events": [{"id": "PRIVATE_OTHER_ID", "title": "Other event", "date": "2026-10-31", "time": "4:30 PM"}],
        }
        self.raw = self.write(self.document)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, document=None, raw=None):
        if raw is None:
            raw = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        with open(self.path, "wb") as handle:
            handle.write(raw)
        os.chmod(self.path, 0o640)
        self.expected = hashlib.sha256(raw).hexdigest()
        return raw

    def execute(self, apply=False, expected=None, clock=None, checkpoint=None, path=None, backup=None):
        return INSERT._execute(apply=apply, host_file=path or self.path,
                               backup_dir=backup or self.backup_dir,
                               expected_sha256=expected or self.expected,
                               clock=clock or (lambda: NOW), checkpoint=checkpoint)

    def bytes(self):
        with open(self.path, "rb") as handle:
            return handle.read()

    def assert_private_output(self, result):
        output = json.dumps(result)
        for value in ["PRIVATE_EDITOR", "PRIVATE_TIME", "PRIVATE_NOTE", "PRIVATE_STAT",
                      "PRIVATE_STAFF_NAME", "PRIVATE_OTHER_ID"]:
            self.assertNotIn(value, output)

    def test_missing_check_does_not_write_or_create_backup_or_lock(self):
        result = self.execute()
        self.assertEqual("ready_to_append", result["verdict"])
        self.assertEqual(self.raw, self.bytes())
        self.assertFalse(os.path.exists(self.backup_dir))
        self.assertFalse(os.path.exists(self.path + ".lock"))
        self.assertFalse(result["write_committed"])
        self.assert_private_output(result)

    def test_apply_appends_exact_candidate_and_preserves_all_other_values_and_bytes(self):
        before = os.stat(self.path)
        result = self.execute(apply=True)
        self.assertEqual("appended", result["verdict"])
        self.assertTrue(result["write_committed"])
        after = os.stat(self.path)
        self.assertEqual((before.st_uid, before.st_gid, stat.S_IMODE(before.st_mode)),
                         (after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode)))
        self.assertNotEqual(before.st_ino, after.st_ino)
        actual = self.bytes()
        decoded = json.loads(actual.decode("utf-8"))
        expected = copy.deepcopy(self.document)
        expected["events"].append(INSERT.CANDIDATE)
        self.assertEqual(expected, decoded)
        token = b"," + INSERT._candidate_bytes()
        self.assertEqual(self.raw, actual.replace(token, b"", 1))
        self.assertEqual(self.expected, result["backup_sha256"])
        self.assertEqual(hashlib.sha256(actual).hexdigest(), result["host_sha256_after"])
        self.assertEqual(2, result["event_count_after"])
        self.assert_private_output(result)
        backup_path = os.path.join(self.backup_dir, result["backup_basename"])
        with open(backup_path, "rb") as handle:
            self.assertEqual(self.raw, handle.read())
        self.assertEqual(0o600, stat.S_IMODE(os.stat(backup_path).st_mode))
        self.assertEqual(0o700, stat.S_IMODE(os.stat(self.backup_dir).st_mode))
        self.assertEqual(0o600, stat.S_IMODE(os.stat(self.path + ".lock").st_mode))
        self.assertEqual(["content.json", "content.json.lock"], sorted(os.listdir(self.data_dir)))

    def test_utf8_crlf_nested_events_and_authored_whitespace_are_literal_preserved(self):
        raw = (' {\r\n  "private":{"events":["quote \\\" and ] bracket"],"text":"café — é"},\r\n'
               ' "meta":{"content_release":"3.0.0","space":"  "},\r\n'
               ' "events" : [ \r\n  {"id":"other","title":"Other"} \r\n ],\r\n'
               ' "bulletin":{"notes":["","   ","a\\nb","________"]}\r\n} \r\n').encode("utf-8")
        self.raw = self.write(raw=raw)
        result = self.execute(apply=True)
        self.assertEqual("appended", result["verdict"])
        self.assertEqual(raw, self.bytes().replace(b"," + INSERT._candidate_bytes(), b"", 1))
        self.assertEqual(json.loads(raw.decode())['bulletin'], json.loads(self.bytes().decode())['bulletin'])

    def test_empty_events_append_keeps_original_bytes(self):
        self.document["events"] = []
        raw = self.write(self.document)
        result = self.execute(apply=True)
        self.assertEqual("appended", result["verdict"])
        self.assertEqual(raw, self.bytes().replace(INSERT._candidate_bytes(), b"", 1))
        self.assertEqual(1, result["event_count_after"])

    def test_already_same_pinned_file_is_no_op(self):
        self.document["events"].append(copy.deepcopy(INSERT.CANDIDATE))
        raw = self.write(self.document)
        result = self.execute(apply=True)
        self.assertEqual("already_same", result["verdict"])
        self.assertFalse(result["write_committed"])
        self.assertFalse(os.path.exists(self.backup_dir))
        self.assertEqual(raw, self.bytes())

    def test_real_pinned_sha_drift_is_refused_even_if_candidate_already_same(self):
        self.document["events"].append(copy.deepcopy(INSERT.CANDIDATE))
        raw = self.write(self.document)
        result = self.execute(apply=True, expected=INSERT.EXPECTED_HOST_SHA256)
        self.assertEqual("host_sha256_drift", result["refusal_code"])
        self.assertEqual(raw, self.bytes())
        self.assertFalse(os.path.exists(self.backup_dir))

    def test_same_id_conflict_and_trimmed_id_are_refused(self):
        for modification in [{"description": "PRIVATE_EDITOR_OVERRIDE"},
                             {"id": "  " + INSERT.CANDIDATE["id"] + "\t"}]:
            event = copy.deepcopy(INSERT.CANDIDATE)
            event.update(modification)
            self.document["events"] = [event]
            raw = self.write(self.document)
            result = self.execute(apply=True)
            self.assertEqual("same_id_conflict", result["refusal_code"])
            self.assertEqual(raw, self.bytes())
            self.assertNotIn("PRIVATE_EDITOR_OVERRIDE", json.dumps(result))
            self.assertFalse(os.path.exists(self.backup_dir))

    def test_full_or_short_title_possible_duplicate_is_refused(self):
        for title in ["Hope Keepers — First Gathering", "  HOPE KEEPERS  "]:
            event = copy.deepcopy(INSERT.CANDIDATE)
            event.update(id="PRIVATE_DIFFERENT_ID", title=title, time="13:00")
            self.document["events"] = [event]
            raw = self.write(self.document)
            result = self.execute(apply=True)
            self.assertEqual("possible_duplicate", result["refusal_code"])
            self.assertEqual(raw, self.bytes())
            self.assertNotIn("PRIVATE_DIFFERENT_ID", json.dumps(result))

    def test_newer_sha_refused_before_backup_and_write(self):
        old_expected = self.expected
        raw = self.write(raw=self.raw + b" ")
        result = self.execute(apply=True, expected=old_expected)
        self.assertEqual("host_sha256_drift", result["refusal_code"])
        self.assertFalse(os.path.exists(self.backup_dir))
        self.assertEqual(raw, self.bytes())

    def test_candidate_expired_by_actual_clock_no_read_or_lock(self):
        result = self.execute(apply=True, clock=lambda: INSERT.EXPIRES_AT)
        self.assertEqual("expired_candidate", result["refusal_code"])
        self.assertIsNone(result["host_sha256_before"])
        self.assertEqual(self.raw, self.bytes())
        self.assertFalse(os.path.exists(self.path + ".lock"))

    def test_expiration_at_commit_refuses_and_keeps_exact_original(self):
        clock_now = [NOW]
        def checkpoint(phase):
            if phase == "before_replace":
                clock_now[0] = INSERT.EXPIRES_AT
        result = self.execute(apply=True, clock=lambda: clock_now[0], checkpoint=checkpoint)
        self.assertEqual("expired_candidate", result["refusal_code"])
        self.assertEqual(self.raw, self.bytes())
        self.assertFalse(result["write_committed"])
        self.assertEqual(["content.json", "content.json.lock"], sorted(os.listdir(self.data_dir)))

    def test_interruption_before_replace_preserves_original_and_private_backup(self):
        for point in ["after_backup", "before_replace"]:
            def checkpoint(phase):
                if phase == point:
                    raise KeyboardInterrupt()
            result = self.execute(apply=True, checkpoint=checkpoint)
            self.assertEqual("interrupted", result["refusal_code"])
            self.assertFalse(result["write_committed"])
            self.assertEqual(self.raw, self.bytes())
            backup_path = os.path.join(self.backup_dir, result["backup_basename"])
            with open(backup_path, "rb") as handle:
                self.assertEqual(self.raw, handle.read())
            self.assertEqual(["content.json", "content.json.lock"], sorted(os.listdir(self.data_dir)))

    def test_interruption_after_replace_reports_commit_without_auto_rollback(self):
        def checkpoint(phase):
            if phase == "after_replace":
                raise KeyboardInterrupt()
        result = self.execute(apply=True, checkpoint=checkpoint)
        self.assertEqual("committed_verification_incomplete", result["verdict"])
        self.assertTrue(result["write_committed"])
        self.assertEqual("interrupted", result["refusal_code"])
        self.assertEqual(INSERT.CANDIDATE, json.loads(self.bytes().decode())['events'][-1])

    def test_sigterm_before_commit_preserves_original_and_reports_interruption(self):
        previous = signal.signal(signal.SIGTERM, INSERT._signal_interrupt)
        try:
            def checkpoint(phase):
                if phase == "before_replace":
                    os.kill(os.getpid(), signal.SIGTERM)
            result = self.execute(apply=True, checkpoint=checkpoint)
        finally:
            signal.signal(signal.SIGTERM, previous)
        self.assertEqual("interrupted", result["refusal_code"])
        self.assertFalse(result["write_committed"])
        self.assertEqual(self.raw, self.bytes())

    def test_sigterm_inside_atomic_commit_has_truthful_committed_receipt(self):
        real_replace = os.replace
        previous = signal.signal(signal.SIGTERM, INSERT._signal_interrupt)
        def replace_and_signal(*args, **kwargs):
            result = real_replace(*args, **kwargs)
            os.kill(os.getpid(), signal.SIGTERM)
            return result
        try:
            with mock.patch.object(INSERT.os, "replace", side_effect=replace_and_signal):
                result = self.execute(apply=True)
        finally:
            signal.signal(signal.SIGTERM, previous)
        self.assertEqual("committed_verification_incomplete", result["verdict"])
        self.assertTrue(result["write_committed"])
        self.assertEqual("interrupted", result["refusal_code"])
        self.assertEqual(INSERT.CANDIDATE, json.loads(self.bytes().decode())['events'][-1])

    def test_main_sigterm_during_late_cleanup_keeps_shared_committed_receipt(self):
        real_execute, real_close = INSERT._execute, os.close
        shared = [{}]
        signaled = [False]
        def fixture_execute(apply=False, report_state=None):
            shared[0] = report_state
            return real_execute(apply=apply, host_file=self.path, backup_dir=self.backup_dir,
                                expected_sha256=self.expected, clock=lambda: NOW,
                                report_state=report_state)
        def close_and_signal(fd):
            result = real_close(fd)
            if shared[0].get("verdict") == "appended" and not signaled[0]:
                signaled[0] = True
                os.kill(os.getpid(), signal.SIGTERM)
            return result
        output = io.StringIO()
        with mock.patch.object(INSERT, "_execute", side_effect=fixture_execute):
            with mock.patch.object(INSERT.os, "close", side_effect=close_and_signal):
                with contextlib.redirect_stdout(output):
                    exit_code = INSERT.main(["--apply"])
        result = json.loads(output.getvalue())
        self.assertEqual(2, exit_code)
        self.assertTrue(signaled[0])
        self.assertTrue(result["write_committed"])
        self.assertEqual("committed_verification_incomplete", result["verdict"])
        self.assertEqual("interrupted", result["refusal_code"])
        self.assertEqual(INSERT.CANDIDATE, json.loads(self.bytes().decode())['events'][-1])
        self.assert_private_output(result)

    def test_noncooperating_newer_write_during_staging_is_not_overwritten(self):
        newer = self.raw + b" \n"
        def checkpoint(phase):
            if phase == "before_replace":
                with open(self.path, "wb") as handle:
                    handle.write(newer)
        result = self.execute(apply=True, checkpoint=checkpoint)
        self.assertEqual("host_changed_before_replace", result["refusal_code"])
        self.assertFalse(result["write_committed"])
        self.assertEqual(newer, self.bytes())

    def test_existing_lock_inode_swap_during_open_is_refused(self):
        lockpath = self.path + ".lock"
        with open(lockpath, "wb") as handle:
            handle.write(b"")
        real_open = os.open
        swapped = [False]
        def swapping_open(path, flags, *args, **kwargs):
            if path == "content.json.lock" and not flags & os.O_CREAT and not swapped[0]:
                swapped[0] = True
                replacement = lockpath + ".replacement"
                with open(replacement, "wb") as handle:
                    handle.write(b"")
                os.replace(replacement, lockpath)
            return real_open(path, flags, *args, **kwargs)
        with mock.patch.object(INSERT.os, "open", side_effect=swapping_open):
            result = self.execute(apply=True)
        self.assertEqual("lock_changed_during_open", result["refusal_code"])
        self.assertEqual(self.raw, self.bytes())
        self.assertFalse(os.path.exists(self.backup_dir))

    def test_parent_move_after_replace_reports_committed_incomplete(self):
        moved = self.data_dir + "-moved"
        newer = self.raw + b"  "
        def checkpoint(phase):
            if phase == "after_replace":
                os.rename(self.data_dir, moved)
                os.mkdir(self.data_dir)
                with open(self.path, "wb") as handle:
                    handle.write(newer)
        result = self.execute(apply=True, checkpoint=checkpoint)
        self.assertEqual("committed_verification_incomplete", result["verdict"])
        self.assertEqual("host_parent_changed", result["refusal_code"])
        self.assertTrue(result["write_committed"])
        self.assertEqual(newer, self.bytes())

    def test_planned_file_size_limit_refuses_before_backup(self):
        with mock.patch.object(INSERT, "MAX_BYTES", len(self.raw)):
            for apply in (False, True):
                result = self.execute(apply=apply)
                self.assertEqual("planned_file_too_large", result["refusal_code"])
                self.assertFalse(result["write_committed"])
                self.assertFalse(os.path.exists(self.backup_dir))
                self.assertEqual(self.raw, self.bytes())

    def test_duplicate_keys_duplicate_ids_and_bad_json_refuse(self):
        cases = [
            (b'{"events":[],"PRIVATE_KEY":1,"PRIVATE_KEY":2}', "duplicate_json_keys"),
            (b'{"events":[{"id":"PRIVATE_ID"},{"id":" PRIVATE_ID "}]}', "duplicate_event_ids"),
            (b'{"events":[],"other":NaN}', "invalid_json"),
            (b'{"events":', "invalid_json"),
            (b'\xff', "invalid_json"),
        ]
        for raw, code in cases:
            self.write(raw=raw)
            result = self.execute(apply=True)
            self.assertEqual(code, result["refusal_code"])
            self.assertEqual(raw, self.bytes())
            self.assertNotIn("PRIVATE_KEY", json.dumps(result))
            self.assertNotIn("PRIVATE_ID", json.dumps(result))

    def test_content_symlink_and_hardlink_refused(self):
        link = os.path.join(self.data_dir, "link.json")
        os.symlink(self.path, link)
        result = self.execute(apply=True, path=link)
        self.assertEqual("symlink_refused", result["refusal_code"])
        os.link(self.path, os.path.join(self.data_dir, "hardlink.json"))
        result = self.execute(apply=True)
        self.assertEqual("hardlinked_file", result["refusal_code"])
        self.assertEqual(self.raw, self.bytes())

    def test_parent_symlink_refused(self):
        link = os.path.join(self.temp.name, "parent-link")
        os.symlink(self.data_dir, link)
        result = self.execute(apply=True, path=os.path.join(link, "content.json"))
        self.assertEqual("filesystem_operation_failed", result["refusal_code"])
        self.assertEqual(self.raw, self.bytes())

    def test_lock_symlink_hardlink_and_busy_lock_refused(self):
        lockpath = self.path + ".lock"
        os.symlink(self.path, lockpath)
        self.assertEqual("symlink_lock_refused", self.execute(apply=True)["refusal_code"])
        os.unlink(lockpath)
        with open(lockpath, "wb") as handle:
            handle.write(b"")
        os.link(lockpath, lockpath + ".other")
        self.assertEqual("hardlinked_file", self.execute(apply=True)["refusal_code"])
        os.unlink(lockpath + ".other")
        with open(lockpath, "r+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual("content_lock_busy", self.execute(apply=True)["refusal_code"])
        self.assertEqual(self.raw, self.bytes())

    def test_release_overlay_guard_preserves_metadata(self):
        self.document["meta"]["content_release"] = "older"
        raw = self.write(self.document)
        result = self.execute(apply=True)
        self.assertEqual("content_release_unexpected", result["refusal_code"])
        self.assertEqual(raw, self.bytes())

    def test_nonprivate_backup_directory_refused(self):
        os.mkdir(self.backup_dir, 0o755)
        os.chmod(self.backup_dir, 0o755)
        result = self.execute(apply=True)
        self.assertEqual("backup_directory_not_private", result["refusal_code"])
        self.assertEqual(self.raw, self.bytes())

    def test_backup_under_webroot_refused(self):
        result = self.execute(apply=True, backup=INSERT.PUBLIC_ROOT + "/unsafe-backups")
        self.assertEqual("backup_inside_webroot", result["refusal_code"])
        self.assertEqual(self.raw, self.bytes())

    def test_directory_and_fifo_content_refused_without_blocking(self):
        self.assertEqual("non_regular_file", self.execute(path=self.data_dir)["refusal_code"])
        os.unlink(self.path)
        os.mkfifo(self.path)
        self.assertEqual("non_regular_file", self.execute()["refusal_code"])

    def test_canonical_candidate_ci_gate_accepts_only_exact_source(self):
        self.document["events"].append(copy.deepcopy(INSERT.CANDIDATE))
        self.write(self.document)
        self.assertTrue(INSERT.verify_source(self.path)["verified"])
        self.document["events"][-1]["time"] = "2:00 PM"
        self.write(self.document)
        result = INSERT.verify_source(self.path)
        self.assertFalse(result["verified"])
        self.assertEqual("canonical_candidate_mismatch", result["refusal_code"])


if __name__ == "__main__":
    unittest.main()
