from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

try:
    from strands import Agent, tool
except Exception:  # permits local archive/PPT tests without AWS credentials
    Agent = None
    def tool(fn):
        return fn


@dataclass
class SongMatch:
    title: str
    status: str
    source: str | None = None


def normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


@tool
def find_song_in_archive(title: str, archive_root: str) -> dict:
    """Find an existing editable PowerPoint song deck by normalized title."""
    target = normalize(title)
    root = Path(archive_root)
    if not root.exists():
        return asdict(SongMatch(title, "missing"))
    for path in root.rglob("*.pptx"):
        if target in normalize(path.stem) or normalize(path.stem) in target:
            return asdict(SongMatch(title, "found", str(path)))
    return asdict(SongMatch(title, "missing"))


@tool
def build_editable_song_deck(title: str, lyrics: str, output_path: str, service_style: str = "Contemporary") -> str:
    """Create a simple fully editable PPTX song deck from lyric blocks."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    layout = prs.slide_layouts[6]
    blocks = [b.strip() for b in lyrics.split("\n\n") if b.strip()]
    for block in blocks or [title]:
        slide = prs.slides.add_slide(layout)
        box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(5.9))
        tf = box.text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.text = block
        p.font.size = Pt(30 if service_style.lower() == "traditional" else 34)
        p.font.bold = True
        p.alignment = 1
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    return str(out)


@tool
def quality_check_deck(pptx_path: str) -> dict:
    """Check that the deck opens, has slides, and contains editable text shapes."""
    path = Path(pptx_path)
    if not path.exists():
        return {"ok": False, "errors": ["file_missing"]}
    prs = Presentation(path)
    errors: list[str] = []
    if len(prs.slides) == 0:
        errors.append("no_slides")
    editable_text = 0
    for slide in prs.slides:
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text.strip():
                editable_text += 1
    if editable_text == 0:
        errors.append("no_editable_text")
    return {"ok": not errors, "errors": errors, "slides": len(prs.slides), "editable_text_shapes": editable_text}


@tool
def write_approval_manifest(service_name: str, songs: list[dict], output_path: str) -> str:
    """Create the human-approval gate manifest. Nothing is published automatically."""
    payload = {
        "service": service_name,
        "status": "AWAITING_PASTOR_APPROVAL",
        "songs": songs,
        "autopublish": False,
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(out)


SYSTEM_PROMPT = """
You are KCMC Service Agent, a production assistant for worship-service preparation.
Your job is to reduce repetitive production work while preserving human authority.
Always search the existing archive before creating anything new. Prefer editable PPTX assets.
When an asset is missing, create a draft using the approved service style.
Run quality checks before handoff. Never publish, send, or mark a service final without explicit pastor approval.
Return a concise production report including found assets, created assets, QA failures, and items needing judgment.
""".strip()


def make_agent():
    if Agent is None:
        raise RuntimeError("Install strands-agents before running the autonomous agent")
    return Agent(
        system_prompt=SYSTEM_PROMPT,
        tools=[find_song_in_archive, build_editable_song_deck, quality_check_deck, write_approval_manifest],
        callback_handler=None,
    )


def run_service_request(request: str):
    agent = make_agent()
    return agent(request)
