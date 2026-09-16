from pathlib import Path

from orchestrator import prepare_service


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo-output"

# Synthetic text keeps the public repository copyright-safe.
result = prepare_service(
    service_name="Sunday Front Porch Demo",
    songs=[
        {
            "title": "Sample Worship Song",
            "lyrics": "Sample worship line one\nSample worship line two\n\nSample chorus line one\nSample chorus line two",
        }
    ],
    catalog_path=str(ROOT / "data" / "kcmc_song_catalog.sample.json"),
    archive_root=str(ROOT / "data" / "empty-archive"),
    output_root=str(OUT),
    service_style="Front Porch",
)
print(
    {
        "status": result["status"],
        "ready_for_approval": result["ready_for_approval"],
        "final_deck": result["final_deck"],
        "approval_ui": result["approval_ui"],
        "autopublish": result["autopublish"],
    }
)
