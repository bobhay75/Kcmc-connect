import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from orchestrator import prepare_service  # noqa: E402
from service_agent import build_editable_song_deck, sha256_file  # noqa: E402


class OrchestratorTests(unittest.TestCase):
    def _catalog(self, root: Path) -> Path:
        catalog = root / "catalog.json"
        catalog.write_text(json.dumps({
            "confirmation": {"status": "confirmed", "method": "sha256-manifest"},
            "segments": [],
        }), encoding="utf-8")
        return catalog

    def test_existing_missing_and_created_flow(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "archive"
            archive.mkdir()
            existing_path = Path(build_editable_song_deck(
                "Existing Song", "User supplied text", str(archive / "Existing Song.pptx")
            ))
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({
                "confirmation": {"status": "confirmed", "method": "sha256-manifest"},
                "segments": [{
                    "title": "Existing Song",
                    "source_deck": existing_path.name,
                    "source_sha256": sha256_file(existing_path),
                }],
            }), encoding="utf-8")

            result = prepare_service(
                "Sunday Front Porch",
                [
                    {"title": "Existing Song"},
                    {"title": "Missing Song"},
                    {"title": "New Supplied Song", "lyrics": "Line one\n\nLine two"},
                ],
                str(catalog),
                str(archive),
                str(root / "out"),
            )

            self.assertEqual(result["status"], "AWAITING_PASTOR_APPROVAL")
            self.assertFalse(result["ready_for_approval"])
            self.assertEqual(result["items"][0]["status"], "REUSED_EXISTING")
            self.assertEqual(result["items"][1]["status"], "NEEDS_HUMAN_INPUT")
            self.assertEqual(result["items"][2]["status"], "CREATED_DRAFT")
            self.assertTrue(result["items"][2]["qa"]["ok"])
            self.assertTrue(Path(result["final_deck"]).is_file())
            self.assertEqual(result["summary"]["assembled_slides"], 3)

    def test_filename_match_cannot_bypass_confirmation_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "archive"
            archive.mkdir()
            build_editable_song_deck("Unconfirmed Song", "Archive text", str(archive / "Unconfirmed Song.pptx"))
            result = prepare_service(
                "Sunday Front Porch",
                [{"title": "Unconfirmed Song"}],
                str(self._catalog(root)),
                str(archive),
                str(root / "out"),
            )
            self.assertEqual(result["items"][0]["status"], "NEEDS_HUMAN_INPUT")
            self.assertEqual(result["summary"]["assembled_slides"], 0)

    def test_changed_confirmed_deck_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "archive"
            archive.mkdir()
            deck = Path(build_editable_song_deck("Confirmed Song", "Old text", str(archive / "Confirmed Song.pptx")))
            confirmed_hash = sha256_file(deck)
            build_editable_song_deck("Confirmed Song", "Changed text", str(deck))
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({
                "confirmation": {"status": "confirmed", "method": "sha256-manifest"},
                "segments": [{
                    "title": "Confirmed Song",
                    "source_deck": deck.name,
                    "source_sha256": confirmed_hash,
                }],
            }), encoding="utf-8")
            result = prepare_service(
                "Sunday Front Porch",
                [{"title": "Confirmed Song"}],
                str(catalog),
                str(archive),
                str(root / "out"),
            )
            self.assertEqual(result["items"][0]["status"], "SOURCE_CONFIRMATION_FAILED")

    def test_complete_flow_stops_at_human_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "archive"
            archive.mkdir()
            result = prepare_service(
                "Sunday Front Porch",
                [{"title": "Authorized Draft", "lyrics": "Line one\nLine two"}],
                str(self._catalog(root)),
                str(archive),
                str(root / "out"),
            )
            self.assertTrue(result["ready_for_approval"], result)
            self.assertFalse(result["approved"])
            self.assertFalse(result["autopublish"])
            manifest = json.loads(Path(result["approval_manifest"]).read_text(encoding="utf-8"))
            self.assertIsNone(manifest["approval"]["decision"])
            self.assertFalse(manifest["autopublish"])
            self.assertEqual(manifest["final_deck_sha256"], result["final_deck_sha256"])
            self.assertEqual(len(manifest["final_deck_sha256"]), 64)
            page = Path(result["approval_ui"]).read_text(encoding="utf-8")
            self.assertIn("cannot publish or send anything", page)
            self.assertIn(result["final_deck_sha256"], page)
            self.assertIn("APPROVAL_RECOMMENDED", page)
            self.assertIn("identity_verified:false", page)

    def test_output_inside_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "archive"
            archive.mkdir()
            with self.assertRaises(ValueError):
                prepare_service(
                    "Sunday Front Porch",
                    [{"title": "Song", "lyrics": "Line"}],
                    str(self._catalog(root)),
                    str(archive),
                    str(archive / "output"),
                )

    def test_nonexistent_archive_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "not-created" / "archive"
            output = archive / "output"
            with self.assertRaises(ValueError):
                prepare_service(
                    "Sunday Front Porch",
                    [{"title": "Song", "lyrics": "Line"}],
                    str(self._catalog(root)),
                    str(archive),
                    str(output),
                )
            self.assertFalse(output.exists())

    def test_malformed_song_item_is_blocked_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "archive"
            archive.mkdir()
            result = prepare_service(
                "Sunday Front Porch",
                ["not an object"],
                str(self._catalog(root)),
                str(archive),
                str(root / "out"),
            )
            self.assertFalse(result["ready_for_approval"])
            self.assertEqual(result["items"][0]["status"], "NEEDS_HUMAN_INPUT")


if __name__ == "__main__":
    unittest.main()
