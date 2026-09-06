from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from service_agent import (
    build_editable_song_deck,
    find_song_in_archive,
    find_song_in_catalog,
    quality_check_deck,
    write_approval_manifest,
)


@dataclass
class ServiceItem:
    title: str
    status: str
    source: str | None = None
    qa: dict | None = None
    needs_lyrics: bool = False


def prepare_service(service_name: str, songs: list[dict], catalog_path: str, archive_root: str, output_root: str) -> dict:
    """Deterministic production pipeline used beneath the Strands agent.

    Each song dict requires title and may include lyrics. Existing assets are always
    preferred. Missing songs without supplied/licensed lyrics are surfaced for human
    input rather than fetched or invented.
    """
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    items: list[ServiceItem] = []

    for song in songs:
        title = song["title"]
        match = find_song_in_catalog(title, catalog_path)
        if match.get("status") != "found":
            match = find_song_in_archive(title, archive_root)

        if match.get("status") == "found":
            items.append(ServiceItem(title=title, status="FOUND_EXISTING", source=match.get("source")))
            continue

        lyrics = (song.get("lyrics") or "").strip()
        if not lyrics:
            items.append(ServiceItem(title=title, status="NEEDS_HUMAN_INPUT", needs_lyrics=True))
            continue

        safe_name = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
        deck = build_editable_song_deck(title, lyrics, str(out / f"{safe_name}.pptx"))
        qa = quality_check_deck(deck)
        items.append(ServiceItem(title=title, status="CREATED_DRAFT", source=deck, qa=qa))

    payload = [asdict(item) for item in items]
    manifest = write_approval_manifest(service_name, payload, str(out / "approval.json"))
    result = {
        "service": service_name,
        "status": "AWAITING_PASTOR_APPROVAL",
        "items": payload,
        "approval_manifest": manifest,
        "ready_for_approval": all(i.status != "NEEDS_HUMAN_INPUT" and (not i.qa or i.qa.get("ok")) for i in items),
    }
    (out / "production-report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
