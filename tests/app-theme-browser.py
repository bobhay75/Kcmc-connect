#!/usr/bin/env python3
"""Real-PHP, synthetic-account acceptance for the app palette and page controls.

Uses only a temporary copy and private store. Browser traffic is restricted to
that local server; no production account, message, payroll or push is used.
"""
from __future__ import annotations

import argparse
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


def theme(page, label):
    body = page.locator("body").evaluate(PALETTE)
    check("gradient" in body["image"] and max(body["foreground"][:3]) >= 230,
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


def run(app, output, http_only=False):
    f = accounts.Fixture(app)
    server = None
    output.mkdir(parents=True, exist_ok=True)
    evidence = []
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
                        page = contexts[actor].new_page()
                        page.set_viewport_size(dict(width=width, height=height))
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        response = page.goto(base + "/" + route, wait_until="networkidle")
                        label = actor + " " + route.split("?")[0]
                        check(response.status == expected_status, label + " retains its HTTP status")
                        controls(page, base, label, route == "index.php")
                        fit(page, label, width)
                        theme(page, label)
                        if route == "admin/home.php" and actor == "owner":
                            dropdowns(page, width)
                        if route == "member/timeclock.php":
                            check(page.get_by_role("button", name="Clock In", exact=True).is_visible(), "Clock In remains immediately available")
                        if route == "member/work.php":
                            workspace_colors(page, width)
                        if route == "admin/publication-designer.php":
                            designer_colors(page)
                        if route.startswith("admin/timecards-print.php") and expected_status == 200:
                            page.emulate_media(media="print")
                            check(page.locator("[data-kcmc-back]").is_hidden(), "print output excludes page controls")
                            body = page.locator("body").evaluate(PALETTE)
                            check(max(body["foreground"][:3]) < 70 and body["image"] == "none", "printed time card retains dark text on paper")
                            page.emulate_media(media="screen")
                        if actor != "member" or route != "admin/home.php":
                            filename = screenshot_routes.get(route)
                            if filename and expected_status == 200:
                                page.screenshot(path=str(output / (filename + "-" + str(width) + ".png")), full_page=True)
                        evidence.append(dict(actor=actor, route=route.split("?")[0], width=width, status=response.status))
                        page.close()
                # Setup has a separate unconfigured state. Restore users before
                # any signed-in request; no account is created by this test.
                users = (f.private / "users.json").read_bytes()
                f.write("users.json", dict(version=1, users=[]))
                try:
                    page = contexts["anonymous"].new_page()
                    page.goto(base + "/admin/setup.php")
                    controls(page, base, "unconfigured secure setup")
                    theme(page, "unconfigured secure setup")
                    fit(page, "unconfigured secure setup", 390)
                    page.close()
                finally:
                    (f.private / "users.json").write_bytes(users)
                history_and_clock(contexts, base)
                check(not errors, "rendered pages have no uncaught JavaScript errors: " + "; ".join(errors))
                browser.close()
        (output / "results.json").write_text(json.dumps(dict(cases=evidence, production=False, delivery=False), indent=2) + "\n")
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


def history_and_clock(contexts, base):
    page = contexts["member"].new_page()
    page.goto(base + "/member/")
    page.locator('.screen-navigation a[href$="/member/timeclock.php"]').click()
    page.wait_for_url("**/member/timeclock.php")
    page.locator("[data-kcmc-back]").click()
    page.wait_for_url("**/member/")
    check(True, "Back returns to the previous same-app screen")
    page.locator('.screen-navigation a[href$="/member/timeclock.php"]').click()
    page.wait_for_url("**/member/timeclock.php")
    page.evaluate("url=>location.assign(url)", base + "/member/notifications.php")
    page.wait_for_url("**/member/notifications.php")
    check(page.evaluate("document.referrer === ''"), "private document keeps no-referrer policy")
    page.locator("[data-kcmc-back]").click()
    page.wait_for_url("**/member/timeclock.php")
    check(True, "private Back uses same-app history despite an empty referrer")
    page.close()
    # New-page history has no previous app entry. Its real fallback is useful.
    page = contexts["member"].new_page()
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
    page.close()
    context = contexts["anonymous"].browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(base + "/member/reset-password.php")
    expected = urljoin(page.url, page.locator("[data-kcmc-back]").get_attribute("href"))
    page.locator("[data-kcmc-back]").click()
    page.wait_for_url(expected)
    check(True, "Back has a working fallback without JavaScript")
    context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=APP)
    parser.add_argument("--output", type=Path, default=ROOT / "test-artifacts/app-theme")
    parser.add_argument("--http-only", action="store_true")
    args = parser.parse_args()
    run(args.app.resolve(), args.output.resolve(), args.http_only)
