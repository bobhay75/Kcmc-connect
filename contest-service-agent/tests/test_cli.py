import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import cli  # noqa: E402

SIGNED_JOB_ID = "sdj_" + "a" * 32
UNSIGNED_JOB_ID = "sdj_" + "b" * 32
BLOCKED_JOB_ID = "sdj_" + "c" * 32


class CliTests(unittest.TestCase):
    def _inputs(self, root: Path, request_bytes: bytes) -> tuple[list[str], Path]:
        archive = root / "archive"
        archive.mkdir()
        catalog = root / "catalog.json"
        catalog.write_text(json.dumps({
            "confirmation": {"status": "confirmed", "method": "sha256-and-human-reviewed-ranges"},
            "segments": [],
        }), encoding="utf-8")
        request = root / "request.json"
        request.write_bytes(request_bytes)
        output = root / "output"
        return [
            str(request),
            "--catalog", str(catalog),
            "--archive", str(archive),
            "--out", str(output),
        ], output

    def test_ready_kcmc_job_writes_valid_signed_import_envelope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request_bytes = json.dumps({
                "schema_version": 1,
                "service_name": "Signed Service",
                "service_date": "2026-09-20",
                "service_style": "Front Porch",
                "kcmc_job_id": SIGNED_JOB_ID,
                "items": [{"type": "song", "title": "Authorized", "lyrics": "Approved line"}],
                "autopublish": False,
            }, separators=(",", ":")).encode("utf-8")
            argv, _ = self._inputs(root, request_bytes)
            signing_key = "kcmc-test-signing-key-32-characters-minimum"
            stdout = StringIO()
            with patch.dict(os.environ, {cli.IMPORT_KEY_ENV: signing_key}, clear=False):
                with redirect_stdout(stdout):
                    self.assertEqual(cli.main(argv), 0)

            output = json.loads(stdout.getvalue())
            envelope_path = Path(output["kcmc_import"])
            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            manifest_path = Path(output["approval_manifest"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["ready_for_approval"])
            self.assertEqual(set(envelope), {
                "schema_version",
                "job_id",
                "request_sha256",
                "deck_sha256",
                "manifest_sha256",
                "signature_hmac_sha256",
            })
            self.assertEqual(envelope["schema_version"], 1)
            self.assertEqual(envelope["job_id"], SIGNED_JOB_ID)
            self.assertEqual(envelope["request_sha256"], hashlib.sha256(request_bytes).hexdigest())
            self.assertEqual(envelope["deck_sha256"], manifest["final_deck_sha256"])
            self.assertEqual(envelope["deck_sha256"], hashlib.sha256(Path(output["final_deck"]).read_bytes()).hexdigest())
            self.assertEqual(envelope["manifest_sha256"], hashlib.sha256(manifest_path.read_bytes()).hexdigest())
            message = (
                "KCMC-SERMON-IMPORT-V1\n"
                f"{SIGNED_JOB_ID}\n{envelope['request_sha256']}\n{envelope['deck_sha256']}\n"
                f"{envelope['manifest_sha256']}\n"
            )
            expected_signature = hmac.new(
                signing_key.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            self.assertTrue(hmac.compare_digest(envelope["signature_hmac_sha256"], expected_signature))
            self.assertEqual(envelope_path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(envelope_path.with_name(".kcmc-import.json.tmp").exists())

            original_manifest = manifest_path.read_bytes()
            result = {
                "ready_for_approval": True,
                "final_deck": output["final_deck"],
                "final_deck_sha256": envelope["deck_sha256"],
                "approval_manifest": str(manifest_path),
                "output_directory": output["output_directory"],
            }
            for field in ("autopublish", "approval", "final_deck", "item_qa", "final_qa"):
                with self.subTest(tampered_field=field):
                    tampered = json.loads(original_manifest.decode("utf-8"))
                    if field == "autopublish":
                        tampered[field] = True
                    elif field == "approval":
                        tampered[field]["decision"] = "APPROVED"
                    elif field == "item_qa":
                        tampered["items"][0]["qa"]["errors"] = ["hidden_failure"]
                    elif field == "final_qa":
                        tampered["final_qa"]["slides"] = 0
                    else:
                        tampered[field] = "../other.pptx"
                    manifest_path.write_text(json.dumps(tampered), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "not hash-bound and ready"):
                        cli._write_kcmc_import_envelope(
                            result,
                            SIGNED_JOB_ID,
                            envelope["request_sha256"],
                            signing_key,
                        )
            manifest_path.write_bytes(original_manifest)

    def test_kcmc_job_missing_or_short_signing_key_fails_before_build(self):
        request_bytes = json.dumps({
            "service_name": "Unsigned Service",
            "kcmc_job_id": UNSIGNED_JOB_ID,
            "items": [{"type": "song", "title": "Authorized", "lyrics": "Approved line"}],
        }).encode("utf-8")
        for signing_key in (None, "x" * 31):
            with self.subTest(signing_key=signing_key):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    argv, output = self._inputs(root, request_bytes)
                    environment = {} if signing_key is None else {cli.IMPORT_KEY_ENV: signing_key}
                    with patch.dict(os.environ, environment, clear=True):
                        with self.assertRaisesRegex(SystemExit, "at least 32 characters"):
                            cli.main(argv)
                    self.assertFalse(output.exists())

    def test_blocked_kcmc_job_does_not_write_import_envelope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request_bytes = json.dumps({
                "service_name": "Blocked Service",
                "kcmc_job_id": BLOCKED_JOB_ID,
                "items": [{"type": "song", "title": "Missing words"}],
            }).encode("utf-8")
            argv, _ = self._inputs(root, request_bytes)
            stdout = StringIO()
            with patch.dict(os.environ, {cli.IMPORT_KEY_ENV: "x" * 32}, clear=False):
                with redirect_stdout(stdout):
                    self.assertEqual(cli.main(argv), 2)
            output = json.loads(stdout.getvalue())
            self.assertNotIn("kcmc_import", output)
            self.assertFalse((Path(output["output_directory"]) / "kcmc-import.json").exists())
            manifest = json.loads(Path(output["approval_manifest"]).read_text(encoding="utf-8"))
            self.assertFalse(manifest["ready_for_approval"])

    def test_request_without_job_id_keeps_local_cli_keyless(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request_bytes = json.dumps({
                "service_name": "Local Service",
                "items": [{"type": "song", "title": "Authorized", "lyrics": "Approved line"}],
            }).encode("utf-8")
            argv, _ = self._inputs(root, request_bytes)
            stdout = StringIO()
            with patch.dict(os.environ, {}, clear=True):
                with redirect_stdout(stdout):
                    self.assertEqual(cli.main(argv), 0)
            output = json.loads(stdout.getvalue())
            self.assertNotIn("kcmc_import", output)
            self.assertFalse((Path(output["output_directory"]) / "kcmc-import.json").exists())

    def test_non_php_job_id_format_fails_before_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request_bytes = json.dumps({
                "service_name": "Invalid Job ID",
                "kcmc_job_id": "job-123",
                "items": [{"type": "song", "title": "Authorized", "lyrics": "Approved line"}],
            }).encode("utf-8")
            argv, output = self._inputs(root, request_bytes)
            with patch.dict(os.environ, {cli.IMPORT_KEY_ENV: "x" * 32}, clear=False):
                with self.assertRaisesRegex(SystemExit, "32 lowercase hexadecimal"):
                    cli.main(argv)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
