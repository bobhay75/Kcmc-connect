#!/usr/bin/env python3
"""Synthetic full-app acceptance for the signed-in KCMC workflows.

Runs the real PHP application against isolated temporary private storage. It never
uses production accounts, production private data, email delivery, or real push
providers. The goal is to prove the member/admin navigation and core interactive
Time Clock path before live owner-controlled acceptance.
"""
from __future__ import annotations

import json
import os
import pathlib
import signal
import subprocess
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1] / "KCMC-Connect-Phase6-Recreated"
BASE = "http://127.0.0.1:8766/KCMC-Connect-Phase6-Recreated"


def die(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def assert_title(page, expected: str, label: str) -> None:
    title = page.title()
    if expected not in title:
        die(f"{label}: expected title containing {expected!r}, got {title!r}")
    print(f"PASS: {label}")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        die(f"Playwright is required: {exc}")

    with tempfile.TemporaryDirectory(prefix="kcmc-signed-in-") as tmp:
        private = pathlib.Path(tmp) / "private"
        private.mkdir(mode=0o750)
        password = "Synthetic-Test-Password-2031!"
        hash_proc = subprocess.run(
            ["php", "-r", "echo password_hash($argv[1], PASSWORD_DEFAULT);", password],
            check=True,
            capture_output=True,
            text=True,
        )
        users = {
            "version": 1,
            "users": [
                {
                    "id": "test_admin",
                    "email": "admin@example.invalid",
                    "email_normalized": "admin@example.invalid",
                    "display_name": "Synthetic KCMC Admin",
                    "role": "pastor_admin",
                    "active": True,
                    "password_hash": hash_proc.stdout.strip(),
                    "created_at": "2031-01-01T00:00:00Z",
                }
            ],
        }
        (private / "users.json").write_text(json.dumps(users), encoding="utf-8")
        (private / "login-attempts.json").write_text(json.dumps({"attempts": {}}), encoding="utf-8")

        env = os.environ.copy()
        env["KCMC_PRIVATE_DATA_DIR"] = str(private)
        env["KCMC_SETUP_KEY"] = ""
        server = subprocess.Popen(
            ["php", "-S", "127.0.0.1:8766", "-t", str(ROOT.parent)],
            cwd=str(ROOT.parent),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            for _ in range(40):
                try:
                    with urllib.request.urlopen(BASE + "/", timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(0.25)
            else:
                output = server.stdout.read(4000) if server.stdout else ""
                die(f"PHP server did not start: {output}")

            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(viewport={"width": 390, "height": 844})
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))

                page.goto(BASE + "/", wait_until="domcontentloaded")
                if "KCMC CONNECT" not in page.locator("body").inner_text():
                    die("public home did not render the KCMC Connect shell")
                print("PASS: public home renders before sign-in")

                page.goto(BASE + "/member/login.php", wait_until="domcontentloaded")
                page.locator('input[name="email"]').fill("admin@example.invalid")
                page.locator('input[name="password"]').fill(password)
                page.locator('button[type="submit"]').click()
                page.wait_for_url("**/member/**", timeout=5000)

                page.goto(BASE + "/member/", wait_until="domcontentloaded")
                assert_title(page, "Member Prayer", "signed-in member area loads")
                if "VERIFIED MEMBER AREA" not in page.locator("body").inner_text():
                    die("member area did not show the verified-member shell")

                page.goto(BASE + "/admin/", wait_until="domcontentloaded")
                assert_title(page, "KCMC Publishing Desk", "Publishing Desk loads for pastor admin")
                if page.locator('button:has-text("Publish changes")').count() != 1:
                    die("Publishing Desk did not expose the guarded publish control")

                page.goto(BASE + "/member/timeclock.php", wait_until="domcontentloaded")
                assert_title(page, "Time Clock", "Time Clock loads while signed in")
                page.locator('button:has-text("Clock In")').click()
                page.wait_for_load_state("domcontentloaded")
                if "Clocked in" not in page.locator("body").inner_text():
                    die("Time Clock did not enter the clocked-in state")
                page.locator('select[name="category"]').select_option(label="KCMC Connect / IT")
                page.locator('textarea[name="description"]').fill("Synthetic signed-in acceptance check")
                page.locator('button:has-text("Clock Out")').click()
                page.wait_for_load_state("domcontentloaded")
                body = page.locator("body").inner_text()
                if "Synthetic signed-in acceptance check" not in body or "You are clocked out" not in body:
                    die("Time Clock did not save and render the completed synthetic shift")
                print("PASS: Time Clock clock-in and clock-out interaction works")

                page.goto(BASE + "/admin/rsvps.php", wait_until="domcontentloaded")
                assert_title(page, "Event RSVPs", "authenticated RSVP inbox loads")

                page.goto(BASE + "/admin/connections.php", wait_until="domcontentloaded")
                assert_title(page, "Connection Inbox", "authenticated follow-up inbox loads")

                page.goto(BASE + "/admin/operations.php", wait_until="domcontentloaded")
                assert_title(page, "Operations", "Operations hub loads")

                page.goto(BASE + "/admin/health.php", wait_until="domcontentloaded")
                assert_title(page, "Release Health", "Release Health loads")
                if "KCMC production readiness" not in page.locator("body").inner_text():
                    die("Release Health did not render the production-readiness panel")

                page.goto(BASE + "/admin/push.php", wait_until="domcontentloaded")
                assert_title(page, "Push Updates", "Push Updates loads")
                if "Test my subscribed device" not in page.locator("body").inner_text():
                    die("signed-in-device push self-test control is missing")
                print("PASS: signed-in-device push self-test control is present")

                if errors:
                    die("browser page errors: " + "; ".join(errors))

                browser.close()
                print("Signed-in workflow browser acceptance passed.")
        finally:
            server.send_signal(signal.SIGTERM)
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
