from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from orchestrator import prepare_service
from service_agent import build_editable_song_deck


def test_existing_and_missing_song_flow(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    build_editable_song_deck("Existing Song", "User supplied text", str(archive / "Existing Song.pptx"))
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"source_deck": "service.pptx", "segments": []}), encoding="utf-8")

    result = prepare_service(
        "Sunday Front Porch",
        [
            {"title": "Existing Song"},
            {"title": "Missing Song"},
            {"title": "New Supplied Song", "lyrics": "Line one\n\nLine two"},
        ],
        str(catalog), str(archive), str(tmp_path / "out")
    )

    assert result["status"] == "AWAITING_PASTOR_APPROVAL"
    assert result["ready_for_approval"] is False
    assert result["items"][0]["status"] == "FOUND_EXISTING"
    assert result["items"][1]["status"] == "NEEDS_HUMAN_INPUT"
    assert result["items"][2]["status"] == "CREATED_DRAFT"
    assert result["items"][2]["qa"]["ok"] is True
