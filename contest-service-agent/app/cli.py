from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator import prepare_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an approval-ready KCMC service deck.")
    parser.add_argument("request", type=Path, help="JSON file containing service_name, service_style, and ordered items")
    parser.add_argument("--catalog", type=Path, required=True, help="Metadata-only KCMC song catalog")
    parser.add_argument("--archive", type=Path, required=True, help="Approved private PowerPoint archive")
    parser.add_argument("--out", type=Path, required=True, help="Output directory outside the archive")
    args = parser.parse_args()

    request = json.loads(args.request.read_text(encoding="utf-8"))
    service_name = str(request.get("service_name") or "").strip()
    items = request.get("items")
    if items is None and isinstance(request.get("songs"), list):
        items = [{"type": "song", **song} if isinstance(song, dict) else song for song in request["songs"]]
    if not service_name:
        raise SystemExit("request.service_name is required")
    if not isinstance(items, list) or not items:
        raise SystemExit("request.items must be a non-empty ordered array")

    result = prepare_service(
        service_name=service_name,
        service_items=items,
        catalog_path=str(args.catalog),
        archive_root=str(args.archive),
        output_root=str(args.out),
        service_style=str(request.get("service_style") or "Front Porch"),
    )
    print(json.dumps({
        "status": result["status"],
        "run_id": result["run_id"],
        "output_directory": result["output_directory"],
        "ready_for_approval": result["ready_for_approval"],
        "final_deck": result["final_deck"],
        "approval_manifest": result["approval_manifest"],
        "approval_ui": result["approval_ui"],
        "summary": result["summary"],
    }, indent=2))
    return 0 if result["ready_for_approval"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
