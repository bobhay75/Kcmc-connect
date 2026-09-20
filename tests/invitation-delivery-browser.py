#!/usr/bin/env python3
"""Full-app invitation delivery acceptance test.

Runs the real KCMC PHP application with isolated synthetic private storage.
No production data, mail transport, or real invitation token is used.
"""
from __future__ import annotations

import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1] / "KCMC-Connect-Phase6-Recreated"
BASE = "http://127.0.0.1:8765/KCMC-Connect-Phase6-Recreated"

def die(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")

def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        die(f"Playwright is required: {exc}")

    with tempfile.TemporaryDirectory(prefix="kcmc-invitation-") as tmp:
        private = pathlib.Path(tmp) / "private"
        private.mkdir(mode=0o750)
        password = "Synthetic-Test-Password-2031!"
        hash_proc = subprocess.run(
            ["php", "-r", "echo password_hash($argv[1], PASSWORD_DEFAULT);", password],
            check=True, capture_output=True, text=True,
        )
        users = {
            "version": 1,
            "users": [{
                "id": "test_admin",
                "email": "admin@example.invalid",
                "email_normalized": "admin@example.invalid",
                "display_name": "Synthetic KCMC Admin",
                "role": "pastor_admin",
                "active": True,
                "password_hash": hash_proc.stdout.strip(),
                "created_at": "2031-01-01T00:00:00Z",
            }],
        }
        (private / "users.json").write_text(json.dumps(users), encoding="utf-8")
        (private / "invites.json").write_text(json.dumps({"version": 1, "invites": []}), encoding="utf-8")
        (private / "login-attempts.json").write_text(json.dumps({"attempts": {}}), encoding="utf-8")

        env = os.environ.copy()
        env["KCMC_PRIVATE_DATA_DIR"] = str(private)
        env["KCMC_SETUP_KEY"] = ""
        server = subprocess.Popen(
            ["php", "-S", "127.0.0.1:8765", "-t", str(ROOT.parent)],
            cwd=str(ROOT.parent), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            for _ in range(40):
                try:
                    with urllib.request.urlopen(BASE + "/member/login.php", timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(0.25)
            else:
                output = server.stdout.read(4000) if server.stdout else ""
                die(f"PHP server did not start: {output}")

            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    permissions=["clipboard-read", "clipboard-write"],
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))

                page.goto(BASE + "/member/login.php?next=%2FKCMC-Connect-Phase6-Recreated%2Fadmin%2Fusers.php", wait_until="domcontentloaded")
                page.locator('input[name="email"]').fill("admin@example.invalid")
                page.locator('input[name="password"]').fill(password)
                page.locator('button[type="submit"]').click()
                page.wait_for_url("**/admin/users.php", timeout=5000)

                page.locator('input[name="display_name"]').fill("Dana Example")
                page.locator('input[name="email"]').fill("dana@example.invalid")
                page.locator('select[name="role"]').select_option("pastor_admin")
                page.locator('button:has-text("Create invitation")').click()
                page.wait_for_load_state("domcontentloaded")

                card = page.locator("[data-invitation-delivery]")
                if card.count() != 1:
                    die("real admin page did not render exactly one invitation delivery card")
                if "Invitation ready — not emailed" not in card.inner_text():
                    die("delivery card did not state that nothing was emailed")

                checkbox = page.locator("[data-invite-confirm]")
                checkbox.check()
                copy = page.locator('[data-copy-invitation="message"]')
                if not copy.is_enabled():
                    die("recipient confirmation did not enable Copy invitation email")

                page.on("dialog", lambda dialog: dialog.dismiss())
                copy.click()
                status = page.locator("[data-invite-status]").inner_text()
                if "Nothing has been sent" not in status or "dana@example.invalid" not in status:
                    die("copy action did not report the verified recipient and no-send state")

                gmail = page.locator("[data-invite-gmail]")
                href = gmail.get_attribute("href") or ""
                if not href.startswith("https://mail.google.com/"):
                    die("Gmail action did not point to the fixed Gmail origin")
                if "token=" in href or "body=" in href:
                    die("Gmail compose URL leaked the private invitation token/body")

                manual = page.locator("[data-invite-manual]")
                if manual.count() != 1:
                    die("manual delivery fallback is missing")

                page.locator("[data-invite-confirm]").uncheck()
                if copy.is_enabled():
                    die("delivery controls remained enabled after recipient uncheck")

                if errors:
                    die("browser console page errors: " + "; ".join(errors))

                print("PASS: authenticated admin can create a synthetic invitation in the real app")
                print("PASS: recipient-bound delivery card renders in the real app")
                print("PASS: copy action works with browser clipboard permissions")
                print("PASS: Gmail compose origin is fixed and contains no token/body")
                print("PASS: unchecking recipient disables delivery controls")
                print("PASS: manual fallback is present")
                browser.close()
        finally:
            server.send_signal(signal.SIGTERM)
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
