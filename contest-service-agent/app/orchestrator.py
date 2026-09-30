from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from pptx import Presentation

from service_agent import (
    KCMC_SLIDE_HEIGHT,
    KCMC_SLIDE_WIDTH,
    append_slides_from_deck,
    build_editable_song_deck,
    find_song_in_archive,
    find_song_in_catalog,
    quality_check_deck,
    resolve_archive_source,
    write_approval_manifest,
    write_approval_ui,
)


@dataclass
class ServiceItem:
    title: str
    status: str
    source: str | None = None
    slides_added: int = 0
    qa: dict | None = None
    needs_lyrics: bool = False
    needs_selection: bool = False
    detail: str | None = None


def safe_slug(value: str, fallback: str = "service") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug[:80].strip("-") or fallback)


def _source_label(path: str, archive_root: str) -> str:
    source = Path(path).resolve()
    root = Path(archive_root).resolve()
    if source.is_relative_to(root):
        return str(source.relative_to(root))
    return source.name


def _new_deck() -> Presentation:
    deck = Presentation()
    deck.slide_width = KCMC_SLIDE_WIDTH
    deck.slide_height = KCMC_SLIDE_HEIGHT
    return deck


def _append_existing(
    final_deck: Presentation,
    title: str,
    match: dict,
    archive_root: str,
) -> ServiceItem | None:
    source_result = resolve_archive_source(match.get("source"), archive_root)
    if source_result.get("status") != "found":
        return None
    source_path = str(source_result["path"])
    source_qa = quality_check_deck(source_path, expected_font=None, expected_font_size_pt=None)
    if not source_qa.get("ok"):
        return ServiceItem(
            title=title,
            status="QA_FAILED",
            source=_source_label(source_path, archive_root),
            qa=source_qa,
            detail="Existing deck failed editability or layout checks.",
        )
    copied = append_slides_from_deck(
        final_deck,
        source_path,
        int(match["start_slide"]) if match.get("start_slide") else None,
        int(match["end_slide"]) if match.get("end_slide") else None,
    )
    if not copied.get("ok"):
        return ServiceItem(
            title=title,
            status="QA_FAILED",
            source=_source_label(source_path, archive_root),
            qa={"ok": False, "errors": [copied.get("error")], "warnings": []},
            detail="The selected archive slide range could not be assembled.",
        )
    return ServiceItem(
        title=title,
        status="REUSED_EXISTING",
        source=_source_label(source_path, archive_root),
        slides_added=int(copied["slides_added"]),
        qa=source_qa,
    )


def prepare_service(
    service_name: str,
    songs: list[dict],
    catalog_path: str,
    archive_root: str,
    output_root: str,
    service_style: str = "Front Porch",
) -> dict:
    """Build one editable service deck and stop at the human approval gate.

    Each song requires a title and may include authorized lyrics. The pipeline searches
    metadata first, then the private archive. It never fetches or invents lyrics.
    """
    service_name = service_name.strip()
    if not service_name:
        raise ValueError("Service name is required.")
    if not isinstance(songs, list) or not songs:
        raise ValueError("At least one song request is required.")
    started = time.monotonic()
    out = Path(output_root).expanduser().resolve()
    archive = Path(archive_root).expanduser().resolve()
    if archive.is_dir() and out.is_relative_to(archive):
        raise ValueError("Output directory must be outside the private source archive.")
    out.mkdir(parents=True, exist_ok=True)
    asset_dir = out / "draft-assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    final_deck = _new_deck()
    items: list[ServiceItem] = []

    for position, song in enumerate(songs, start=1):
        if not isinstance(song, dict):
            items.append(
                ServiceItem(
                    title=f"Invalid item {position}",
                    status="NEEDS_HUMAN_INPUT",
                    detail="Each song request must be an object with a title.",
                    needs_selection=True,
                )
            )
            continue
        title = str(song.get("title") or "").strip()
        if not title:
            items.append(
                ServiceItem(
                    title=f"Untitled item {position}",
                    status="NEEDS_HUMAN_INPUT",
                    detail="Song title is required.",
                    needs_selection=True,
                )
            )
            continue

        match = find_song_in_catalog(title, catalog_path)
        if match.get("status") == "ambiguous":
            items.append(
                ServiceItem(
                    title=title,
                    status="NEEDS_HUMAN_SELECTION",
                    needs_selection=True,
                    detail="More than one catalog match has the same score.",
                )
            )
            continue

        existing = _append_existing(final_deck, title, match, str(archive)) if match.get("status") == "found" else None
        if existing is None:
            archive_match = find_song_in_archive(title, str(archive))
            if archive_match.get("status") == "ambiguous":
                items.append(
                    ServiceItem(
                        title=title,
                        status="NEEDS_HUMAN_SELECTION",
                        needs_selection=True,
                        detail="More than one archive file matches this title.",
                    )
                )
                continue
            if archive_match.get("status") == "found":
                existing = _append_existing(final_deck, title, archive_match, str(archive))

        if existing is not None:
            items.append(existing)
            continue

        raw_lyrics = song.get("lyrics")
        lyrics = raw_lyrics.strip() if isinstance(raw_lyrics, str) else ""
        if not lyrics:
            items.append(
                ServiceItem(
                    title=title,
                    status="NEEDS_HUMAN_INPUT",
                    needs_lyrics=True,
                    detail="Authorized lyrics or an approved archive deck are required.",
                )
            )
            continue

        name = f"{position:02d}-{safe_slug(title, 'song')}.pptx"
        deck_path = build_editable_song_deck(title, lyrics, str(asset_dir / name), service_style)
        qa = quality_check_deck(deck_path)
        slides_added = 0
        status = "CREATED_DRAFT"
        detail = None
        if qa.get("ok"):
            copied = append_slides_from_deck(final_deck, deck_path)
            if copied.get("ok"):
                slides_added = int(copied["slides_added"])
            else:
                status = "QA_FAILED"
                detail = "Generated slides could not be added to the complete service deck."
                qa = {"ok": False, "errors": [copied.get("error")], "warnings": []}
        else:
            status = "QA_FAILED"
            detail = "Generated deck failed editability or layout checks."
        items.append(
            ServiceItem(
                title=title,
                status=status,
                source=str(Path("draft-assets") / name),
                slides_added=slides_added,
                qa=qa,
                detail=detail,
            )
        )

    payload = [asdict(item) for item in items]
    final_path: Path | None = None
    final_qa: dict | None = None
    if len(final_deck.slides):
        final_path = out / f"{safe_slug(service_name, 'kcmc-service')}.pptx"
        final_deck.core_properties.title = service_name
        final_deck.core_properties.subject = "KCMC approval draft; human approval required"
        final_deck.save(final_path)
        final_qa = quality_check_deck(str(final_path), expected_font=None, expected_font_size_pt=None)

    complete_statuses = {"REUSED_EXISTING", "CREATED_DRAFT"}
    ready_for_approval = bool(items) and all(
        item.status in complete_statuses and (item.qa is None or item.qa.get("ok")) for item in items
    ) and bool(final_qa and final_qa.get("ok"))

    manifest_path = out / "approval.json"
    manifest = write_approval_manifest(
        service_name,
        payload,
        str(manifest_path),
        final_path.name if final_path else None,
        final_qa,
    )
    approval_ui = write_approval_ui(service_name, payload, str(out / "approval.html"))
    result = {
        "schema_version": 2,
        "service": service_name,
        "service_style": service_style,
        "status": "AWAITING_PASTOR_APPROVAL",
        "items": payload,
        "summary": {
            "requested": len(items),
            "reused": sum(item.status == "REUSED_EXISTING" for item in items),
            "created": sum(item.status == "CREATED_DRAFT" for item in items),
            "blocked": sum(item.status not in complete_statuses for item in items),
            "assembled_slides": len(final_deck.slides),
        },
        "final_deck": str(final_path) if final_path else None,
        "final_qa": final_qa,
        "approval_manifest": manifest,
        "approval_ui": approval_ui,
        "ready_for_approval": ready_for_approval,
        "approved": False,
        "autopublish": False,
        "pipeline_seconds": round(time.monotonic() - started, 3),
    }
    (out / "production-report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
