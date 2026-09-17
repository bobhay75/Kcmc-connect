from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
from pathlib import Path

from orchestrator import prepare_service


IMPORT_KEY_ENV = "KCMC_SERMON_IMPORT_KEY"
IMPORT_SIGNATURE_PREFIX = "KCMC-SERMON-IMPORT-V1"
KCMC_JOB_ID_PATTERN = re.compile(r"^sdj_[a-f0-9]{32}$")


def _write_kcmc_import_envelope(
    result: dict,
    job_id: str,
    request_sha256: str,
    signing_key: str,
) -> str:
    """Write a server-verifiable pointer to an approval-ready build."""
    if not result.get("ready_for_approval"):
        raise ValueError("KCMC import envelopes may only be written for approval-ready builds.")
    if len(signing_key) < 32:
        raise ValueError(f"{IMPORT_KEY_ENV} must contain at least 32 characters")
    if not KCMC_JOB_ID_PATTERN.fullmatch(job_id):
        raise ValueError("KCMC job ID must match sdj_ followed by 32 lowercase hexadecimal characters.")
    deck_path = Path(str(result.get("final_deck") or ""))
    manifest_path = Path(str(result.get("approval_manifest") or ""))
    if not deck_path.is_file() or not manifest_path.is_file():
        raise ValueError("Approval-ready build is missing hash-bound artifacts.")
    deck_sha256 = hashlib.sha256(deck_path.read_bytes()).hexdigest()
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Approval-ready build has an invalid manifest.") from exc
    approval = manifest.get("approval")
    items = manifest.get("items")
    complete_statuses = {"REUSED_EXISTING", "CREATED_DRAFT"}
    items_are_ready = (
        isinstance(items, list)
        and bool(items)
        and all(
            isinstance(item, dict)
            and item.get("status") in complete_statuses
            and isinstance(item.get("slides_added"), int)
            and not isinstance(item.get("slides_added"), bool)
            and item["slides_added"] > 0
            and isinstance(item.get("qa"), dict)
            and item["qa"].get("ok") is True
            and item["qa"].get("errors") == []
            for item in items
        )
    )
    approval_is_empty = (
        isinstance(approval, dict)
        and all(approval.get(field) is None for field in ("decision", "approved_by", "decided_at", "notes"))
        and approval.get("authoritative") in (None, False)
    )
    if (
        manifest.get("schema_version") != 3
        or manifest.get("ready_for_approval") is not True
        or manifest.get("final_deck_sha256") != deck_sha256
        or result.get("final_deck_sha256") != deck_sha256
        or manifest.get("final_deck") != deck_path.name
        or manifest.get("autopublish") is not False
        or not isinstance(manifest.get("final_qa"), dict)
        or manifest["final_qa"].get("ok") is not True
        or manifest["final_qa"].get("errors") != []
        or not isinstance(manifest["final_qa"].get("slides"), int)
        or isinstance(manifest["final_qa"].get("slides"), bool)
        or manifest["final_qa"]["slides"] < 1
        or not items_are_ready
        or not approval_is_empty
    ):
        raise ValueError("Approval manifest and final deck are not hash-bound and ready.")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    message = (
        f"{IMPORT_SIGNATURE_PREFIX}\n"
        f"{job_id}\n"
        f"{request_sha256}\n"
        f"{deck_sha256}\n"
        f"{manifest_sha256}\n"
    )
    signature = hmac.new(
        signing_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    envelope = {
        "schema_version": 1,
        "job_id": job_id,
        "request_sha256": request_sha256,
        "deck_sha256": deck_sha256,
        "manifest_sha256": manifest_sha256,
        "signature_hmac_sha256": signature,
    }
    output_path = Path(result["output_directory"]) / "kcmc-import.json"
    temporary_path = output_path.with_name(".kcmc-import.json.tmp")
    temporary_path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    temporary_path.chmod(0o600)
    temporary_path.replace(output_path)
    return str(output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an approval-ready KCMC service deck.")
    parser.add_argument("request", type=Path, help="JSON file containing service_name, service_style, and ordered items")
    parser.add_argument("--catalog", type=Path, required=True, help="Metadata-only KCMC song catalog")
    parser.add_argument("--archive", type=Path, required=True, help="Approved private PowerPoint archive")
    parser.add_argument("--out", type=Path, required=True, help="Output directory outside the archive")
    args = parser.parse_args(argv)

    request_bytes = args.request.read_bytes()
    request = json.loads(request_bytes.decode("utf-8"))
    if not isinstance(request, dict):
        raise SystemExit("request must be a JSON object")
    service_name = str(request.get("service_name") or "").strip()
    items = request.get("items")
    if items is None and isinstance(request.get("songs"), list):
        items = [{"type": "song", **song} if isinstance(song, dict) else song for song in request["songs"]]
    if not service_name:
        raise SystemExit("request.service_name is required")
    if not isinstance(items, list) or not items:
        raise SystemExit("request.items must be a non-empty ordered array")

    job_id: str | None = None
    signing_key: str | None = None
    if "kcmc_job_id" in request:
        raw_job_id = request["kcmc_job_id"]
        if not isinstance(raw_job_id, str) or not KCMC_JOB_ID_PATTERN.fullmatch(raw_job_id):
            raise SystemExit(
                "request.kcmc_job_id must match sdj_ followed by 32 lowercase hexadecimal characters"
            )
        job_id = raw_job_id
        signing_key = os.environ.get(IMPORT_KEY_ENV)
        if signing_key is None or len(signing_key) < 32:
            raise SystemExit(f"{IMPORT_KEY_ENV} must contain at least 32 characters")

    result = prepare_service(
        service_name=service_name,
        service_items=items,
        catalog_path=str(args.catalog),
        archive_root=str(args.archive),
        output_root=str(args.out),
        service_style=str(request.get("service_style") or "Front Porch"),
    )
    output = {
        "status": result["status"],
        "run_id": result["run_id"],
        "output_directory": result["output_directory"],
        "ready_for_approval": result["ready_for_approval"],
        "final_deck": result["final_deck"],
        "approval_manifest": result["approval_manifest"],
        "approval_ui": result["approval_ui"],
        "summary": result["summary"],
    }
    if job_id is not None and result["ready_for_approval"]:
        output["kcmc_import"] = _write_kcmc_import_envelope(
            result,
            job_id,
            hashlib.sha256(request_bytes).hexdigest(),
            signing_key or "",
        )
    print(json.dumps(output, indent=2))
    return 0 if result["ready_for_approval"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
