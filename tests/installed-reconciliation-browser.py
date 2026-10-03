#!/usr/bin/env python3
"""Focused acceptance of the installed Tony staff entry and four-page repair.

Runs a copied real PHP app with synthetic accounts/records in temporary storage.
No production traffic, credentials, email, push, or church-record mutations.
Screenshots and measured contrast results use KCMC_RECONCILIATION_OUTPUT.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1] / "KCMC-Connect-Phase6-Recreated"
OUT = Path(os.environ.get("KCMC_RECONCILIATION_OUTPUT", "/tmp/kcmc-reconciliation-review"))
PAGES = {
    "admin/health.php": "Release Health",
    "admin/audit.php": "Audit History",
    "admin/timecards.php": "Time Cards",
    "member/timeclock.php": "Time Clock",
}
PASSWORD = "Synthetic-Reconciliation-Test-2031!"
EMAIL = "reconciliation-admin@example.invalid"


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print("PASS:", label, flush=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed_private(private: Path) -> None:
    password_hash = subprocess.run(
        ["php", "-r", "echo password_hash($argv[1], PASSWORD_DEFAULT);", PASSWORD],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    users = []
    for user_id, email, name, role in [
        ("synthetic_admin", EMAIL, "Synthetic Review Admin", "pastor_admin"),
        ("synthetic_employee", "employee@example.invalid", "Synthetic Employee", "member"),
    ]:
        users.append({"id": user_id, "email": email, "email_normalized": email,
                      "display_name": name, "role": role, "active": True,
                      "password_hash": password_hash, "created_at": "2031-01-01T00:00:00Z"})
    (private / "users.json").write_text(json.dumps({"version": 1, "users": users}))
    (private / "login-attempts.json").write_text(json.dumps({"attempts": {}}))
    today = datetime.now(ZoneInfo("America/Chicago")).date()
    start = today.replace(day=23)
    if today.day < 23:
        start = (today.replace(day=1) - timedelta(days=1)).replace(day=23)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=23)
    end = next_month - timedelta(days=1)
    stamp = today.isoformat()
    entries = []
    for user_id, entry_id, status in [
        ("synthetic_admin", "admin_completed", "completed"),
        ("synthetic_employee", "employee_submitted", "submitted"),
    ]:
        entries.append({"id": entry_id, "user_id": user_id, "work_date": stamp,
                        "clock_in_at": stamp + "T13:00:00Z", "clock_out_at": stamp + "T14:00:00Z",
                        "breaks": [], "category": "KCMC Connect / IT", "net_minutes": 60,
                        "description": "Synthetic display-only reconciliation fixture.",
                        "status": status, "corrections": []})
    entries.append({**entries[0], "id": "admin_open", "status": "open",
                    "clock_in_at": stamp + "T15:00:00Z", "clock_out_at": None, "net_minutes": 0})
    state = {"version": 1, "entries": entries, "adjustments": [],
             "periods": [{"user_id": "synthetic_employee", "start": start.isoformat(),
                          "end": end.isoformat(), "status": "submitted",
                          "submitted_at": stamp + "T14:01:00Z"}],
             "correction_requests": [{"id": "synthetic_correction", "entry_id": "employee_submitted",
                                      "user_id": "synthetic_employee", "status": "pending",
                                      "reason": "Synthetic correction to expose review controls.",
                                      "requested_at": stamp + "T14:02:00Z"}]}
    (private / "timeclock.json").write_text(json.dumps(state))


# Measure the repaired solid cards, including controls and placeholders. The
# installed repair intentionally retains the existing dark outer-page gradients;
# a solid-color calculation is not pixel evidence for those gradient surfaces.
CONTRAST_JS = r"""() => {
    const rgba = value => {
        const m = value.match(/^rgba?\(([^)]+)\)$/);
        if (!m) throw new Error('Unsupported computed color: ' + value);
        const parts = m[1].split(',').map(Number);
        return parts.length === 3 ? [...parts, 1] : parts;
    };
    const over = (top, bottom) => top.slice(0,3).map((v,i) => v*top[3]+bottom[i]*(1-top[3]));
    const background = el => {
        const layers = [];
        for (let node=el; node; node=node.parentElement) {
            const style = getComputedStyle(node);
            if (style.backgroundImage !== 'none') throw new Error('Unexpected background image: '+node.tagName);
            const color = rgba(style.backgroundColor);
            layers.push(color);
            if (color[3] === 1) break;
        }
        return layers.reverse().reduce((bg,fg) => over(fg,bg), [255,255,255]);
    };
    const lum = rgb => rgb.map(v => v/255).map(v => v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
        .reduce((sum,v,i) => sum+v*[.2126,.7152,.0722][i],0);
    const measure = (el, color, kind, text) => {
        const bg=background(el), fg=over(rgba(color),bg), a=lum(fg), b=lum(bg);
        return {kind, text:text.trim().slice(0,90), foreground:color, background:bg,
                ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
    };
    const rows=[];
    const targets=':is(.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card)';
    for (const el of document.querySelectorAll(targets+', '+targets+' *, .health-pill')) {
        const style=getComputedStyle(el), rect=el.getBoundingClientRect();
        if (!rect.width || !rect.height || style.visibility!=='visible' || Number(style.opacity)===0) continue;
        const direct=[...el.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join(' ').trim();
        if (direct && el.tagName!=='OPTION') rows.push(measure(el,style.color,'text',direct));
        if (el.matches('input:not([type=hidden]):not([type=checkbox]), select, textarea')) {
            rows.push(measure(el,style.color,'control',el.name));
            if (el.placeholder) rows.push(measure(el,getComputedStyle(el,'::placeholder').color,'placeholder',el.placeholder));
        }
    }
    return rows;
}"""


def check_controls_and_keyboard(page, label: str) -> int:
    controls = page.locator("main a[href], main button, main input:not([type=hidden]), main select, main textarea, main summary")
    expected = []
    for index in range(controls.count()):
        control = controls.nth(index)
        if not control.is_visible() or not control.is_enabled():
            continue
        token = str(index)
        control.evaluate("(el, token) => el.setAttribute('data-reconciliation-control', token)", token)
        expected.append(token)
        box = control.bounding_box()
        check(bool(box) and box["x"] >= -1 and box["x"] + box["width"] <= page.viewport_size["width"] + 1,
              f"{label}: visible control {index} fits viewport")
    check(bool(expected), f"{label}: rendered interactive controls exist")
    # Tab through real controls; no click/submit/approval/export is performed.
    page.locator("body").evaluate("el => { el.tabIndex=-1; el.focus(); }")
    reached = set()
    for _ in range(len(expected) * 8 + 10):
        page.keyboard.press("Tab")
        focused = page.evaluate("""() => {
            const el=document.activeElement, s=getComputedStyle(el), r=el.getBoundingClientRect();
            return {id:el.getAttribute('data-reconciliation-control'),
                    visible:el.matches(':focus-visible'), outline:s.outlineStyle, width:parseFloat(s.outlineWidth),
                    color:s.outlineColor,
                    repaired:!!el.closest('.health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card'),
                    left:r.left, right:r.right, top:r.top, bottom:r.bottom};
        }""")
        if focused["id"] in expected:
            check(focused["visible"] and focused["outline"] != "none" and focused["width"] >= 3
                  and (not focused["repaired"] or focused["color"] == "rgb(23, 77, 117)"),
                  f"{label}: control {focused['id']} has visible keyboard focus ring")
            check(focused["left"] >= -1 and focused["right"] <= page.viewport_size["width"] + 1
                  and focused["bottom"] > 0 and focused["top"] < page.viewport_size["height"],
                  f"{label}: focused control {focused['id']} is on screen")
            reached.add(focused["id"])
        if reached == set(expected):
            break
    check(reached == set(expected), f"{label}: Tab reaches every visible enabled control")
    return len(reached)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    original_content = sha256(APP / "data/content.json")
    with tempfile.TemporaryDirectory(prefix="kcmc-reconciliation-") as td:
        work = Path(td)
        local = work / "app"
        shutil.copytree(APP, local, ignore=shutil.ignore_patterns("config.php", "private", "backups"))
        copied_content = sha256(local / "data/content.json")
        private = work / "private"
        private.mkdir(mode=0o750)
        seed_private(private)
        original_timeclock = sha256(private / "timeclock.json")
        sessions = work / "sessions"
        sessions.mkdir(mode=0o700)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        base = origin + "/app"
        # Do not inherit installation-specific KCMC configuration.
        env = {key: value for key, value in os.environ.items() if not key.startswith("KCMC_")}
        env.update({"KCMC_PRIVATE_DATA_DIR": str(private), "KCMC_SETUP_KEY": ""})
        with (work / "php.log").open("w+") as log:
            server = subprocess.Popen(
                ["php", "-d", f"session.save_path={sessions}", "-S", f"127.0.0.1:{port}", "-t", str(work)],
                stdout=log, stderr=log, env=env,
            )
            try:
                for _ in range(60):
                    try:
                        with urllib.request.urlopen(base + "/", timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError("Isolated PHP application failed to start")
                results = []
                with sync_playwright() as playwright:
                    launch = {"executable_path": os.environ["KCMC_CHROMIUM_PATH"]} if os.environ.get("KCMC_CHROMIUM_PATH") else {}
                    browser = playwright.chromium.launch(**launch)
                    context = browser.new_context(viewport={"width": 390, "height": 844},
                                                  reduced_motion="reduce", service_workers="block")
                    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/") else route.abort())
                    page = context.new_page()
                    errors, failures = [], []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("response", lambda response: failures.append(f"{response.status} {response.url}")
                            if response.url.startswith(base) and response.status >= 400 else None)
                    page.goto(base + "/", wait_until="networkidle")
                    page.locator("#siteMenu summary").focus()
                    page.keyboard.press("Enter")
                    staff = page.locator("#siteMenu .menu-account")
                    check(staff.is_visible() and staff.inner_text() == "Staff Sign In", "anonymous menu exposes Staff Sign In")
                    check(staff.get_attribute("href") == "/app/admin/login.php", "staff entry points to admin/login.php")
                    with page.expect_navigation(wait_until="domcontentloaded") as navigation:
                        staff.click()
                    response = navigation.value
                    check("/member/login.php?next=" in page.url and page.locator('input[name="next"]').input_value() == "/app/admin/",
                          "admin entry redirects to member login with staff return path")
                    check(page.title() == "Staff Sign In • KCMC Connect", "installed staff title renders")
                    check(page.locator(".eyebrow").inner_text() == "KCMC STAFF", "installed staff eyebrow renders")
                    check(page.locator(".portal-lead").inner_text() ==
                          "Staff and authorized ministry teams sign in here. Everyone can use the public app for free without an account. Private records remain protected.",
                          "installed staff/public-access copy renders")
                    check(response is not None and "no-store" in response.headers.get("cache-control", ""), "staff sign-in sends no-store")
                    check(len(page.locator('input[name="csrf"]').input_value()) >= 32, "staff form has CSRF token")
                    # Valid synthetic credentials cannot authenticate without the session CSRF.
                    page.locator('input[name="csrf"]').evaluate("el => el.value='invalid-synthetic-token'")
                    page.locator('input[name="email"]').fill(EMAIL)
                    page.locator('input[name="password"]').fill(PASSWORD)
                    page.locator('button[type="submit"]').click()
                    page.wait_for_load_state("domcontentloaded")
                    check(page.locator(".portal-alert.error").inner_text() == "Please reload the page and try again.", "invalid CSRF blocks staff authentication")
                    for path in ["member/", *PAGES]:
                        page.goto(base + "/" + path, wait_until="domcontentloaded")
                        check("/member/login.php" in page.url, f"anonymous {path} remains protected")
                    page.goto(base + "/admin/login.php", wait_until="domcontentloaded")
                    page.locator('input[name="email"]').fill(EMAIL)
                    page.locator('input[name="password"]').fill(PASSWORD)
                    page.locator('button[type="submit"]').click()
                    page.wait_for_url(base + "/admin/")
                    check("KCMC Publishing Desk" in page.title(), "synthetic pastor_admin authenticates through staff entry")
                    for scheme in ["light", "dark"]:
                        page.emulate_media(color_scheme=scheme)
                        for width in [320, 390, 1440]:
                            page.set_viewport_size({"width": width, "height": 900})
                            for path, title in PAGES.items():
                                label = f"{path} {width}px {scheme}"
                                response = page.goto(base + "/" + path, wait_until="networkidle")
                                name = path.replace("/", "-").replace(".php", "") + f"-{width}-{scheme}.png"
                                # Keep evidence even when a subsequent assertion finds
                                # a real limitation in the already-installed source.
                                page.screenshot(path=str(OUT / name), full_page=True)
                                check(response is not None and response.status == 200 and title in page.title(), label + ": authenticated render")
                                check("no-store" in response.headers.get("cache-control", ""), label + ": no-store retained")
                                check(page.evaluate("document.documentElement.scrollWidth <= innerWidth"), label + ": no horizontal overflow")
                                cards = page.locator(".health-stat,.health-check,.audit-row,.audit-empty,.tc-card,.correction-card")
                                check(cards.count() > 0 and cards.evaluate_all("els => els.every(el => getComputedStyle(el).colorScheme === 'light')"),
                                      label + ": repaired card palette remains light")
                                if path == "admin/audit.php":
                                    check(page.locator(".audit-toolbar .audit-time").evaluate("el => getComputedStyle(el).color") == "rgb(197, 212, 220)",
                                          label + ": toolbar uses installed dark-surface text color")
                                ratios = page.evaluate(CONTRAST_JS)
                                check(len(ratios) >= 5, label + ": key text/control contrast samples exist")
                                low = [row for row in ratios if row["ratio"] < 4.5]
                                check(not low, label + ": text, controls and placeholders meet 4.5:1; " + json.dumps(low))
                                control_count = check_controls_and_keyboard(page, label)
                                page.evaluate("window.scrollTo(0,0)")
                                results.append({"path": path, "width": width, "scheme": scheme,
                                                "contrast": ratios, "keyboard_controls": control_count, "screenshot": name})
                    check(not errors, "no browser JavaScript errors: " + "; ".join(errors))
                    check(not failures, "no failed local responses: " + "; ".join(failures))
                    context.close()
                    browser.close()
                (OUT / "readability-results.json").write_text(json.dumps(results, indent=2))
                check(sha256(local / "data/content.json") == copied_content, "copied public content remains byte-for-byte unchanged")
                check(sha256(APP / "data/content.json") == original_content, "repository public content remains byte-for-byte unchanged")
                check(sha256(private / "timeclock.json") == original_timeclock, "display and keyboard checks do not change synthetic time records")
                log.flush()
                log.seek(0)
                php_log = log.read()
                check(not any(marker in php_log for marker in ["PHP Warning:", "PHP Fatal error:", "PHP Parse error:"]), "no PHP warnings/fatal errors in isolated server log")
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
    print("Installed reconciliation browser acceptance passed.")


if __name__ == "__main__":
    main()
