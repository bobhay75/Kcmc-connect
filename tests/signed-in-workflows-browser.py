#!/usr/bin/env python3
"""Synthetic full-app acceptance for the signed-in KCMC workflows.

Runs the real PHP application against isolated temporary private storage. It never
uses production accounts, production private data, email delivery, or real push
providers. The goal is to prove the member/admin navigation and core interactive
Time Clock path before live owner-controlled acceptance.
"""
from __future__ import annotations

import csv
import io
import json
import os
import pathlib
import signal
import shutil
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
        work = pathlib.Path(tmp)
        app = work / ROOT.name
        shutil.copytree(ROOT, app, ignore=shutil.ignore_patterns('config.php', 'private', 'backups'))
        private = work / "private"
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

        # Start with the same submitted state reported by the owner: a prior
        # turn-in must never hide the live punch controls for the current period.
        period = json.loads(subprocess.check_output(
            ["php", "-r", "require $argv[1]; echo json_encode(kcmc_timeclock_period());", str(app / "lib/timeclock.php")],
            text=True,
        ))
        (private / "timeclock.json").write_text(json.dumps({
            "version": 1, "entries": [], "adjustments": [], "correction_requests": [],
            "periods": [{"user_id": "test_admin", "start": period[0], "end": period[1],
                "status": "submitted", "submitted_at": "2026-01-01T00:00:00Z"}],
        }), encoding="utf-8")
        env = os.environ.copy()
        env["KCMC_PRIVATE_DATA_DIR"] = str(private)
        env["KCMC_SETUP_KEY"] = ""
        env["KCMC_OPERATIONS_OWNER_USER_ID"] = "test_admin"
        # A pipe can fill with asset access logs while the browser is active,
        # blocking the single PHP server before the sign-in redirect completes.
        server_log = (pathlib.Path(tmp) / 'php.log').open('w+', encoding='utf-8')
        server = subprocess.Popen(
            ["php", "-S", "127.0.0.1:8766", "-t", str(work)],
            cwd=str(work),
            env=env,
            stdout=server_log,
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
                server_log.seek(0)
                output = server_log.read(4000)
                die(f"PHP server did not start: {output}")

            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(viewport={"width": 390, "height": 844})
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))

                page.goto(BASE + "/", wait_until="domcontentloaded")
                page.locator("#siteMenu summary").click()
                if "KCMC CONNECT" not in page.locator("#siteMenuLinks").inner_text():
                    die("public home did not render the KCMC Connect shell inside the fish menu")
                page.keyboard.press("Escape")
                print("PASS: public home exposes its KCMC navigation through the fish before sign-in")

                page.goto(BASE + "/member/login.php", wait_until="domcontentloaded")
                page.locator('input[name="email"]').fill("admin@example.invalid")
                page.locator('input[name="password"]').fill(password)
                page.locator('button[type="submit"]').click()
                page.wait_for_url("**/member/**", timeout=5000)

                page.goto(BASE + "/member/", wait_until="domcontentloaded")
                assert_title(page, "My Account", "personal account area loads")
                if page.get_by_role("navigation", name="Personal settings").count() != 1:
                    die("account area did not show personal settings")
                if page.locator('a[href*="/admin/"]').count() != 1:
                    die("personal account should expose one Administration entry")
                if page.get_by_role("button", name="Send private request").count():
                    die("the account overview repeated the private prayer form")
                page.get_by_role("link", name="Administration", exact=True).click()
                assert_title(page, "Administration", "Administration opens from the account")
                operations = page.locator('details.admin-group > summary').filter(has_text='Operations')
                operations.click()
                if not page.get_by_role("link", name="Open Employee time cards", exact=True).is_visible():
                    die("owner Administration did not expose employee review")
                operations.click()
                page.locator('details.admin-group > summary').filter(has_text='Work & publishing').click()
                page.get_by_role("link", name="Open Publishing", exact=True).click()

                assert_title(page, "KCMC Publishing Desk", "Publishing Desk loads for pastor admin")
                if page.locator('button:has-text("Publish changes")').count() != 1:
                    die("Publishing Desk did not expose the guarded publish control")

                page.goto(BASE + "/member/timeclock.php", wait_until="domcontentloaded")
                assert_title(page, "Time Clock", "Time Clock loads while signed in")
                page.locator('button:has-text("Clock In")').click()
                page.wait_for_load_state("domcontentloaded")
                if "Clocked in" not in page.locator("body").inner_text():
                    die("Time Clock did not enter the clocked-in state")
                page.get_by_text("Add work details (optional)", exact=True).click()
                page.locator('select[name="category"]').select_option(label="KCMC Connect / IT")
                page.locator('textarea[name="description"]').fill("Synthetic signed-in acceptance check")
                page.locator('button:has-text("Clock Out")').click()
                page.wait_for_load_state("domcontentloaded")
                body = page.locator("body").inner_text()
                if "Synthetic signed-in acceptance check" not in body or "You are clocked out" not in body:
                    die("Time Clock did not save and render the completed synthetic shift")
                if page.get_by_role("button", name="Submit pay period", exact=True).count():
                    die("employee page exposed a manual pay-period approval/turn-in action")
                print("PASS: submitted current period retains Clock In and Clock Out; optional work details save")

                page.get_by_text("Request a correction", exact=True).click()
                page.get_by_label("What needs to be corrected?", exact=True).fill("Synthetic correction reason for administrator review.")
                page.get_by_role("button", name="Send Correction Request", exact=True).click()
                if "Correction request sent" not in page.locator("body").inner_text():
                    die("employee correction request did not reach administrator review")
                if not json.loads((private / "timeclock.json").read_text())["correction_requests"]:
                    die("the correction request was not saved privately")
                screenshots = pathlib.Path(os.environ.get("KCMC_WORKFLOW_SCREENSHOTS", str(ROOT.parent / "test-artifacts/signed-in-workflows")))
                screenshots.mkdir(parents=True, exist_ok=True)
                for width, height in [(390, 844), (1365, 900)]:
                    page.set_viewport_size({"width": width, "height": height})
                    if not page.evaluate("document.documentElement.scrollWidth <= innerWidth"):
                        die("employee time clock overflows viewport " + str(width))
                    page.screenshot(path=str(screenshots / ("timeclock-" + str(width) + ".png")), full_page=True)

                page.goto(BASE + "/admin/home.php", wait_until="domcontentloaded")
                page.locator('details.admin-group > summary').filter(has_text='Operations').click()
                page.get_by_role("link", name="Open Employee time cards", exact=True).click()
                for action in ("Prepare for review", "Approve", "Return"):
                    if page.get_by_role("button", name=action, exact=True).count():
                        die("time-card page exposed the removed " + action + " action")
                # Correct the owner's own recorded punches without preparing or
                # approving the card, preserving reason and before/after history.
                current = json.loads((private / "timeclock.json").read_text())
                shift = current["entries"][0]
                form = page.locator("form.correction-form")
                form.get_by_label("Corrected clock in", exact=True).fill(shift["work_date"] + "T08:00")
                form.get_by_label("Corrected clock out", exact=True).fill(shift["work_date"] + "T10:30")
                form.get_by_label("Unpaid break minutes", exact=True).fill("10")
                form.get_by_label("Administrator correction reason", exact=True).fill("Synthetic owner correction with recorded actual time.")
                form.get_by_role("button", name="Apply correction", exact=True).click()
                stored = json.loads((private / "timeclock.json").read_text())
                if stored["entries"][0]["net_minutes"] != 140 or stored["correction_requests"][0]["status"] != "applied":
                    die("reasoned owner correction did not update actual recorded time")
                own_period = next(row for row in stored["periods"] if row["user_id"] == "test_admin")
                if own_period["status"] != "submitted" or own_period.get("approved_at") or own_period.get("approved_by"):
                    die("manual punching or correction changed historical submission into an approval")
                before_report = (private / "timeclock.json").read_bytes()
                with page.expect_download() as downloaded:
                    page.get_by_role("link", name="Download CSV", exact=True).click()
                download = downloaded.value
                rows = list(csv.DictReader(io.StringIO(pathlib.Path(download.path()).read_text(encoding="utf-8-sig"))))
                if not rows or rows[-1]["Work Date"] != "TOTAL" or rows[-1]["Net Hours"] != "2.33":
                    die("direct recorded-time CSV did not include corrected completed hours")
                page.get_by_role("link", name="Print time card", exact=True).click()
                if "Recorded Employee Time Card" not in page.locator("body").inner_text() or "2.33 hours" not in page.locator("body").inner_text():
                    die("direct recorded-time print report did not include corrected hours")
                if (private / "timeclock.json").read_bytes() != before_report:
                    die("exporting or printing recorded time changed the time-clock store")
                print("PASS: manual punches, reasoned owner correction, CSV, and print work without preparation or approval")
                page.get_by_role("navigation", name="Page controls").get_by_role("link", name="Home", exact=True).click()
                assert_title(page, "KCMC", "time-card Home returns to the public site")
                page.goto(BASE + "/member/timeclock.php", wait_until="domcontentloaded")
                page.get_by_role("button", name="Clock In", exact=True).click()
                page.get_by_role("button", name="Clock Out", exact=True).click()
                if "You are clocked out" not in page.locator("body").inner_text():
                    die("a recorded current time card prevented the next shift")
                print("PASS: recorded current time also permits the next manual shift without required work details")

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
                server.wait(timeout=5)
            server_log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
