from pathlib import Path
from service_agent import build_editable_song_deck, quality_check_deck, write_approval_manifest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo-output"

# Synthetic demo text keeps the public repository copyright-safe.
lyrics = "Sample worship line one\nSample worship line two\n\nSample chorus line one\nSample chorus line two"
deck = build_editable_song_deck("Sample Worship Song", lyrics, str(OUT / "sample-worship-song.pptx"), "Front Porch")
qa = quality_check_deck(deck)
manifest = write_approval_manifest("Sunday Front Porch", [{"title": "Sample Worship Song", "deck": deck, "qa": qa}], str(OUT / "approval.json"))
print({"deck": deck, "qa": qa, "approval_manifest": manifest})
