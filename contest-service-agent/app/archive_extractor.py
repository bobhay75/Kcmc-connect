from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from pptx import Presentation

TITLE_MAX_CHARS = 70
TITLE_MAX_LINES = 3
CCLI_RE = re.compile(r"\bCCLI\b", re.I)

@dataclass
class Segment:
    title: str
    start_slide: int
    end_slide: int
    slide_count: int
    blank_slides: int
    dominant_font: str | None
    dominant_font_size_pt: float | None
    dominant_alignment: str | None
    source_deck: str
    source_sha256: str


def slide_lines(slide) -> list[str]:
    lines: list[str] = []
    for shape in slide.shapes:
        if not getattr(shape, "has_text_frame", False):
            continue
        for raw in shape.text.splitlines():
            text = " ".join(raw.split()).strip()
            if text:
                lines.append(text)
    return lines


def normalized_title(lines: list[str]) -> str | None:
    if not lines:
        return None
    filtered = [line for line in lines if not CCLI_RE.search(line)]
    if not filtered:
        return None
    candidate = " ".join(filtered).strip()
    if len(candidate) > TITLE_MAX_CHARS or len(filtered) > TITLE_MAX_LINES:
        return None
    return candidate


def looks_like_title(slide, previous_blank: bool, next_has_text: bool) -> bool:
    lines = slide_lines(slide)
    title = normalized_title(lines)
    if not title or not next_has_text:
        return False
    if len(title.split()) <= 8 and len(title) <= 55:
        return True
    return previous_blank and len(title) <= TITLE_MAX_CHARS


def style_fingerprint(slides: Iterable) -> tuple[str | None, float | None, str | None]:
    fonts: Counter[str] = Counter()
    sizes: Counter[float] = Counter()
    aligns: Counter[str] = Counter()
    for slide in slides:
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            for paragraph in shape.text_frame.paragraphs:
                if paragraph.alignment is not None:
                    aligns[str(paragraph.alignment)] += 1
                for run in paragraph.runs:
                    if not run.text.strip():
                        continue
                    if run.font.name:
                        fonts[run.font.name] += 1
                    if run.font.size:
                        sizes[round(run.font.size.pt, 1)] += 1
    return (
        fonts.most_common(1)[0][0] if fonts else None,
        sizes.most_common(1)[0][0] if sizes else None,
        aligns.most_common(1)[0][0] if aligns else None,
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_catalog(path: Path, confirmed: bool = False) -> dict:
    prs = Presentation(str(path))
    text_flags = [bool(slide_lines(s)) for s in prs.slides]
    candidates: list[tuple[int, str]] = []
    for idx, slide in enumerate(prs.slides):
        prev_blank = idx > 0 and not text_flags[idx - 1]
        next_has_text = idx + 1 < len(prs.slides) and text_flags[idx + 1]
        title = normalized_title(slide_lines(slide))
        terminal_card = idx == len(prs.slides) - 1 and bool(title) and title.lower().startswith("thanks for")
        if terminal_card or looks_like_title(slide, prev_blank, next_has_text):
            if title:
                candidates.append((idx + 1, title))

    cleaned: list[tuple[int, str]] = []
    for item in candidates:
        if cleaned and item[0] - cleaned[-1][0] == 1:
            cleaned[-1] = item
        else:
            cleaned.append(item)

    segments: list[Segment] = []
    digest = sha256(path)
    for pos, (start, title) in enumerate(cleaned):
        end = (cleaned[pos + 1][0] - 1) if pos + 1 < len(cleaned) else len(prs.slides)
        if title.lower().startswith(("thanks for", "welcome home")):
            continue
        subset = [prs.slides[i - 1] for i in range(start, end + 1)]
        blank = sum(1 for slide in subset if not slide_lines(slide))
        font, size, alignment = style_fingerprint(subset)
        segments.append(
            Segment(
                title=title,
                start_slide=start,
                end_slide=end,
                slide_count=end - start + 1,
                blank_slides=blank,
                dominant_font=font,
                dominant_font_size_pt=size,
                dominant_alignment=alignment,
                source_deck=path.name,
                source_sha256=digest,
            )
        )

    return {
        "schema_version": 1,
        "source_deck": path.name,
        "slide_count": len(prs.slides),
        "source_sha256": digest,
        "segments": [asdict(s) for s in segments],
        "confirmation": {
            "status": "confirmed" if confirmed else "unconfirmed",
            "method": "sha256-manifest" if confirmed else None,
        },
        "copyright_note": "Catalog stores titles, slide ranges, and style metadata only; lyric text is intentionally excluded.",
    }


def load_confirmation_manifest(path: Path) -> dict[str, str]:
    """Load exact relative-path/SHA-256 pairs approved by an authorized human."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid confirmation manifest: {path}") from exc
    approved: dict[str, str] = {}
    for item in payload.get("approved_decks", []):
        if not isinstance(item, dict):
            continue
        source = str(item.get("source_deck") or "").strip()
        digest = str(item.get("sha256") or "").strip().lower()
        if source and re.fullmatch(r"[a-f0-9]{64}", digest):
            approved[source] = digest
    if not approved:
        raise ValueError("Confirmation manifest contains no approved deck hashes.")
    return approved


def build_archive_catalog(archive_root: Path, approved_decks: dict[str, str]) -> dict:
    """Index only hash-matched, human-confirmed PPTX files; never export lyrics."""
    root = archive_root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Archive directory does not exist: {root}")

    decks: list[dict] = []
    songs: list[dict] = []
    errors: list[dict] = []
    unconfirmed_decks: list[dict] = []
    paths: list[Path] = []
    for candidate in root.rglob("*.pptx"):
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if resolved.is_file() and resolved.is_relative_to(root):
            paths.append(resolved)

    for path in sorted(set(paths), key=lambda item: str(item).lower()):
        relative = str(path.relative_to(root))
        digest = sha256(path)
        expected_digest = approved_decks.get(relative)
        if expected_digest != digest:
            unconfirmed_decks.append(
                {
                    "source_deck": relative,
                    "reason": "not_in_manifest" if expected_digest is None else "hash_mismatch",
                }
            )
            continue
        try:
            catalog = extract_catalog(path, confirmed=True)
        except Exception as exc:
            errors.append({"source_deck": relative, "error": type(exc).__name__})
            continue
        decks.append(
            {
                "source_deck": relative,
                "slide_count": catalog["slide_count"],
                "source_sha256": catalog["source_sha256"],
                "song_count": len(catalog["segments"]),
            }
        )
        for segment in catalog["segments"]:
            item = dict(segment)
            item["source_deck"] = relative
            item["normalized_title"] = re.sub(r"[^a-z0-9]+", "", item["title"].lower())
            songs.append(item)

    by_title: dict[str, list[dict]] = {}
    for song in songs:
        by_title.setdefault(song["normalized_title"], []).append(song)
    duplicates = [
        {
            "normalized_title": title,
            "title": occurrences[0]["title"],
            "occurrences": [
                {
                    "source_deck": item["source_deck"],
                    "start_slide": item["start_slide"],
                    "end_slide": item["end_slide"],
                }
                for item in occurrences
            ],
        }
        for title, occurrences in sorted(by_title.items())
        if title and len(occurrences) > 1
    ]
    return {
        "schema_version": 2,
        "archive_root_name": root.name,
        "deck_count": len(decks),
        "song_count": len(songs),
        "decks": decks,
        "songs": songs,
        "duplicates": duplicates,
        "errors": errors,
        "unconfirmed_decks": unconfirmed_decks,
        "confirmation": {"status": "confirmed", "method": "sha256-manifest"},
        "copyright_note": "Metadata only. Lyrics, speaker notes, and slide images are not exported.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a searchable KCMC PowerPoint song catalog without exporting lyrics.")
    parser.add_argument("source", type=Path, help="One PPTX file or an approved archive directory")
    parser.add_argument("--out", type=Path, default=Path("song_catalog.json"))
    parser.add_argument(
        "--confirmation-manifest",
        type=Path,
        required=True,
        help="JSON file containing approved_decks with relative source_deck and sha256 values",
    )
    args = parser.parse_args()
    approved = load_confirmation_manifest(args.confirmation_manifest)
    if args.source.is_dir():
        catalog = build_archive_catalog(args.source, approved)
    else:
        digest = sha256(args.source)
        expected = approved.get(args.source.name)
        if expected != digest:
            raise SystemExit("Source deck is not confirmed by an exact SHA-256 manifest entry.")
        catalog = extract_catalog(args.source, confirmed=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    count = catalog.get("song_count", len(catalog.get("segments", [])))
    print(f"Wrote {count} song records to {args.out}")


if __name__ == "__main__":
    main()
