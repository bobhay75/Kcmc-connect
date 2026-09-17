from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from pptx import Presentation

MAX_DECK_BYTES = 100 * 1024 * 1024

@dataclass
class Segment:
    title_fingerprint: str
    role: str
    service_style: str
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


def read_deck_snapshot(path: Path) -> tuple[bytes, str]:
    with path.open("rb") as source_file:
        source_bytes = source_file.read(MAX_DECK_BYTES + 1)
    if len(source_bytes) > MAX_DECK_BYTES:
        raise ValueError("PowerPoint exceeds the 100 MB safety limit.")
    return source_bytes, hashlib.sha256(source_bytes).hexdigest()


def title_fingerprint(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", title.lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def reviewed_slide_number(value: object) -> int:
    """Accept only an exact positive integer, never bool or fractional input."""
    if isinstance(value, bool):
        raise ValueError("Segment ranges must use positive integer slide numbers.")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value.strip()):
        number = int(value.strip())
    else:
        raise ValueError("Segment ranges must use positive integer slide numbers.")
    if number < 1:
        raise ValueError("Segment ranges must use positive integer slide numbers.")
    return number


def extract_catalog(path: Path, source_bytes: bytes, segment_definitions: list[dict]) -> dict:
    """Build reusable records only from explicit, human-reviewed slide ranges."""
    prs = Presentation(io.BytesIO(source_bytes))
    segments: list[Segment] = []
    digest = hashlib.sha256(source_bytes).hexdigest()
    for definition in segment_definitions:
        if not isinstance(definition, dict):
            raise ValueError("Every segment definition must be an object.")
        title = str(definition.get("title") or "").strip()
        role = str(definition.get("role") or "").strip().lower()
        service_style = str(definition.get("service_style") or "").strip()
        start = reviewed_slide_number(definition.get("start_slide"))
        end = reviewed_slide_number(definition.get("end_slide"))
        if not title or role != "song" or service_style != "Front Porch":
            raise ValueError("Each segment requires a title, role=song, and verified Front Porch style.")
        if start < 1 or end < start or end > len(prs.slides):
            raise ValueError("Segment range is outside the confirmed deck.")
        subset = [prs.slides[i - 1] for i in range(start, end + 1)]
        blank = sum(1 for slide in subset if not slide_lines(slide))
        font, size, alignment = style_fingerprint(subset)
        segments.append(
            Segment(
                title_fingerprint=title_fingerprint(title),
                role=role,
                service_style=service_style,
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
        "confirmation": {"status": "confirmed", "method": "sha256-and-human-reviewed-ranges"},
        "privacy_note": "Human-supplied titles are stored only as normalized SHA-256 fingerprints; readable slide text is excluded.",
    }


def load_confirmation_manifest(path: Path) -> dict[str, dict]:
    """Load exact deck hashes and explicit ranges approved by an authorized human."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid confirmation manifest: {path}") from exc
    approved: dict[str, dict] = {}
    for item in payload.get("approved_decks", []):
        if not isinstance(item, dict):
            continue
        source = str(item.get("source_deck") or "").strip()
        digest = str(item.get("sha256") or "").strip().lower()
        if source and re.fullmatch(r"[a-f0-9]{64}", digest):
            segments = item.get("segments")
            approved[source] = {
                "sha256": digest,
                "segments": segments if isinstance(segments, list) else [],
            }
    if not approved:
        raise ValueError("Confirmation manifest contains no approved deck hashes.")
    return approved


def build_archive_catalog(archive_root: Path, approved_decks: dict[str, object]) -> dict:
    """Index only snapshot-matched decks and human-reviewed slide ranges."""
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
        approval = approved_decks.get(relative)
        expected_digest = str(approval.get("sha256") or "") if isinstance(approval, dict) else str(approval or "")
        segment_definitions = approval.get("segments", []) if isinstance(approval, dict) else []
        try:
            source_bytes, digest = read_deck_snapshot(path)
        except (OSError, ValueError) as exc:
            errors.append({"source_deck": relative, "error": type(exc).__name__})
            continue
        if expected_digest != digest:
            unconfirmed_decks.append(
                {
                    "source_deck": relative,
                    "reason": "not_in_manifest" if approval is None else "hash_mismatch",
                }
            )
            continue
        try:
            catalog = extract_catalog(path, source_bytes, segment_definitions)
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
            songs.append(item)

    by_title: dict[str, list[dict]] = {}
    for song in songs:
        by_title.setdefault(song["title_fingerprint"], []).append(song)
    duplicates = [
        {
            "title_fingerprint": fingerprint,
            "occurrences": [
                {
                    "source_deck": item["source_deck"],
                    "start_slide": item["start_slide"],
                    "end_slide": item["end_slide"],
                }
                for item in occurrences
            ],
        }
        for fingerprint, occurrences in sorted(by_title.items())
        if fingerprint and len(occurrences) > 1
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
        "confirmation": {"status": "confirmed", "method": "sha256-and-human-reviewed-ranges"},
        "privacy_note": "Readable slide text, speaker notes, and slide images are not exported. Human-supplied titles are normalized SHA-256 fingerprints.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a private KCMC catalog from confirmed decks and reviewed ranges.")
    parser.add_argument("source", type=Path, help="Approved private archive directory")
    parser.add_argument("--out", type=Path, default=Path("song_catalog.json"))
    parser.add_argument(
        "--confirmation-manifest",
        type=Path,
        required=True,
        help="JSON file containing approved_decks with exact hashes and human-reviewed segments",
    )
    args = parser.parse_args()
    approved = load_confirmation_manifest(args.confirmation_manifest)
    if not args.source.is_dir():
        raise SystemExit("Source must be an approved private archive directory.")
    catalog = build_archive_catalog(args.source, approved)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    args.out.chmod(0o600)
    count = catalog.get("song_count", len(catalog.get("segments", [])))
    print(f"Wrote {count} song records to {args.out}")


if __name__ == "__main__":
    main()
