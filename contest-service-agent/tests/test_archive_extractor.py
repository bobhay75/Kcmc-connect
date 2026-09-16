import sys
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from archive_extractor import build_archive_catalog  # noqa: E402


def make_source_deck(path: Path, title: str) -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    for text in (title, "Authorized source text"):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(10), Inches(4))
        box.text = text
    prs.save(path)


class ArchiveExtractorTests(unittest.TestCase):
    def test_directory_catalog_reports_duplicates_without_lyrics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_source_deck(root / "one.pptx", "Same Song")
            make_source_deck(root / "two.pptx", "Same Song")
            catalog = build_archive_catalog(root)
            self.assertEqual(catalog["schema_version"], 2)
            self.assertEqual(catalog["deck_count"], 2)
            self.assertEqual(catalog["song_count"], 2)
            self.assertEqual(len(catalog["duplicates"]), 1)
            self.assertNotIn("Authorized source text", str(catalog))


if __name__ == "__main__":
    unittest.main()
