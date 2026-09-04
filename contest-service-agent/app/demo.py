from pathlib import Path
from service_agent import build_editable_song_deck, quality_check_deck, write_approval_manifest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo-output"

lyrics = "Great are You, Lord\n\nIt's Your breath in our lungs\nSo we pour out our praise"
deck = build_editable_song_deck("Great Are You Lord", lyrics, str(OUT / "great-are-you-lord.pptx"), "Contemporary")
qa = quality_check_deck(deck)
manifest = write_approval_manifest("Sunday 10:30 Contemporary", [{"title": "Great Are You Lord", "deck": deck, "qa": qa}], str(OUT / "approval.json"))
print({"deck": deck, "qa": qa, "approval_manifest": manifest})
