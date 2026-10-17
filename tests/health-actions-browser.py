#!/usr/bin/env python3
"""Owner health controls on real PHP routes and native browser disclosures.

Only temporary app copies, synthetic accounts and loopback requests are used.
The route checks run without Playwright; the browser adds keyboard, no-script,
phone/desktop layout and screenshots of the actual protected screen.
"""
from __future__ import annotations

import argparse
from collections import Counter
import http.cookiejar
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
import urllib.error
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, urlopen

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "KCMC-Connect-Phase6-Recreated"
spec = importlib.util.spec_from_file_location("theme_acceptance", ROOT / "tests/app-theme-browser.py")
theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(theme)
accounts = theme.accounts

# These destinations are real tools, not GET shortcuts for a mutation. The four
# hosting-only checks intentionally disclose guidance without a pretend repair.
ACTIONS = {
    "php": [], "https": [], "content": ["/app/admin/"], "private_storage": [],
    "backups": ["/app/admin/backup.php", "/app/admin/restore.php"], "setup_key": [],
    "invitation_mail": ["/app/admin/users.php"], "push_delivery": ["/app/admin/push.php"],
    "pwa": ["/app/", "/app/member/notifications.php"], "accounts": ["/app/admin/users.php"],
    "pending_invites": ["/app/admin/users.php"],
    "push_subscriptions": ["/app/admin/push.php", "/app/member/notifications.php"],
    "audit": ["/app/admin/audit.php"],
}
SECRETS = ["SECRET OTHER PRAYER", "SECRET PENDING CARE", "SECRET_CONTACT_BODY",
           "SECRET_INVITE_TOKEN_HASH", "secret-invite@example.invalid", "SECRET_PUSH_ENDPOINT",
           "SECRET_PUSH_AUTH", "SECRET_PUSH_P256DH"]


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print("PASS: " + label, flush=True)


class HealthMarkup(HTMLParser):
    """Read rendered destinations and diagnostic rows independently of PHP code."""
    def __init__(self, html):
        super().__init__()
        self.rows, self.links, self.forms = {}, [], 0
        self.row = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details" and "health-check" in attrs.get("class", "").split():
            check(self.row is None, "health rows are independent native disclosures")
            identifier = attrs.get("data-check")
            check(identifier not in self.rows, "health check identifiers are unique")
            self.row = dict(id=identifier, status=next((s for s in ["pass", "warn", "fail"]
                if s in attrs.get("class", "").split()), None), links=[], text=[], summaries=0,
                closed="open" not in attrs)
            self.rows[identifier] = self.row
        if tag == "summary" and self.row is not None:
            self.row["summaries"] += 1
        if tag == "a":
            self.links.append(attrs)
            if self.row is not None:
                self.row["links"].append(attrs.get("href"))
        if tag == "form":
            self.forms += 1

    def handle_data(self, value):
        if self.row is not None:
            self.row["text"].append(value)

    def handle_endtag(self, tag):
        if tag == "details" and self.row is not None:
            self.row = None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def request(client, url, data=None):
    try:
        response = client.open(url, urlencode(data).encode() if data is not None else None, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    status, headers, body = response.code, response.headers, response.read().decode("utf-8")
    check(not re.search(r"(?i)Warning:|Fatal error|headers already sent|Deprecated:", body),
          "route has no PHP runtime warning: " + urlparse(url).path)
    return status, headers, body


def client(base, uid=None):
    result = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())
    if uid is not None:
        status, _, body = request(result, base + "/member/login.php")
        check(status == 200, "synthetic sign-in form is reachable")
        token = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
        status, _, _ = request(result, base + "/member/login.php", dict(csrf=token,
            email=uid + "@example.invalid", password="Synthetic-Fixture-2031!"))
        check(status == 302, "real session established for " + uid)
    return result


def snapshot(f):
    paths = list(f.private.rglob("*")) + list((f.app / "backups").rglob("*"))
    paths += [f.app / "data/content.json", f.app / "config.php"]
    return {p.relative_to(f.root).as_posix(): p.read_bytes() for p in paths if p.is_file()}


def health_page(html, expected_ids=None):
    parsed = HealthMarkup(html)
    if expected_ids is not None:
        check(set(parsed.rows) == set(expected_ids), "rendered health checks match the requested status")
    check(parsed.forms == 0, "health screen offers no form that sends, restores or changes records")
    check(not any(secret in html for secret in SECRETS), "health output omits synthetic private payloads")
    for identifier, row in parsed.rows.items():
        check(row["status"] in ["pass", "warn", "fail"] and row["closed"] and row["summaries"] == 1,
              identifier + " is a closed disclosure with a finding and status")
        check(row["links"] == ACTIONS[identifier], identifier + " opens only its verified work area")
        if not row["links"]:
            check("hosting" in " ".join(row["text"]).lower(), identifier + " gives hosting guidance")
    return parsed


def http_checks(f, base):
    anonymous = client(base)
    status, headers, body = request(anonymous, base + "/admin/health.php")
    check(status == 302 and "/member/login.php" in headers.get("Location", "") and "production readiness" not in body,
          "anonymous visitor cannot read diagnostics")
    clients = {uid: client(base, uid) for uid in ["owner", "pastor", "recovery", "member", "prayer"]}
    before = snapshot(f)
    for uid in ["pastor", "recovery", "member", "prayer"]:
        status, headers, body = request(clients[uid], base + "/admin/health.php?status=fail")
        check(status == 403 and "no-store" in headers.get("Cache-Control", "") and "production readiness" not in body,
              uid + " cannot bypass the configured owner boundary with a filter")
    owner = clients["owner"]
    status, headers, body = request(owner, base + "/admin/health.php")
    check(status == 200 and "text/html" in headers.get("Content-Type", ""), "owner receives the real health screen")
    check("no-store" in headers.get("Cache-Control", "") and headers.get("Referrer-Policy") == "no-referrer"
          and "noindex" in headers.get("X-Robots-Tag", ""), "health keeps private transport and indexing headers")
    parsed = health_page(body, ACTIONS)
    counts = Counter(row["status"] for row in parsed.rows.values())
    check(all(counts[s] > 0 for s in ["pass", "warn", "fail"]), "isolated HTTP fixture exercises all three status groups")
    destinations = {link.get("href") for link in parsed.links}
    for selected in ["pass", "warn", "fail"]:
        href = "/app/admin/health.php?status=" + selected + "#health-checks"
        check(href in destinations, selected + " summary is a real filter link")
        status, _, filtered = request(owner, urljoin(base + "/", href))
        check(status == 200, selected + " filter is a usable GET route")
        result = health_page(filtered, [key for key, row in parsed.rows.items() if row["status"] == selected])
        check('aria-current="true"' in filtered and "/app/admin/health.php#health-checks" in filtered,
              selected + " shows the active filter and a way back to all checks")
        for other in ["pass", "warn", "fail"]:
            # A filtered list must not replace the full-snapshot overview totals.
            pattern = r'href="/app/admin/health.php\?status=' + other + r'#health-checks"[^>]*>.*?<strong>(\d+)</strong>'
            match = re.search(pattern, filtered, re.S)
            check(match is not None and int(match.group(1)) == counts[other], "overview totals remain global under " + selected)
    for query in ["status=unknown", "status%5B%5D=fail", "status%5Bnested%5D=pass", "status=%3Cscript%3Ealert(1)%3C%2Fscript%3E"]:
        status, _, invalid = request(owner, base + "/admin/health.php?" + query)
        check(status == 200 and "<script>alert(1)</script>" not in invalid, "invalid and non-string filters safely fall back to all checks")
        health_page(invalid, ACTIONS)
    for href in sorted({href for row in parsed.rows.values() for href in row["links"]}):
        status, headers, body = request(owner, urljoin(base + "/", href))
        check(status == 200, "health action reaches a permitted real destination: " + href)
        if href.endswith("backup.php"):
            check("application/json" in headers.get("Content-Type", "") and isinstance(json.loads(body), dict),
                  "backup action downloads public JSON without executing recovery")
    check(snapshot(f) == before, "health views, filters and action GETs preserve every private, public-content and backup byte")
    # CLI route metadata marks this isolated request as HTTPS. With writable
    # backup storage, the actual health engine now has no failures. Exercise the
    # zero-result state without replacing or stubbing the diagnostic function.
    before = snapshot(f)
    status, empty = f.route("admin/health.php", "owner", query={"status": "fail"})
    check(status == 200, "zero-failure route remains a successful read")
    health_page(empty, [])
    check("No checks are currently marked as Action needed." in empty and "Show all checks" in empty,
          "zero-result filter explains the result and offers all checks")
    check(snapshot(f) == before, "zero-result health route is read-only")


def browser_checks(f, base, output):
    from playwright.sync_api import sync_playwright
    origin = base.rsplit("/", 1)[0]
    evidence = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get("KCMC_TEST_CHROMIUM") or shutil.which("chromium") or pw.chromium.executable_path,
                                     headless=True, args=["--no-sandbox"])
        try:
            for width, height, javascript in [(390, 844, True), (1365, 900, True), (390, 844, False)]:
                context = browser.new_context(viewport=dict(width=width, height=height), service_workers="block", java_script_enabled=javascript)
                context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/") else route.abort())
                theme.sign_in(context, base, "owner")
                before = snapshot(f)
                page = context.new_page()
                label = str(width) + ("-script" if javascript else "-native")
                try:
                    response = page.goto(base + "/admin/health.php")
                    check(response.status == 200, label + " owner screen loads")
                    theme.controls(page, base, "health " + label)
                    theme.theme(page, "health " + label)
                    theme.fit(page, "health " + label, width)
                    rows = page.locator("details.health-check")
                    check(rows.count() == 13 and rows.evaluate_all("nodes=>nodes.every(el=>!el.open)"),
                          label + " keeps all thirteen diagnostic action menus closed")
                    for identifier in ACTIONS:
                        row = page.locator('details[data-check="' + identifier + '"]')
                        summary = row.locator(":scope > summary")
                        check(summary.is_visible(), label + " exposes a clear finding control for " + identifier)
                        summary.focus()
                        page.keyboard.press("Enter")
                        check(row.get_attribute("open") is not None and row.locator(".health-check-body").is_visible(),
                              identifier + " opens with Enter " + label)
                        if ACTIONS[identifier]:
                            check(all(link.is_visible() for link in row.get_by_role("link").all()), identifier + " reveals its work-area links")
                        theme.fit(page, "expanded " + identifier + " " + label, width)
                        page.keyboard.press(" ")
                        check(row.get_attribute("open") is None, identifier + " closes with Space " + label)
                    page.evaluate("window.scrollTo(0,0)")
                    page.screenshot(path=str(output / ("health-" + label + ".png")), full_page=True)
                    overview = page.get_by_role("navigation", name="Health overview", exact=True)
                    check(overview.get_by_role("link").count() == 4, "all four overview cards are active links " + label)
                    active = overview.get_by_role("link").filter(has_text="Active accounts")
                    check(active.get_attribute("href") == "/app/admin/users.php" and active.locator("strong").inner_text() == "5",
                          "active-account card opens Member access with the actual total " + label)
                    counts = page.locator("section").filter(has=page.get_by_role("heading", name="Access and notification state", exact=True))
                    for name, destination, total in [("Pending invitations", "/app/admin/users.php", "1"),
                            ("Push subscriptions", "/app/admin/push.php", "1"), ("Disabled accounts", "/app/admin/users.php", "1")]:
                        card = counts.locator("a.health-stat-link").filter(has_text=name)
                        check(card.count() == 1 and card.get_attribute("href") == destination and card.locator("strong").inner_text() == total,
                              name + " count opens its actual work area " + label)
                    check(counts.locator("time[datetime]").count() == 1 and counts.locator("time").locator("xpath=ancestor::a").count() == 0,
                          "generated timestamp remains informational " + label)
                    overview.get_by_role("link").filter(has_text="Action needed").click()
                    page.wait_for_url("**/admin/health.php?status=fail#health-checks")
                    check(page.locator("details.health-check").evaluate_all("nodes=>nodes.length>0&&nodes.every(el=>el.classList.contains('fail'))"),
                          "Action needed card filters real checks " + label)
                    check(overview.locator('a[aria-current="true"]').count() == 1, "active status is identified " + label)
                    theme.fit(page, "filtered health " + label, width)
                    page.screenshot(path=str(output / ("health-fail-" + label + ".png")), full_page=True)
                    show_all = page.get_by_role("link", name="Show all checks", exact=True)
                    if javascript:
                        show_all.click()
                    else:
                        # Exercise native anchor keyboard activation as well as
                        # the pointer journeys above. It does not depend on
                        # Playwright's injected animation-frame stability check
                        # after a full-page capture of a smooth-scrolling page.
                        show_all.focus()
                        page.keyboard.press("Enter")
                    page.wait_for_url("**/admin/health.php#health-checks")
                    check(page.locator("details.health-check").count() == 13, "Show all restores every check " + label)
                    check(snapshot(f) == before, "native menu and filter interactions leave records unchanged " + label)
                    evidence.append(dict(width=width, javascript=javascript, checks=13, keyboard=True, read_only=True))
                except Exception as error:
                    page.screenshot(path=str(output / ("failure-" + label + ".png")), full_page=True)
                    (output / ("failure-" + label + ".json")).write_text(json.dumps(dict(error=str(error), url=page.url), indent=2) + "\n")
                    raise
                finally:
                    context.close()
        finally:
            browser.close()
    return evidence


def run(app, output, http_only=False):
    output.mkdir(parents=True, exist_ok=True)
    f, server = accounts.Fixture(app), None
    try:
        (f.app / "backups").mkdir(mode=0o750, exist_ok=True)
        f.write("invites.json", dict(version=1, invites=[dict(id="synthetic-invite", role="member", used_at=None,
            expires_at="2099-01-01T00:00:00Z", email="secret-invite@example.invalid", token_hash="SECRET_INVITE_TOKEN_HASH")]))
        f.write("push-subscriptions.json", dict(version=1, subscriptions=[dict(active=True, user_id="owner",
            endpoint="https://push.example.invalid/SECRET_PUSH_ENDPOINT", keys=dict(auth="SECRET_PUSH_AUTH", p256dh="SECRET_PUSH_P256DH"))]))
        row = dict(id="synthetic-private-contact", name="Secret Synthetic Person", email="secret-contact@example.invalid",
            message="SECRET_CONTACT_BODY", status="new", submitted_at="2026-10-01T12:00:00Z")
        f.write("connection-intake.json", dict(version=1, submissions=[dict(row, kind="visit")]))
        f.write("event-rsvps.json", dict(version=1, rsvps=[dict(row, event="Synthetic event", event_date="2026-10-31")]))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
        base = "http://127.0.0.1:" + str(port) + "/app"
        env = {k: v for k, v in os.environ.items() if not k.startswith("KCMC_")}
        env.update(KCMC_PRIVATE_DATA_DIR=str(f.private), KCMC_SETUP_KEY="", KCMC_OPERATIONS_OWNER_USER_ID="owner",
                   KCMC_INVITATION_MAIL_ENABLED="0")
        with (f.root / "server.log").open("w") as log:
            server = subprocess.Popen([accounts.PHP, "-d", "disable_functions=mail", "-S", "127.0.0.1:" + str(port),
                                       "-t", str(f.root)], env=env, stdout=log, stderr=log)
            for _ in range(60):
                try:
                    urlopen(base + "/member/login.php", timeout=1).close(); break
                except Exception:
                    time.sleep(.1)
            else:
                raise AssertionError("Isolated PHP server did not start")
            http_checks(f, base)
            evidence = [] if http_only else browser_checks(f, base, output)
            (output / "results.json").write_text(json.dumps(dict(http=True, browser=evidence,
                production=False, delivery=False, private_records_changed=False), indent=2) + "\n")
    finally:
        if server is not None:
            server.terminate(); server.wait(timeout=10)
        f.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=APP)
    parser.add_argument("--output", type=Path, default=ROOT / "test-artifacts/health-actions")
    parser.add_argument("--http-only", action="store_true")
    args = parser.parse_args()
    run(args.app.resolve(), args.output.resolve(), args.http_only)
