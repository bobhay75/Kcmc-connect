from __future__ import annotations

import copy
import hashlib
import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TARGET_MODE as RTM
from pptx.opc.package import Part, _Relationship
from pptx.opc.packuri import PackURI
from pptx.util import Inches, Pt

KCMC_FONT = "Arial Narrow"
KCMC_FONT_SIZE_PT = 60
KCMC_SLIDE_WIDTH = Inches(13.333)
KCMC_SLIDE_HEIGHT = Inches(7.5)
SUPPORTED_SERVICE_STYLES = {"Front Porch"}
SUPPORTED_ITEM_TYPES = {"service_title", "song", "scripture", "sermon_title", "announcement", "blank"}
SLIDE_LAYOUT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
NOTES_SLIDE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
UNSAFE_RELATIONSHIP_MARKERS = (
    "oleobject",
    "package",
    "externallink",
    "attachedtemplate",
    "vbaproject",
    "activex",
)
UNSAFE_CONTENT_MARKERS = ("vbaproject", "oleobject", "activex", "macroenabled")


@dataclass
class SongMatch:
    title: str
    status: str
    source: str | None = None


def normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _match_score(target: str, candidate: str) -> int:
    if not target or not candidate:
        return 0
    if target == candidate:
        return 1000
    shorter = min(len(target), len(candidate))
    if shorter >= 6 and (target in candidate or candidate in target):
        return 500 - abs(len(target) - len(candidate))
    return 0


def _catalog_entries(data: dict) -> Iterable[dict]:
    default_source = data.get("source_deck")
    for key in ("segments", "songs"):
        for entry in data.get(key, []):
            if not isinstance(entry, dict):
                continue
            item = dict(entry)
            item.setdefault("source_deck", default_source)
            yield item


def _slide_number(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value.strip()):
        number = int(value.strip())
    else:
        return None
    return number if number > 0 else None


def find_song_in_catalog(title: str, catalog_path: str) -> dict:
    """Search a metadata-only KCMC catalog without reading or exporting lyrics."""
    path = Path(catalog_path)
    if not path.is_file():
        return asdict(SongMatch(title, "missing"))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"title": title, "status": "invalid_catalog"}
    if not isinstance(data, dict):
        return {"title": title, "status": "invalid_catalog"}
    confirmation = data.get("confirmation")
    if (
        not isinstance(confirmation, dict)
        or confirmation.get("status") != "confirmed"
        or confirmation.get("method") != "sha256-and-human-reviewed-ranges"
    ):
        return {
            "title": title,
            "status": "unconfirmed_catalog",
            "detail": "Catalog reuse requires exact source hashes and human-reviewed slide ranges.",
        }

    target = normalize(title)
    target_fingerprint = hashlib.sha256(target.encode("utf-8")).hexdigest()
    ranked: list[tuple[int, dict]] = []
    for entry in _catalog_entries(data):
        fingerprint = str(entry.get("title_fingerprint") or "").lower()
        if re.fullmatch(r"[a-f0-9]{64}", fingerprint):
            if fingerprint == target_fingerprint:
                ranked.append((1000, entry))
            continue
        candidate = normalize(str(entry.get("normalized_title") or entry.get("title") or ""))
        score = _match_score(target, candidate)
        if score:
            ranked.append((score, entry))
    if not ranked:
        return asdict(SongMatch(title, "missing"))

    ranked.sort(
        key=lambda pair: (
            -pair[0],
            str(pair[1].get("source_deck") or ""),
            _slide_number(pair[1].get("start_slide")) or 0,
        )
    )
    best_score = ranked[0][0]
    best = [entry for score, entry in ranked if score == best_score]
    identities = {
        (
            str(entry.get("source_deck") or ""),
            _slide_number(entry.get("start_slide")) or 0,
            _slide_number(entry.get("end_slide")) or 0,
        )
        for entry in best
    }
    if len(identities) > 1:
        return {
            "title": title,
            "status": "ambiguous",
            "matches": [
                {
                    "title": entry.get("title"),
                    "source": entry.get("source_deck"),
                    "start_slide": entry.get("start_slide"),
                    "end_slide": entry.get("end_slide"),
                }
                for entry in best
            ],
        }

    entry = best[0]
    source_sha256 = str(entry.get("source_sha256") or data.get("source_sha256") or "").lower()
    if not re.fullmatch(r"[a-f0-9]{64}", source_sha256):
        return {
            "title": title,
            "status": "invalid_catalog",
            "detail": "Matched catalog entry has no valid confirmed source hash.",
        }
    start_slide = _slide_number(entry.get("start_slide"))
    end_slide = _slide_number(entry.get("end_slide"))
    if start_slide is None or end_slide is None or end_slide < start_slide:
        return {
            "title": title,
            "status": "invalid_catalog",
            "detail": "Matched catalog entry requires an explicit valid human-reviewed slide range.",
        }
    if entry.get("role") != "song" or entry.get("service_style") != "Front Porch":
        return {
            "title": title,
            "status": "invalid_catalog",
            "detail": "Matched catalog entry is not approved as a Front Porch song segment.",
        }
    source_deck = str(entry.get("source_deck") or "").strip()
    if not source_deck:
        return {
            "title": title,
            "status": "invalid_catalog",
            "detail": "Matched catalog entry has no approved source deck.",
        }
    style = entry.get("style") if isinstance(entry.get("style"), dict) else {}
    return {
        "title": title,
        "matched_title": entry.get("title"),
        "status": "found",
        "source": source_deck,
        "source_sha256": source_sha256,
        "start_slide": start_slide,
        "end_slide": end_slide,
        "style": {
            "name": entry.get("style") if isinstance(entry.get("style"), str) else None,
            "font": entry.get("dominant_font") or style.get("font"),
            "font_size_pt": entry.get("dominant_font_size_pt") or style.get("font_size_pt"),
            "alignment": entry.get("dominant_alignment") or style.get("alignment"),
        },
    }


def resolve_archive_source(source: str | None, archive_root: str) -> dict:
    """Resolve catalog paths inside the approved archive root and reject traversal."""
    if not source:
        return {"status": "missing"}
    root = Path(archive_root).expanduser().resolve()
    if not root.is_dir():
        return {"status": "archive_unavailable"}

    raw = Path(source).expanduser()
    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    if not candidate.is_relative_to(root):
        return {"status": "blocked_path"}
    if candidate.is_file():
        return {"status": "found", "path": str(candidate)}

    return {"status": "missing"}


def _lyric_blocks(lyrics: str, max_lines: int = 4) -> list[str]:
    blocks: list[str] = []
    for stanza in re.split(r"\n\s*\n", lyrics.strip()):
        lines = [line.rstrip() for line in stanza.splitlines() if line.strip()]
        for index in range(0, len(lines), max_lines):
            block = "\n".join(lines[index : index + max_lines]).strip()
            if block:
                blocks.append(block)
    return blocks


def _private_file(path: Path) -> None:
    path.chmod(0o600)


def append_blank_slide(destination: Presentation) -> int:
    slide = destination.slides.add_slide(destination.slide_layouts[6])
    background = slide.background.fill
    background.solid()
    background.fore_color.rgb = RGBColor(0, 0, 0)
    # Keep the service cue visually blank while retaining one harmless drawable
    # object so package-integrity tooling can distinguish it from a broken slide.
    field = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0,
        0,
        destination.slide_width,
        destination.slide_height,
    )
    field.fill.solid()
    field.fill.fore_color.rgb = RGBColor(0, 0, 0)
    field.line.fill.background()
    return 1


def build_editable_text_deck(
    title: str,
    text: str,
    output_path: str,
    item_type: str,
    service_style: str = "Front Porch",
) -> str:
    """Create approved Front Porch text slides for a known service item role."""
    if service_style not in SUPPORTED_SERVICE_STYLES:
        raise ValueError(f"Unsupported service style: {service_style}")
    if item_type not in SUPPORTED_ITEM_TYPES - {"song", "blank"}:
        raise ValueError(f"Unsupported service item type: {item_type}")
    body = text.strip()
    if item_type in {"service_title", "sermon_title"} and not body:
        body = title.strip()
    if not body:
        raise ValueError(f"Text is required for {item_type}.")
    return _build_editable_blocks(title, body, output_path, service_style, item_type)


def _build_editable_blocks(
    title: str,
    text: str,
    output_path: str,
    service_style: str,
    item_type: str,
) -> str:
    if service_style not in SUPPORTED_SERVICE_STYLES:
        raise ValueError(f"Unsupported service style: {service_style}")
    blocks = _lyric_blocks(text) or [title]
    prs = Presentation()
    prs.slide_width = KCMC_SLIDE_WIDTH
    prs.slide_height = KCMC_SLIDE_HEIGHT
    prs.core_properties.title = title
    prs.core_properties.subject = f"KCMC {service_style} {item_type} draft"
    layout = prs.slide_layouts[6]
    for block in blocks:
        slide = prs.slides.add_slide(layout)
        background = slide.background.fill
        background.solid()
        background.fore_color.rgb = RGBColor(0, 0, 0)
        box = slide.shapes.add_textbox(Inches(0.65), Inches(0.55), Inches(12.03), Inches(6.35))
        tf = box.text_frame
        tf.clear()
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = block
        p.font.name = KCMC_FONT
        p.font.size = Pt(KCMC_FONT_SIZE_PT)
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    out.parent.chmod(0o700)
    prs.save(out)
    _private_file(out)
    return str(out)


def build_editable_song_deck(
    title: str,
    lyrics: str,
    output_path: str,
    service_style: str = "Front Porch",
) -> str:
    """Create an editable 16:9 lyric deck using verified KCMC black/white typography."""
    return _build_editable_blocks(title, lyrics, output_path, service_style, "song")


def inspect_deck_security(prs: Presentation) -> list[str]:
    """Reject active, embedded, or externally linked package content before reuse."""
    findings: set[str] = set()
    for part in prs.part.package.iter_parts():
        content_type = str(getattr(part, "content_type", "")).lower()
        if any(marker in content_type for marker in UNSAFE_CONTENT_MARKERS):
            findings.add("unsafe_embedded_content")
        for relationship in part.rels.values():
            reltype = str(relationship.reltype).lower()
            if relationship.is_external:
                findings.add("unsafe_external_relationship")
            if any(marker in reltype for marker in UNSAFE_RELATIONSHIP_MARKERS):
                findings.add("unsafe_embedded_relationship")
    return sorted(findings)


def quality_check_deck(
    pptx_path: str,
    expected_font: str | None = KCMC_FONT,
    expected_font_size_pt: float | None = KCMC_FONT_SIZE_PT,
    start_slide: int | None = None,
    end_slide: int | None = None,
) -> dict:
    """Check readability, editability, geometry, typography, and likely overflow."""
    path = Path(pptx_path)
    if not path.is_file():
        return {"ok": False, "errors": ["file_missing"], "warnings": []}
    try:
        prs = Presentation(path)
    except Exception:
        return {"ok": False, "errors": ["invalid_powerpoint"], "warnings": []}

    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(inspect_deck_security(prs))
    selected_slides = list(prs.slides)
    if start_slide is not None or end_slide is not None:
        if (
            isinstance(start_slide, bool)
            or isinstance(end_slide, bool)
            or not isinstance(start_slide, int)
            or not isinstance(end_slide, int)
            or start_slide < 1
            or end_slide < start_slide
            or end_slide > len(prs.slides)
        ):
            errors.append("invalid_slide_range")
            selected_slides = []
        else:
            selected_slides = list(prs.slides)[start_slide - 1 : end_slide]
    if not selected_slides:
        errors.append("no_slides")
    ratio = float(prs.slide_width) / float(prs.slide_height)
    if abs(ratio - (16 / 9)) > 0.01:
        errors.append("not_widescreen_16_9")

    editable_text = 0
    off_style_runs = 0
    off_size_runs = 0
    likely_overflow = 0
    for slide in selected_slides:
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False) or not shape.text.strip():
                continue
            editable_text += 1
            lines = shape.text.splitlines()
            if len(lines) > 5 or any(len(line) > 70 for line in lines):
                likely_overflow += 1
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if not run.text.strip():
                        continue
                    if expected_font and run.font.name and run.font.name != expected_font:
                        off_style_runs += 1
                    if expected_font_size_pt and run.font.size and abs(run.font.size.pt - expected_font_size_pt) > 0.5:
                        off_size_runs += 1
    if editable_text == 0:
        errors.append("no_editable_text")
    if off_style_runs:
        errors.append("off_style_font")
    if off_size_runs:
        warnings.append("off_style_font_size")
    if likely_overflow:
        errors.append("likely_text_overflow")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "slides": len(selected_slides),
        "source_slides": len(prs.slides),
        "editable_text_shapes": editable_text,
        "off_style_runs": off_style_runs,
        "off_size_runs": off_size_runs,
        "likely_overflow_shapes": likely_overflow,
        "slide_size_emu": {"width": int(prs.slide_width), "height": int(prs.slide_height)},
    }


def _replace_relationship_ids(element, relationship_ids: dict[str, str]) -> None:
    for node in element.iter():
        for attribute, value in list(node.attrib.items()):
            if value in relationship_ids:
                node.set(attribute, relationship_ids[value])


def _part_namespace(source_path: str) -> str:
    return sha256_file(source_path)[:16]


def _clone_related_part(
    source_part: Part,
    destination,
    namespace: str,
    cache: dict[int, Part],
) -> Part:
    """Clone a relationship part tree into the destination package.

    PowerPoint decks commonly reuse names such as ``image1.png``. A namespaced
    part name prevents one imported deck from silently replacing another.
    Relationship IDs inside XML parts are preserved because their XML refers to
    those exact IDs.
    """
    cache_key = id(source_part)
    if cache_key in cache:
        return cache[cache_key]

    relative_name = source_part.partname.membername.lstrip("/")
    partname = PackURI(f"/ppt/kcmc-imports/{namespace}/{relative_name}")
    existing = next(
        (part for part in destination.part.package.iter_parts() if part.partname == partname),
        None,
    )
    if existing is not None:
        if existing.content_type != source_part.content_type or existing.blob != source_part.blob:
            raise ValueError(f"Imported PowerPoint part collision: {partname}")
        cache[cache_key] = existing
        return existing

    cloned = Part(partname, source_part.content_type, destination.part.package, source_part.blob)
    cache[cache_key] = cloned
    for relationship in source_part.rels.values():
        if relationship.is_external:
            target = relationship.target_ref
            target_mode = RTM.EXTERNAL
        else:
            target = _clone_related_part(
                relationship.target_part,
                destination,
                namespace,
                cache,
            )
            target_mode = RTM.INTERNAL
        cloned.rels._rels[relationship.rId] = _Relationship(
            cloned.partname.baseURI,
            relationship.rId,
            relationship.reltype,
            target_mode,
            target,
        )
    return cloned


def _copy_slide(
    source_slide,
    destination: Presentation,
    namespace: str,
    cache: dict[int, Part],
) -> None:
    target = destination.slides.add_slide(destination.slide_layouts[6])
    relationship_ids: dict[str, str] = {}
    for relationship in source_slide.part.rels.values():
        if relationship.reltype in {SLIDE_LAYOUT_REL, NOTES_SLIDE_REL}:
            continue
        if relationship.is_external:
            new_id = target.part.rels.get_or_add_ext_rel(relationship.reltype, relationship.target_ref)
        else:
            cloned_part = _clone_related_part(
                relationship.target_part,
                destination,
                namespace,
                cache,
            )
            new_id = target.part.rels.get_or_add(relationship.reltype, cloned_part)
        relationship_ids[relationship.rId] = new_id

    copied_slide = copy.deepcopy(source_slide._element)
    _replace_relationship_ids(copied_slide, relationship_ids)
    target.part._element = copied_slide
    target._element = copied_slide


def append_slides_from_deck(
    destination: Presentation,
    source_path: str,
    start_slide: int | None = None,
    end_slide: int | None = None,
) -> dict:
    """Append an approved slide range while keeping slide objects editable."""
    source = Presentation(source_path)
    security_findings = inspect_deck_security(source)
    if security_findings:
        return {
            "ok": False,
            "error": "unsafe_powerpoint_relationships",
            "security_findings": security_findings,
            "slides_added": 0,
        }
    first = start_slide or 1
    last = end_slide or len(source.slides)
    if first < 1 or last < first or last > len(source.slides):
        return {"ok": False, "error": "invalid_slide_range", "slides_added": 0}
    if abs((float(source.slide_width) / float(source.slide_height)) - (16 / 9)) > 0.01:
        return {"ok": False, "error": "source_not_widescreen_16_9", "slides_added": 0}
    namespace = _part_namespace(source_path)
    cache: dict[int, Part] = {}
    for number in range(first, last + 1):
        _copy_slide(source.slides[number - 1], destination, namespace, cache)
    return {
        "ok": True,
        "slides_added": last - first + 1,
        "start_slide": first,
        "end_slide": last,
    }


def write_approval_manifest(
    service_name: str,
    items: list[dict],
    output_path: str,
    final_deck: str | None = None,
    final_deck_sha256: str | None = None,
    final_qa: dict | None = None,
) -> str:
    """Create the human approval gate. Nothing is published automatically."""
    payload = {
        "schema_version": 3,
        "service": service_name,
        "status": "AWAITING_PASTOR_APPROVAL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "final_deck": final_deck,
        "final_deck_sha256": final_deck_sha256,
        "final_qa": final_qa,
        "approval": {"decision": None, "approved_by": None, "decided_at": None, "notes": None},
        "autopublish": False,
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _private_file(out)
    return str(out)


def write_approval_ui(
    service_name: str,
    items: list[dict],
    output_path: str,
    final_deck: str | None = None,
    final_deck_sha256: str | None = None,
    ready_for_approval: bool = False,
) -> str:
    """Write an offline approval page that downloads, but never submits, a human decision."""
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('item_type') or 'song'))}</td>"
            f"<td>{html.escape(str(item.get('title') or ''))}</td>"
            f"<td>{html.escape(str(item.get('status') or ''))}</td>"
            f"<td>{html.escape(str(item.get('slides_added') or 0))}</td>"
            "</tr>"
        )
    service_json = json.dumps(service_name).replace("</", "<\\/")
    deck_json = json.dumps(final_deck).replace("</", "<\\/")
    hash_json = json.dumps(final_deck_sha256).replace("</", "<\\/")
    deck_label = html.escape(final_deck or "No completed deck")
    hash_label = html.escape(final_deck_sha256 or "Unavailable")
    approve_button = (
        '<button class="approve" type="button" onclick="saveDecision(\'APPROVAL_RECOMMENDED\')">'
        "Record approval recommendation</button>"
        if ready_for_approval
        else '<p class="notice">Approval recommendation is unavailable because this build has blockers.</p>'
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>KCMC service approval</title><style>
body{{font:18px/1.45 Arial,sans-serif;background:#101820;color:#fff;margin:0}}main{{max-width:900px;margin:auto;padding:32px}}
table{{width:100%;border-collapse:collapse;background:#fff;color:#111}}th,td{{padding:12px;border:1px solid #bbb;text-align:left}}
label{{display:block;margin:18px 0 6px}}input,textarea{{width:100%;box-sizing:border-box;padding:11px;font:inherit}}
button{{margin:18px 10px 0 0;padding:12px 18px;font:700 16px Arial;cursor:pointer}}.approve{{background:#d7b25b;border:0}}.changes{{background:#fff;border:0}}
.notice{{padding:14px;border:1px solid #d7b25b;background:#1b2b37}}
</style></head><body><main><h1>{html.escape(service_name)}</h1>
<p class="notice">Review the exact PowerPoint first. This page cannot publish or send anything. It only downloads your decision as a JSON file.</p>
<p><strong>Deck:</strong> {deck_label}<br><strong>SHA-256:</strong> <code>{hash_label}</code></p>
<table><thead><tr><th>Type</th><th>Item</th><th>Status</th><th>Slides</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<label for="reviewer">Reviewer name <small>(identity is not verified by this offline page)</small></label><input id="reviewer" autocomplete="name">
<label for="notes">Notes</label><textarea id="notes" rows="5"></textarea>
{approve_button}
<button class="changes" type="button" onclick="saveDecision('CHANGES_REQUESTED')">Request changes</button>
<script>
const service={service_json};const finalDeck={deck_json};const finalDeckSha256={hash_json};
function saveDecision(decision){{
 const reviewer=document.getElementById('reviewer').value.trim();
 if(!reviewer){{alert('Enter the reviewer name.');return;}}
 const payload={{service,final_deck:finalDeck,final_deck_sha256:finalDeckSha256,decision,reviewer_name:reviewer,identity_verified:false,authoritative:false,decided_at:new Date().toISOString(),notes:document.getElementById('notes').value.trim(),autopublish:false}};
 const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{{type:'application/json'}}));
 link.download='approval-decision.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
}}
</script></main></body></html>"""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    _private_file(out)
    return str(out)
