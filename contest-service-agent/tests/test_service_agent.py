from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from service_agent import normalize, build_editable_song_deck, quality_check_deck, find_song_in_archive


def test_normalize():
    assert normalize("Great Are You, Lord!") == "greatareyoulord"


def test_build_and_qa(tmp_path):
    deck = build_editable_song_deck("Test", "Verse one\n\nVerse two", str(tmp_path / "test.pptx"))
    qa = quality_check_deck(deck)
    assert qa["ok"] is True
    assert qa["slides"] == 2
    assert qa["editable_text_shapes"] >= 2


def test_archive_search(tmp_path):
    build_editable_song_deck("Amazing Grace", "Amazing grace", str(tmp_path / "Amazing Grace.pptx"))
    result = find_song_in_archive("Amazing Grace", str(tmp_path))
    assert result["status"] == "found"
