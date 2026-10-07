"""Meaningful isolated fixtures for the read-only public-event planner."""
import copy
import datetime
import hashlib
import importlib.util
import json
import os
import stat
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "content_review", os.path.join(os.path.dirname(__file__), "content-review.py"))
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
AS_OF = REVIEW._parse_as_of("2026-10-07T15:00:00Z")


class ContentReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "content.json")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, document):
        raw = json.dumps(document, ensure_ascii=False).encode("utf-8")
        with open(self.path, "wb") as handle:
            handle.write(raw)
        os.chmod(self.path, 0o640)
        return raw

    def review(self, as_of=AS_OF, path=None):
        return REVIEW._review_host_file(path or self.path, as_of)

    def test_missing_preserves_all_bytes_mode_and_private_values(self):
        private = {"events": [], "bulletin": {"date": "2026-09-27", "notes": ["", "PRIVATE_MESSAGE_NOTE"]},
                   "stats": {"secret": "PRIVATE_STAT"}, "staff": [{"name": "PRIVATE_STAFF_NAME"}]}
        raw = self.write(private)
        result = self.review()
        self.assertEqual("missing", result["verdict"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result["host_file_sha256"])
        with open(self.path, "rb") as handle:
            self.assertEqual(raw, handle.read())
        self.assertEqual(0o640, stat.S_IMODE(os.stat(self.path).st_mode))
        output = json.dumps(result)
        for value in ["PRIVATE_MESSAGE_NOTE", "PRIVATE_STAT", "PRIVATE_STAFF_NAME", "bulletin", "stats", "staff"]:
            self.assertNotIn(value, output)
        self.assertFalse(result["writes_performed"])

    def test_exact_candidate_already_same(self):
        self.write({"events": [copy.deepcopy(REVIEW.CANDIDATE)]})
        self.assertEqual("already_same", self.review()["verdict"])

    def test_same_id_conflict_does_not_leak_host_changed_fields(self):
        event = copy.deepcopy(REVIEW.CANDIDATE)
        event["description"] = "PRIVATE_HOST_OVERRIDE"
        event["staff_notes"] = "PRIVATE_STAFF_NOTE"
        self.write({"events": [event]})
        result = self.review()
        self.assertEqual("same_id_conflict", result["verdict"])
        self.assertNotIn("PRIVATE_HOST_OVERRIDE", json.dumps(result))
        self.assertNotIn("PRIVATE_STAFF_NOTE", json.dumps(result))

    def test_whitespace_equivalent_candidate_id_is_conflict(self):
        event = copy.deepcopy(REVIEW.CANDIDATE)
        event["id"] = "  " + event["id"] + "\t"
        self.write({"events": [event]})
        result = self.review()
        self.assertEqual("same_id_conflict", result["verdict"])
        self.assertFalse(result["possible_duplicate"])

    def test_possible_duplicate_normalizes_title_date_and_clock(self):
        event = copy.deepcopy(REVIEW.CANDIDATE)
        event.update(id="PRIVATE_ALTERNATE_ID", title="  HOPE Keepers - First   Gathering ",
                     date="2026-10-13", time="13:00", description="PRIVATE_DUPLICATE_BODY")
        self.write({"events": [event]})
        result = self.review()
        self.assertEqual("possible_duplicate", result["verdict"])
        self.assertTrue(result["possible_duplicate"])
        self.assertNotIn("PRIVATE_ALTERNATE_ID", json.dumps(result))
        self.assertNotIn("PRIVATE_DUPLICATE_BODY", json.dumps(result))

    def test_short_ministry_title_at_same_date_time_flags_possible_duplicate(self):
        event = copy.deepcopy(REVIEW.CANDIDATE)
        event.update(id="PRIVATE_SHORT_TITLE_ID", title="  HOPE   KEEPERS ", time="1PM")
        self.write({"events": [event]})
        result = self.review()
        self.assertEqual("possible_duplicate", result["verdict"])
        self.assertTrue(result["possible_duplicate"])
        self.assertNotIn("PRIVATE_SHORT_TITLE_ID", json.dumps(result))

    def test_short_title_requires_same_date_time_and_does_not_match_other_suffixes(self):
        event = copy.deepcopy(REVIEW.CANDIDATE)
        event.update(id="other-event", title="Hope Keepers", date="2026-10-20")
        self.write({"events": [event]})
        self.assertEqual("missing", self.review()["verdict"])
        event.update(date="2026-10-13", time="2PM")
        self.write({"events": [event]})
        self.assertEqual("missing", self.review()["verdict"])
        event.update(time="1PM", title="Hope Keepers Planning")
        self.write({"events": [event]})
        self.assertEqual("missing", self.review()["verdict"])

    def test_exact_and_possible_duplicate_both_flagged(self):
        alternate = copy.deepcopy(REVIEW.CANDIDATE)
        alternate["id"] = "other-event"
        self.write({"events": [copy.deepcopy(REVIEW.CANDIDATE), alternate]})
        result = self.review()
        self.assertEqual("already_same", result["verdict"])
        self.assertTrue(result["possible_duplicate"])

    def test_other_date_or_clock_does_not_infer_recurrence(self):
        event = copy.deepcopy(REVIEW.CANDIDATE)
        event.update(id="other-week", date="2026-10-20")
        self.write({"events": [event]})
        self.assertEqual("missing", self.review()["verdict"])
        event.update(date="2026-10-13", time="2 PM")
        self.write({"events": [event]})
        self.assertEqual("missing", self.review()["verdict"])

    def test_duplicate_event_ids_refused_without_leak(self):
        self.write({"events": [{"id": "PRIVATE_ID"}, {"id": " PRIVATE_ID "}]})
        result = self.review()
        self.assertEqual("duplicate_event_ids", result["refusal_code"])
        self.assertEqual("refused", result["verdict"])
        self.assertNotIn("PRIVATE_ID", json.dumps(result))

    def test_duplicate_json_keys_refused(self):
        with open(self.path, "wb") as handle:
            handle.write(b'{"events": [], "private": "a", "private": "b"}')
        self.assertEqual("duplicate_json_keys", self.review()["refusal_code"])

    def test_invalid_json_and_nan_refused(self):
        for raw in [b'{"events":', b'{"events": [], "private": NaN}', b'\xff']:
            with open(self.path, "wb") as handle:
                handle.write(raw)
            self.assertEqual("invalid_json", self.review()["refusal_code"])

    def test_malformed_events_refused(self):
        for document, code in [({}, "invalid_event_container"),
                               ({"events": {}}, "invalid_event_container"),
                               ({"events": [1]}, "invalid_event_record"),
                               ({"events": [{"id": ""}]}, "invalid_event_id")]:
            self.write(document)
            self.assertEqual(code, self.review()["refusal_code"])

    def test_symlink_file_and_parent_refused(self):
        self.write({"events": []})
        link = os.path.join(self.temp.name, "link.json")
        os.symlink(self.path, link)
        self.assertEqual("symlink_refused", self.review(path=link)["refusal_code"])
        parent = os.path.join(self.temp.name, "parent-link")
        os.symlink(self.temp.name, parent)
        self.assertEqual("symlink_refused", self.review(path=os.path.join(parent, "content.json"))["refusal_code"])

    def test_directory_and_fifo_refused_without_blocking(self):
        self.assertEqual("non_regular_host_file", self.review(path=self.temp.name)["refusal_code"])
        os.mkfifo(self.path)
        self.assertEqual("non_regular_host_file", self.review()["refusal_code"])

    def test_candidate_expiration_uses_source_offset(self):
        self.write({"events": []})
        self.assertEqual("missing", self.review(REVIEW._parse_as_of("2026-10-14T04:59:59Z"))["verdict"])
        result = self.review(REVIEW._parse_as_of("2026-10-14T05:00:00Z"))
        self.assertEqual("expired_candidate", result["refusal_code"])
        self.assertIsNone(result["host_file_sha256"])

    def test_expired_candidate_refused_before_host_read(self):
        result = self.review(REVIEW._parse_as_of("2026-10-15"))
        self.assertEqual("expired_candidate", result["refusal_code"])

    def test_as_of_requires_utc_syntax_and_real_calendar_date(self):
        self.assertEqual(datetime.timedelta(0), AS_OF.utcoffset())
        for value in ["2026-10-07T15:00:00-05:00", "2026-02-30", "tomorrow"]:
            with self.assertRaises(Exception):
                REVIEW._parse_as_of(value)


if __name__ == "__main__":
    unittest.main()
