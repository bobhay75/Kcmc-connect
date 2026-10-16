#!/usr/bin/env python3
"""Real-PHP, synthetic-account acceptance for the app palette and page controls.

Uses only a temporary copy and private store. Browser traffic is restricted to
that local server; no production account, message, payroll or push is used.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from html import unescape
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "KCMC-Connect-Phase6-Recreated"
spec = importlib.util.spec_from_file_location("account_routes", ROOT / "tests/member-account-routes.py")
accounts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accounts)

PUBLIC = ["index.php", "backpack-blessing.php", "bulletin.php", "care.php", "connect.php", "events.php",
          "member/login.php", "member/activate.php", "member/reset-password.php", "member/first-login.php"]
MEMBER = ["member/index.php", "member/notifications.php", "member/password.php", "member/prayer-care.php",
          "member/prayers.php", "member/timeclock.php", "member/work.php"]
ADMIN = ["admin/home.php", "admin/index.php", "admin/audit.php", "admin/connections.php",
         "admin/event-create.php", "admin/health.php", "admin/operations.php", "admin/password-resets.php",
         "admin/payroll-setup.php", "admin/posts.php", "admin/publication-designer.php", "admin/push.php",
         "admin/restore.php", "admin/rsvps.php", "admin/timecards.php", "admin/users.php"]
PASTOR = ["admin/prayer-care.php", "admin/prayer-inbox.php", "admin/prayers.php"]
PRINT_QUERY = urlencode(dict(user="owner", start="2026-08-23", end="2026-09-22"))

# Capture the real seven-minute gallery timer so its existing callback can be
# exercised without waiting seven minutes or changing the application script.
PHOTO_TIMER = """(() => {
    const nativeSet=window.setTimeout.bind(window),nativeClear=window.clearTimeout.bind(window),timers=new Map();let serial=0;
    window.setTimeout=(fn,delay,...args)=>{if(delay!==420000)return nativeSet(fn,delay,...args);const id='app-theme-photo-'+(++serial);timers.set(id,{fn,delay,args});return id};
    window.clearTimeout=id=>{if(timers.has(id))timers.delete(id);else nativeClear(id)};
    window.kcmcPhotoReview={delays:()=>[...timers.values()].map(t=>t.delay),advance:()=>{const next=timers.entries().next().value;if(!next)throw Error('No photo timer scheduled');const[id,timer]=next;timers.delete(id);timer.fn(...timer.args)}};
})();"""


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print("PASS: " + label, flush=True)


def contrast(rgb1, rgb2):
    def luminance(rgb):
        values = [v / 255 for v in rgb[:3]]
        values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(values, [.2126, .7152, .0722]))
    a, b = sorted([luminance(rgb1), luminance(rgb2)])
    return (b + .05) / (a + .05)


PALETTE = """(element) => {
    const s=getComputedStyle(element), parse=c=>{const v=[...c.matchAll(/[\\d.]+/g)].map(m=>+m[0]);return v.length===3?[...v,1]:v};
    let background=element, color;
    while(background){color=parse(getComputedStyle(background).backgroundColor);if(color[3]===1)break;background=background.parentElement;}
    return {foreground:parse(s.color),background:color||[7,18,28,1],image:s.backgroundImage,
            ownBackground:parse(s.backgroundColor),fontSize:parseFloat(s.fontSize)};
}"""


def local_target(href, base):
    target, origin = urlparse(urljoin(base + "/", href)), urlparse(base)
    return target.scheme == origin.scheme and target.netloc == origin.netloc and target.path.startswith(origin.path + "/")


def controls(page, base, label, public_home=False):
    back = page.locator("[data-kcmc-back]")
    check(back.count() == 1, label + " has exactly one explicit Back link")
    check(local_target(back.get_attribute("href") or "", base), label + " Back has a safe, usable local href")
    if public_home:
        check(back.is_hidden(), "public home keeps Back inside the closed fish menu")
        page.locator("#siteMenu summary").click()
    check(back.is_visible(), label + " Back is visible")
    # A real anchor works with JavaScript disabled or unavailable. Home remains
    # an independent escape hatch even when there is no usable history entry.
    nav = back.locator("xpath=ancestor::nav[1]")
    homes = (nav if nav.count() else page).get_by_role("link", name="Home", exact=True)
    check(homes.count() >= 1 and homes.first.is_visible(), label + " has a visible Home fallback")
    check(local_target(homes.first.get_attribute("href") or "", base), label + " Home stays within this app")
    if public_home:
        page.keyboard.press("Escape")


def theme(page, label, public_home=False):
    body = page.locator("body").evaluate(PALETTE)
    background_ok = "gradient" in body["image"]
    if public_home:
        # The approved photo homepage intentionally retains its solid navy
        # backdrop beneath the fish menu and full-bleed church photographs.
        background_ok = background_ok or (body["ownBackground"][3] == 1 and max(body["ownBackground"][:3]) < 80)
    check(background_ok and max(body["foreground"][:3]) >= 230,
          label + " uses the dark shell with soft-white text")
    # Evaluate representative real UI surfaces instead of merely checking that
    # a stylesheet tag exists. Publication page/items intentionally keep their
    # authored document colors and are tested separately below.
    surfaces = page.locator(".portal-card,.tc-card,.card,.panel,.post-card,.event-card,.bulletin-sheet,.payroll-command")
    for surface in surfaces.all():
        if not surface.is_visible():
            continue
        style = surface.evaluate(PALETTE)
        own = style["ownBackground"]
        check(not (len(own) > 3 and own[3] > .9 and min(own[:3]) > 200), label + " has no bright-white UI panel")
    for field in page.locator('input:not([type=hidden]):not([type=color]):not([type=checkbox]):not([type=radio]):not([type=range]),select,textarea').all():
        if not field.is_visible() or field.is_disabled():
            continue
        style = field.evaluate(PALETTE)
        # A readonly document-copy text area is still application UI.
        check(max(style["background"][:3]) < 110 and contrast(style["foreground"], style["background"]) >= 4.5,
              label + " form control uses a readable dark input")


def fit(page, label, width):
    check(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), label + " fits " + str(width) + "px")
    # Wide tables and the publication canvas may scroll within their own
    # container. The page controls themselves must never be clipped.
    for link in page.locator("[data-kcmc-back],.screen-navigation a").all():
        if link.is_visible():
            box = link.bounding_box()
            check(box is not None and box["x"] >= -1 and box["x"] + box["width"] <= width + 1,
                  label + " page controls stay on screen")


def sign_in(context, base, uid):
    page = context.new_page()
    page.goto(base + "/member/login.php")
    page.locator('input[name="email"]').fill(uid + "@example.invalid")
    page.locator('input[name="password"]').fill("Synthetic-Fixture-2031!")
    page.get_by_role("button", name="Sign in securely", exact=True).click()
    page.wait_for_url("**/member/")
    page.close()


@contextmanager
def diagnostic_page(context, output, label, failures=None):
    """Retain the actual failed rendering before the browser context closes."""
    page = context.new_page()
    try:
        yield page
    except Exception as failure:
        stem = "failure-" + re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-")
        metadata = dict(case=label, error=str(failure), url=page.url)
        try:
            page.screenshot(path=str(output / (stem + ".png")), full_page=True, timeout=5000)
            metadata["body_style"] = page.locator("body").evaluate(PALETTE)
            metadata["overflowing_elements"] = page.evaluate("""() => [...document.querySelectorAll('body *')]
                .map(el=>({tag:el.tagName,id:el.id,classes:String(el.className),text:(el.textContent||'').slice(0,100),
                    x:el.getBoundingClientRect().x,right:el.getBoundingClientRect().right,width:el.getBoundingClientRect().width}))
                .filter(el=>el.width>0 && (el.x < -1 || el.right > innerWidth+1)).slice(0,20)""")
        except Exception as capture_failure:
            metadata["capture_error"] = str(capture_failure)
        (output / (stem + ".json")).write_text(json.dumps(metadata, indent=2) + "\n")
        if failures is None:
            raise
        failures.append(metadata)
        print("FAIL: " + label + ": " + str(failure), flush=True)
    finally:
        page.close()


def run(app, output, http_only=False):
    f = accounts.Fixture(app)
    server = None
    output.mkdir(parents=True, exist_ok=True)
    evidence = []
    route_failures = []
    try:
        task_id = "teamtask_" + "a" * 24
        comment_id = "teamcomment_" + "b" * 24
        now = int(time.time())
        f.write("team-workspace.json", dict(version=1, revision=1, tasks={task_id: dict(id=task_id,
            revision=1, title="Prepare Sunday announcements and confirm the approved service details",
            body="Synthetic assigned work for visual and navigation acceptance.", assigned_to="member",
            created_by="owner", updated_by="owner", created_at=now, updated_at=now, blocked=True,
            priority="high", status="in_progress", publication_id="", start_date="2000-01-01", due_date="2000-01-02")},
            comments={comment_id: dict(id=comment_id, context=dict(kind="task", id=task_id), author_id="owner",
                parent_id="", body="Synthetic task conversation stays readable.", created_at=now)}, preferences={}, nonces={}))
        (f.private / "team-workspace.json").chmod(0o640)
        f.write("timeclock.json", dict(version=1, entries=[dict(id="synthetic_approved_shift", user_id="owner",
            work_date="2026-09-01", clock_in_at="2026-09-01T14:00:00+00:00", clock_out_at="2026-09-01T15:00:00+00:00",
            breaks=[], net_minutes=60, category="Media", description="Synthetic approved shift", status="closed")],
            adjustments=[], correction_requests=[], periods=[dict(user_id="owner", start="2026-08-23", end="2026-09-22",
                status="approved", submitted_at="2026-09-23T00:00:00Z", approved_at="2026-09-23T01:00:00Z", approved_by="owner")]))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
        origin = "http://127.0.0.1:" + str(port)
        base = origin + "/app"
        env = {key: value for key, value in os.environ.items() if not key.startswith("KCMC_")}
        env.update(KCMC_PRIVATE_DATA_DIR=str(f.private), KCMC_SETUP_KEY="", KCMC_OPERATIONS_OWNER_USER_ID="owner")
        with (f.root / "server.log").open("w") as log:
            server = subprocess.Popen([accounts.PHP, "-S", "127.0.0.1:" + str(port), "-t", str(f.root)],
                                      env=env, stdout=log, stderr=log)
            for _ in range(60):
                try:
                    urlopen(base + "/member/login.php", timeout=1).close(); break
                except Exception:
                    time.sleep(.1)
            else:
                raise AssertionError("Isolated PHP server did not start")

            # Enumerate every concrete PHP file that emits an HTML document.
            # Runtime error documents in shared libraries are exercised through
            # their real denied routes, never by invoking a library as a page.
            html_sources = {p.relative_to(f.app).as_posix() for p in f.app.rglob("*.php")
                            if not p.relative_to(f.app).as_posix().startswith("lib/")
                            and re.search(r"<!doctype\s+html|<html", p.read_text(), re.I)}
            covered = set(PUBLIC + MEMBER + ADMIN + PASTOR + ["admin/setup.php", "admin/save.php", "admin/timecards-print.php"])
            check(html_sources == covered - {"admin/prayer-care.php"},
                  "all concrete HTML document sources are enumerated (no screen silently omitted)")

            http_checks(f, base)
            if http_only:
                return

            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=os.environ.get("KCMC_TEST_CHROMIUM") or shutil.which("chromium") or pw.chromium.executable_path,
                                             headless=True, args=["--no-sandbox"])
                contexts = {}
                errors = []
                for actor in ["anonymous", "member", "owner", "pastor"]:
                    context = browser.new_context(service_workers="block", viewport=dict(width=390, height=844))
                    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/") else route.abort())
                    if actor != "anonymous":
                        sign_in(context, base, actor)
                    contexts[actor] = context
                # Exercise the private Back path first so an actual history
                # failure produces its diagnostic evidence without waiting for
                # the complete viewport matrix. Both clock actions finish out.
                history_and_clock(contexts, base, output, route_failures)
                (output / "results.json").write_text(json.dumps(dict(cases=evidence, failures=route_failures,
                    production=False, delivery=False), indent=2) + "\n")
                check(not route_failures, "Back and clock journeys pass before the full route matrix: " + "; ".join(
                    failure["case"] + ": " + failure["error"] for failure in route_failures))
                cases = [("anonymous", route, 410 if route.endswith("first-login.php") else 200) for route in PUBLIC]
                cases += [("member", route, 200) for route in MEMBER]
                cases += [("owner", route, 200) for route in ADMIN]
                cases += [("pastor", route, 200) for route in PASTOR]
                cases += [("owner", "admin/save.php", 403), ("member", "admin/home.php", 403),
                          ("member", "admin/timecards.php", 403), ("owner", "admin/timecards-print.php", 404),
                          ("owner", "admin/timecards-print.php?" + PRINT_QUERY, 200)]
                screenshot_routes = {"index.php": "public-home", "member/index.php": "account", "admin/home.php": "administration",
                    "member/timeclock.php": "timeclock", "admin/index.php": "publishing", "admin/publication-designer.php": "designer",
                    "admin/timecards.php": "timecards", "bulletin.php": "bulletin", "admin/event-create.php": "event-create",
                    "member/work.php": "assigned-workspace"}
                for width, height in [(390, 844), (1365, 900)]:
                    for actor, route, expected_status in cases:
                        case_label = actor + "-" + route.split("?")[0] + "-" + str(width) + "-status-" + str(expected_status)
                        with diagnostic_page(contexts[actor], output, case_label, route_failures) as page:
                            if route == "index.php":
                                page.add_init_script(PHOTO_TIMER)
                            page.set_viewport_size(dict(width=width, height=height))
                            page.on("pageerror", lambda error: errors.append(str(error)))
                            response = page.goto(base + "/" + route, wait_until="networkidle")
                            label = actor + " " + route.split("?")[0]
                            check(response.status == expected_status, label + " retains its HTTP status")
                            controls(page, base, label, route == "index.php")
                            fit(page, label, width)
                            theme(page, label, route == "index.php")
                            if route == "index.php":
                                public_home(page, width)
                            if route == "admin/home.php" and actor == "owner":
                                dropdowns(page, width)
                            if route == "member/timeclock.php":
                                check(page.get_by_role("button", name="Clock In", exact=True).is_visible(), "Clock In remains immediately available")
                            if route == "member/work.php":
                                workspace_colors(page, width)
                            if route == "admin/publication-designer.php":
                                designer_colors(page)
                            if route == "admin/payroll-setup.php":
                                fingerprint = page.locator(".payroll-shell code")
                                check(fingerprint.count() == 1 and fingerprint.evaluate("el=>[...el.getClientRects()].every(r=>r.left>=0&&r.right<=innerWidth+1)"),
                                      "the complete payroll store fingerprint wraps within the phone card")
                            if route.startswith("admin/timecards-print.php") and expected_status == 200:
                                table_region = page.get_by_role("region", name="Approved shift details", exact=True)
                                check(table_region.is_visible(), "approved time card provides a named shift-details region")
                                table_region.focus()
                                check(table_region.evaluate("el=>el===document.activeElement"), "shift-details region is keyboard focusable")
                                if table_region.evaluate("el=>el.scrollWidth>el.clientWidth+1"):
                                    page.keyboard.press("ArrowRight")
                                    page.wait_for_function("document.querySelector('.timecard-table').scrollLeft>0", timeout=2000)
                                    check(True, "narrow-screen shift details can be scrolled with the keyboard")
                                page.emulate_media(media="print")
                                check(page.locator("[data-kcmc-back]").is_hidden(), "print output excludes page controls")
                                body = page.locator("body").evaluate(PALETTE)
                                check(max(body["foreground"][:3]) < 70 and body["image"] == "none", "printed time card retains dark text on paper")
                                check(table_region.evaluate("el=>getComputedStyle(el).overflowX==='visible'")
                                      and table_region.locator("thead th").count() == 7,
                                      "printed shift details retain the full seven-column table without a screen scrollbox")
                                page.emulate_media(media="screen")
                            if actor != "member" or route != "admin/home.php":
                                filename = screenshot_routes.get(route)
                                if filename and expected_status == 200:
                                    page.screenshot(path=str(output / (filename + "-" + str(width) + ".png")), full_page=True)
                            evidence.append(dict(actor=actor, route=route.split("?")[0], width=width, status=response.status))
                # Setup has a separate unconfigured state. Restore users before
                # any signed-in request; no account is created by this test.
                users = (f.private / "users.json").read_bytes()
                f.write("users.json", dict(version=1, users=[]))
                try:
                    with diagnostic_page(contexts["anonymous"], output, "secure-setup", route_failures) as page:
                        page.goto(base + "/admin/setup.php")
                        controls(page, base, "unconfigured secure setup")
                        theme(page, "unconfigured secure setup")
                        fit(page, "unconfigured secure setup", 390)
                finally:
                    (f.private / "users.json").write_bytes(users)
                (output / "results.json").write_text(json.dumps(dict(cases=evidence, failures=route_failures,
                    production=False, delivery=False), indent=2) + "\n")
                check(not errors, "rendered pages have no uncaught JavaScript errors: " + "; ".join(errors))
                check(not route_failures, "all rendered routes pass: " + "; ".join(
                    failure["case"] + ": " + failure["error"] for failure in route_failures))
                browser.close()
        (output / "results.json").write_text(json.dumps(dict(cases=evidence, failures=route_failures,
            production=False, delivery=False), indent=2) + "\n")
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=10)
        f.close()


def http_checks(f, base):
    import http.cookiejar
    import urllib.error
    import urllib.request
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None
    def request(client, route, accept=None, data=None):
        req = urllib.request.Request(base + "/" + route,
            data=urlencode(data).encode() if data is not None else None,
            headers={"Accept": accept} if accept else {})
        try:
            response = client.open(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        return response.status, response.headers, response.read().decode()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())
    for route in ["api/team-workspace.php", "admin/publication-projects.php?watch=1"]:
        status, headers, body = request(client, route)
        check(status == 401 and "application/json" in headers.get("Content-Type", "") and isinstance(json.loads(body), dict),
              "anonymous " + route + " remains a pure JSON 401 without navigation markup")
    # The established interactive endpoints use ordinary login redirects;
    # passive polling endpoints return JSON 401. Preserve both transports.
    for route in ["member/", "admin/home.php", "admin/timecards.php", "admin/timecards-print.php",
                  "api/push-subscription.php", "admin/publication-projects.php", "admin/publication-media.php"]:
        status, headers, body = request(client, route)
        check(status == 302 and "member/login.php" in headers.get("Location", "") and "data-kcmc-back" not in body,
              "private redirect " + route + " is not decorated")
    status, headers, body = request(client, "api/content.php")
    check(status == 200 and isinstance(json.loads(body), dict) and "data-kcmc-back" not in body,
          "public content API remains pure JSON")
    # Real account session, then inspect JSON error, JSON download and CSV.
    _, _, body = request(client, "member/login.php")
    csrf = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
    data = urlencode(dict(csrf=csrf, email="owner@example.invalid", password="Synthetic-Fixture-2031!")).encode()
    try:
        client.open(base + "/member/login.php", data, timeout=10)
    except urllib.error.HTTPError as error:
        check(error.code == 302, "synthetic owner HTTP sign-in succeeds")
    for route, content_type in [("admin/save.php", "application/json"), ("admin/backup.php", "application/json"),
                                ("api/push-subscription.php", "application/json"),
                                ("admin/timecards-export.php?" + PRINT_QUERY, "text/csv")]:
        status, headers, body = request(client, route, "application/json" if "save.php" in route else None)
        expected = 403 if "save.php" in route else 405 if "push-subscription.php" in route else 200
        check(status == expected and content_type in headers.get("Content-Type", ""),
              route.split("?")[0] + " retains machine-readable transport")
        check("data-kcmc-back" not in body and "<html" not in body.lower(), route.split("?")[0] + " has no injected HTML")
        if content_type == "application/json":
            json.loads(body)
    error_navigation(f, base, request, client, NoRedirect)


def error_navigation(f, base, request, owner, no_redirect):
    """Real rejected requests retain status/auth/CSRF and never mutate stores."""
    import http.cookiejar
    import urllib.request
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.back = []; self.homes = []; self.current = None
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a":
                self.current = [attrs.get("href", ""), ""]
                if "data-kcmc-back" in attrs:
                    self.back.append(attrs.get("href", ""))
        def handle_data(self, data):
            if self.current is not None:
                self.current[1] += data
        def handle_endtag(self, tag):
            if tag == "a" and self.current is not None:
                if self.current[1].strip() == "Home":
                    self.homes.append(self.current[0])
                self.current = None
    clients = {"owner": owner}
    for actor in ["member", "pastor"]:
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), no_redirect())
        _, _, body = request(client, "member/login.php")
        csrf = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
        status, _, _ = request(client, "member/login.php", data=dict(csrf=csrf,
            email=actor + "@example.invalid", password="Synthetic-Fixture-2031!"))
        check(status == 302, "synthetic rejected-request sign-in " + actor)
        clients[actor] = client
    tokens = {}
    for actor, route in [("member", "member/prayers.php"), ("pastor", "admin/prayers.php")]:
        status, _, body = request(clients[actor], route)
        check(status == 200, "rejected-request fixture opens permitted form " + actor)
        tokens[actor] = unescape(re.search(r'name="csrf" value="([^"]+)"', body).group(1))
    def snapshot():
        return {path.relative_to(f.private).as_posix(): path.read_bytes()
                for path in f.private.rglob("*") if path.is_file()}
    before = snapshot()
    cases = [
        ("owner", "admin/timecards-print.php", None, 404, None),
        ("member", "admin/timecards-print.php", None, 403, None),
        ("member", "member/prayer-care.php", dict(csrf="invalid", revision="0", action="join"), 403, None),
        ("member", "member/submit-prayer.php", dict(csrf="invalid", message="Synthetic rejected request."), 403, None),
        ("member", "member/submit-prayer.php", dict(csrf=tokens["member"], message="short"), 422, None),
        ("member", "member/logout.php", None, 405, "POST"),
        ("member", "member/logout.php", dict(csrf="invalid"), 403, None),
        ("pastor", "member/prayer-team.php", {}, 405, "GET, HEAD"),
        ("pastor", "admin/prayers.php", dict(csrf="invalid", action="approve"), 403, None),
        ("pastor", "admin/prayers.php", dict(csrf=tokens["pastor"], action="invalid"), 422, None),
    ]
    for actor, route, data, expected, allow in cases:
        status, headers, body = request(clients[actor], route, data=data)
        label = actor + " " + route + " " + str(expected)
        check(status == expected and "no-store" in headers.get("Cache-Control", ""), label + " retains rejection and private headers")
        if allow is not None:
            check(headers.get("Allow") == allow, label + " retains allowed methods")
        parsed = Links(); parsed.feed(body)
        check(len(parsed.back) == 1 and local_target(parsed.back[0], base)
              and bool(parsed.homes) and all(local_target(href, base) for href in parsed.homes),
              label + " offers a real local Back and Home escape")
        check("text/html" in headers.get("Content-Type", "") and "app-theme.css" in body,
              label + " is a styled human-facing error document")
        check(snapshot() == before, label + " leaves all private store bytes unchanged")
    status, _, body = request(clients["member"], "member/")
    check(status == 200 and "My Account" in body, "rejected sign-out leaves the existing member session usable")


def dropdowns(page, width):
    groups = page.locator("details.admin-group")
    check(groups.count() == 3 and groups.evaluate_all("nodes=>nodes.every(node=>!node.open)"), "all three Administration groups begin collapsed")
    for label in ["Work & publishing", "People & care", "Operations"]:
        summary = page.locator("details.admin-group > summary").filter(has_text=label)
        check(summary.count() == 1 and summary.is_visible(), "Administration exposes " + label + " heading")
        summary.focus()
        page.keyboard.press("Enter")
        check(summary.locator("..").get_attribute("open") is not None, label + " expands with keyboard")
        page.keyboard.press(" ")
        check(summary.locator("..").get_attribute("open") is None, label + " collapses with keyboard")
    operations = page.locator("details.admin-group").filter(has=page.locator("summary").filter(has_text="Operations"))
    check(operations.get_by_role("link", name="Open Employee time cards", exact=True).is_hidden(), "closed Operations hides its tool links")
    operations.locator("summary").click()
    check(operations.get_by_role("link", name="Open Employee time cards", exact=True).is_visible(), "Operations reveals employee time cards")
    fit(page, "expanded Administration", width)
    operations.locator("summary").click()


def public_home(page, width):
    """No welcome-copy clutter or empty lazy-photo shells on the current home."""
    home = page.locator('[data-view="home"]')
    menu = page.locator("#siteMenu")
    check(menu.get_attribute("open") is None, "public home keeps the fish dropdown closed")
    for element in home.locator(".home-cover-card > .eyebrow,.home-cover-card h1,.home-cover-card > .lead,.home-worship-strip,.family-welcome-copy").all():
        check(element.is_hidden(), "welcome copy, service strip and family prose stay off the photo homepage")
    check(home.locator("[data-hero-previous]:visible,[data-hero-toggle]:visible,[data-hero-next]:visible").count() == 3,
          "the three compact photo controls remain available")
    for shell in home.locator(".home-cover-card,.home-cover-layout").all():
        color = shell.evaluate(PALETTE)["ownBackground"]
        check(color[3] == 0 or max(color[:3]) < 100, "photo controls have a navy or transparent shell without a cream card")
    outside_actions = page.locator("body a:visible,body button:visible").evaluate_all("""elements=>elements.filter(el=>
        !el.closest('#siteMenu')&&!el.matches('.skip-link,[data-hero-previous],[data-hero-toggle],[data-hero-next]')).map(el=>el.textContent.trim())""")
    check(outside_actions == [], "homepage destination actions stay inside the fish menu")
    check(home.locator('[data-hero-photo]').count() == 4 and home.locator('[data-hero-photo]:visible').count() == 1,
          "the approved four-photo carousel keeps one visible image plane")
    gallery = home.locator('[aria-label="KCMC kids and family photos"]')
    family = home.locator('[data-family-welcome]')
    check(gallery.is_visible() and gallery.locator('img:visible').count() == 3
          and family.is_visible() and family.locator('img:visible').count() == 1,
          "the three supplied gallery photos and family photo remain on the homepage")
    # Simulate reaching each photo before a full-page capture. A full-page
    # screenshot alone does not trigger native below-the-fold lazy loading.
    for photo in home.locator('img:visible').all():
        photo.scroll_into_view_if_needed()
        page.wait_for_function("img=>img.complete&&img.naturalWidth>0", arg=photo.element_handle(), timeout=10000)
    page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    page.wait_for_function("window.scrollY===0")
    photo = home.locator('[data-hero-photo]:visible')
    check(photo.evaluate("el=>getComputedStyle(el).objectFit==='contain'&&el.naturalWidth>0"),
          "the authentic church photograph remains fully contained and decoded")
    hero_box = home.locator('[data-hero-gallery]').bounding_box()
    photo_box = photo.bounding_box()
    control_box = home.locator('[data-hero-controls]').bounding_box()
    check(hero_box['height'] <= photo_box['height'] + control_box['height'] + 64,
          "the photo cover has no reserved welcome-card space")
    sections = home.locator(':scope > .section:visible')
    check(sections.count() == 2, "only the retained gallery and family photo sections follow the cover")
    for section in sections.all():
        bounds = [image.bounding_box() for image in section.locator('img:visible').all()]
        check(bool(bounds), "each visible homepage section contains a real photograph")
        photo_span = max(box['y'] + box['height'] for box in bounds) - min(box['y'] for box in bounds)
        check(section.bounding_box()['height'] <= photo_span + 96,
              "a photo section has no large empty text shell beneath its images")
    # Exercise the actual scheduled callback, followed by the manual controls.
    page.mouse.move(width - 1, 10)
    check(page.evaluate("window.kcmcPhotoReview.delays()")==[420000], "public photo rotation retains the seven-minute interval")
    first = photo.get_attribute('src')
    page.evaluate("window.kcmcPhotoReview.advance()")
    check(home.locator('[data-hero-photo]:visible').get_attribute('src') != first,
          "the existing automatic photo callback still advances the carousel")
    home.locator('[data-hero-previous]').click()
    check(home.locator('[data-hero-photo]:visible').get_attribute('src') == first, "Previous photo still works")
    home.locator('[data-hero-next]').click()
    check(home.locator('[data-hero-photo]:visible').get_attribute('src') != first, "Next photo still works")
    home.locator('[data-hero-previous]').click()
    check(page.evaluate("window.kcmcPhotoReview.delays()")==[], "manual photo selection pauses automatic changes")
    home.locator('[data-hero-toggle]').click()
    page.mouse.move(width - 1, 10)
    check(page.evaluate("window.kcmcPhotoReview.delays()")==[420000], "Play photos restores automatic rotation")
    for route in ['visit', 'watch', 'news', 'events', 'serve', 'partner']:
        menu.locator('summary').click()
        menu.locator('a[data-route="'+route+'"]').click()
        page.wait_for_function("route=>document.querySelector('[data-view=\"'+route+'\"]').classList.contains('active')", arg=route)
        view = page.locator('[data-view="'+route+'"]')
        check(view.is_visible() and len(view.inner_text().strip()) > 10, route + " content remains reachable through the fish")
        check(menu.get_attribute('open') is None, route + " selection closes the fish dropdown")
        fit(page, 'public '+route, width)
        menu.locator('summary').click()
        menu.get_by_role('link', name='Home', exact=True).click()
        page.wait_for_function("document.querySelector('[data-view=home]').classList.contains('active')")
    page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    fit(page, 'photo homepage after fish navigation', width)


def designer_colors(page):
    page.wait_for_function("document.getElementById('page').children.length > 0")
    canvas = page.locator("#page").evaluate(PALETTE)
    check(min(canvas["ownBackground"][:3]) >= 245, "publication canvas stays white inside the navy workspace")
    item = page.locator('#page .item[data-type="text"]').first
    item.evaluate("el=>{el.style.color='rgb(67, 20, 92)';el.style.backgroundColor='rgb(250, 238, 211)'}")
    before = item.evaluate("el=>({color:getComputedStyle(el).color,background:getComputedStyle(el).backgroundColor})")
    check(before == dict(color="rgb(67, 20, 92)", background="rgb(250, 238, 211)"),
          "publication object keeps its chosen colors inside screen theme")
    page.emulate_media(media="print")
    check(page.locator(".topbar").is_hidden() and page.locator(".panel").first.is_hidden(), "publication print excludes workspace chrome")
    check(item.evaluate("el=>({color:getComputedStyle(el).color,background:getComputedStyle(el).backgroundColor})") == before,
          "screen and print media never rewrite authored publication object colors")
    page.emulate_media(media="screen")


def workspace_colors(page, width):
    page.wait_for_function("document.getElementById('work-tasks').getAttribute('aria-busy') === 'false'")
    check(page.locator(".work-task").count() == 1, "assigned workspace renders a real saved task instead of an empty-state fixture")
    for view in ["list", "board", "timeline"]:
        page.get_by_role("combobox", name="View", exact=True).select_option(view)
        task = page.locator(".work-task")
        for state in ["resting", "hover", "selected"]:
            if state == "hover":
                task.hover()
            elif state == "selected":
                task.click()
            style = task.evaluate(PALETTE)
            background = style["ownBackground"]
            check(max(background[:3]) < 110 and background[3] == 1,
                  view + " " + state + " task remains a dark surface")
            labels = task.locator(".work-task-title,.work-task-meta,.work-task-flag")
            check(labels.count() >= 6, "assigned task exposes title, date/status and priority/blocked/overdue/comment metadata")
            for text in labels.all():
                check(contrast(text.evaluate(PALETTE)["foreground"], background) >= 4.5,
                      view + " " + state + " " + text.inner_text() + " meets normal-text contrast")
        fit(page, view + " populated workspace", width)
    page.get_by_role("combobox", name="View", exact=True).select_option("list")
    page.locator(".work-task").click()
    page.wait_for_function("document.getElementById('work-comments').textContent.includes('Synthetic task conversation')")
    check(page.locator(".work-comment").count() == 1, "assigned task conversation appears in the same workspace")


def history_and_clock(contexts, base, output, failures):
    snapshots = []
    script_errors = []
    native_state_journey(contexts["member"], base, output, failures)
    def snapshot(page, phase):
        value = page.evaluate("""() => {
            const nav=window.navigation, entry=e=>e?{key:e.key,index:e.index,url:e.url,marker:typeof e.getState==='function'?e.getState()?.kcmcAppScreenV1??null:null}:null;
            let state={type:typeof nav,canGoBack:null,current:null,entries:[]};
            try{if(nav)state={type:typeof nav,canGoBack:nav.canGoBack??null,current:entry(nav.currentEntry),entries:typeof nav.entries==='function'?nav.entries().map(entry):[]}}catch(error){state.error=String(error)}
            const script=document.querySelector('script[src*="/app-navigation.js"]'),resources=performance.getEntriesByType('resource').filter(r=>r.name.includes('/app-navigation.js'));
            return {url:location.href,hash:location.hash,appBase:document.querySelector('[data-kcmc-back]')?.dataset.kcmcAppBase??null,
                isSecureContext:window.isSecureContext,referrer:document.referrer,readyState:document.readyState,historyLength:history.length,navigation:state,
                scriptReady:document.documentElement.dataset.kcmcNavigationReady==='true',
                scripts:[...document.scripts].filter(s=>s.src.includes('/app-navigation.js')).map(s=>({src:s.src,defer:s.defer})),
                scriptResources:resources.map(r=>({url:r.name,startTime:r.startTime,responseEnd:r.responseEnd,duration:r.duration,responseStatus:r.responseStatus??null}))};
        }""")
        value.update(phase=phase, script_errors=list(script_errors))
        snapshots.append(value)
        (output / "private-back-history.json").write_text(json.dumps(snapshots, indent=2) + "\n")
    with diagnostic_page(contexts["member"], output, "private-back-history", failures) as page:
        page.on("pageerror", lambda error: script_errors.append(str(error)))
        page.on("requestfailed", lambda request: script_errors.append(request.url + ": " + str(request.failure))
                if "/app-navigation.js" in request.url else None)
        try:
            page.goto(base + "/member/")
            page.locator('.screen-navigation a[href$="/member/timeclock.php"]').click()
            page.wait_for_url("**/member/timeclock.php")
            page.wait_for_function("document.documentElement.dataset.kcmcNavigationReady === 'true'")
            snapshot(page, "initial-clock-before-back")
            page.locator("[data-kcmc-back]").click()
            page.wait_for_url("**/member/")
            check(True, "Back returns to the previous same-app screen")
            page.locator('.screen-navigation a[href$="/member/timeclock.php"]').click()
            page.wait_for_url("**/member/timeclock.php")
            page.evaluate("url=>location.assign(url)", base + "/member/notifications.php")
            page.wait_for_url("**/member/notifications.php")
            check(page.evaluate("document.referrer === ''"), "private document keeps no-referrer policy")
            page.wait_for_function("document.documentElement.dataset.kcmcNavigationReady === 'true'")
            snapshot(page, "notifications-before-back")
            page.locator("[data-kcmc-back]").click()
            snapshot(page, "notifications-back-after-click")
            page.wait_for_url("**/member/timeclock.php", timeout=10000)
            check(True, "private Back uses same-app history despite an empty referrer")
            check(not script_errors, "private Back navigation has no script load or execution errors")
        finally:
            snapshot(page, "private-history-final-url")
    # New-page history has no previous app entry. Its real fallback is useful.
    with diagnostic_page(contexts["member"], output, "direct-entry-back-and-clock", failures) as page:
        page.goto(base + "/member/timeclock.php", referer="https://external.example.invalid/elsewhere")
        expected = urljoin(page.url, page.locator("[data-kcmc-back]").get_attribute("href"))
        page.locator("[data-kcmc-back]").click()
        page.wait_for_url(expected)
        check(page.url.startswith(base + "/"), "Back from external entry uses its local fallback")
        page.goto(base + "/member/timeclock.php")
        page.get_by_role("button", name="Clock In", exact=True).click()
        check(page.get_by_role("button", name="Clock Out", exact=True).is_visible(), "a member can still clock in without opening a menu")
        page.get_by_role("button", name="Clock Out", exact=True).click()
        check(page.get_by_role("button", name="Clock In", exact=True).is_visible(), "a member can still clock out without opening a menu")
    context = contexts["anonymous"].browser.new_context(java_script_enabled=False)
    try:
        with diagnostic_page(context, output, "back-without-javascript", failures) as page:
            page.goto(base + "/member/reset-password.php")
            expected = urljoin(page.url, page.locator("[data-kcmc-back]").get_attribute("href"))
            page.locator("[data-kcmc-back]").click()
            page.wait_for_url(expected)
            check(True, "Back has a working fallback without JavaScript")
    finally:
        context.close()


def native_state_journey(context, base, output, failures):
    """Real native-entry state survives private reload and browser traversal."""
    seed = """(() => {
        const classic={unrelatedClassic:{exact:['keep',7]}};
        if(history.state===null)history.replaceState(classic,'',location.href);
        const nav=window.navigation;
        if(nav?.currentEntry&&typeof nav.currentEntry.getState==='function'&&typeof nav.updateCurrentEntry==='function'){
            const state=nav.currentEntry.getState();
            if(state===undefined||state===null)nav.updateCurrentEntry({state:{unrelatedNavigation:{exact:['keep',9]}}});
            window.__beforeKcmcApp={historyLength:history.length,entryCount:nav.entries().length};
        }
    })();"""
    observations = []
    def state(page, phase, freshly_loaded=True):
        page.wait_for_function("document.documentElement.dataset.kcmcNavigationReady === 'true'")
        value = page.evaluate("""() => {
            const nav=window.navigation,current=nav.currentEntry,entryState=current.getState();
            return {url:location.href,path:location.pathname,referrer:document.referrer,
                entryKey:current.key,entryIndex:current.index,entryCount:nav.entries().length,
                historyLength:history.length,beforeApp:window.__beforeKcmcApp,
                marker:entryState?.kcmcAppScreenV1??null,unrelatedNavigation:entryState?.unrelatedNavigation??null,
                classicState:history.state};
        }""")
        value["phase"] = phase; observations.append(value)
        (output / "native-navigation-state.json").write_text(json.dumps(observations, indent=2) + "\n")
        expected_marker = dict(version=1, base=urlparse(base).path + "/", origin=urlparse(base).scheme + "://" + urlparse(base).netloc,
                               path=value["path"], key=value["entryKey"], index=value["entryIndex"])
        check(value["marker"] == expected_marker,
              phase + " native marker stores only the exact app boundary, path and native entry identity")
        check(value["unrelatedNavigation"] == dict(exact=["keep", 9])
              and value["classicState"] == dict(unrelatedClassic=dict(exact=["keep", 7])),
              phase + " preserves unrelated Navigation API and classic History state")
        if freshly_loaded:
            check(value["beforeApp"] == dict(historyLength=value["historyLength"], entryCount=value["entryCount"]),
                  phase + " adds no native or classic history entries")
        return value
    with diagnostic_page(context, output, "native-entry-state-and-traversal", failures) as page:
        page.add_init_script(seed)
        account = base + "/member/?fixture_context=synthetic-private#personal-test"
        clock = base + "/member/timeclock.php?fixture_context=synthetic-private#shift-test"
        notifications = base + "/member/notifications.php?fixture_context=synthetic-private#device-test"
        page.goto(account)
        initial = state(page, "account-initial")
        page.reload()
        reloaded = state(page, "account-reloaded")
        check(initial["historyLength"] == reloaded["historyLength"] and initial["entryCount"] == reloaded["entryCount"],
              "reloading a marked private screen adds no history entry")
        page.goto(clock)
        state(page, "clock-before-next-screen")
        page.goto(notifications)
        total = state(page, "notifications-before-native-back")
        check(total["referrer"] == "", "native state journey keeps private referrers hidden")
        page.locator("[data-kcmc-back]").click()
        page.wait_for_url(clock, timeout=10000)
        returned = state(page, "clock-after-native-back", freshly_loaded=False)
        check(returned["historyLength"] == total["historyLength"] and returned["entryCount"] == total["entryCount"],
              "private Back traverses an existing entry and preserves its exact private query and fragment")
        page.go_forward()
        page.wait_for_url(notifications)
        state(page, "notifications-after-browser-forward", freshly_loaded=False)
        page.locator("[data-kcmc-back]").click()
        page.wait_for_url(clock, timeout=10000)
        state(page, "clock-after-back-again", freshly_loaded=False)
        same_path = base + "/member/timeclock.php?fixture_context=second-private#another-shift-test"
        page.goto(same_path)
        state(page, "same-path-distinct-private-entry")
        page.locator("[data-kcmc-back]").click()
        page.wait_for_url(clock, timeout=10000)
        state(page, "same-path-private-back", freshly_loaded=False)
        check(True, "different private entries at the same path can return through actual native history")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=APP)
    parser.add_argument("--output", type=Path, default=ROOT / "test-artifacts/app-theme")
    parser.add_argument("--http-only", action="store_true")
    args = parser.parse_args()
    run(args.app.resolve(), args.output.resolve(), args.http_only)
