#!/usr/bin/env python3
"""Exercise the protected device-display control with real PHP and Chromium.

Only temporary stores and loopback HTTP are used. Chromium creates a real
service-worker notification object; this does not prove a Windows banner was
visible or that a push provider delivered anything. Subscription, permission
prompts, external traffic and subscription API writes are explicitly forbidden.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "KCMC-Connect-Phase6-Recreated"
spec = importlib.util.spec_from_file_location("theme_acceptance", ROOT / "tests/app-theme-browser.py")
theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(theme)
accounts = theme.accounts

# These guards do not mock registration, service-worker activation, display,
# notification enumeration or permission state. Any forbidden operation fails.
SAFETY = """(() => {
    window.kcmcPushAcceptance={permissionPrompts:0,subscriptions:0};
    if('Notification' in window)Notification.requestPermission=()=>{window.kcmcPushAcceptance.permissionPrompts++;throw Error('No permission prompt is authorized in this test')};
    if('PushManager' in window)PushManager.prototype.subscribe=()=>{window.kcmcPushAcceptance.subscriptions++;throw Error('No subscription is authorized in this test')};
})();"""


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print("PASS: " + label, flush=True)


def snapshot(f):
    paths = list(f.private.rglob("*")) + list((f.app / "backups").rglob("*"))
    paths += [f.app / "data/content.json", f.app / "config.php"]
    return {p.relative_to(f.root).as_posix(): p.read_bytes() for p in paths if p.is_file()}


def observe_notifications(page, worker):
    return page.evaluate("""async worker => {
        const registration=await navigator.serviceWorker.getRegistration(worker);
        if(!registration)return [];
        return (await registration.getNotifications({tag:'kcmc-display-test'})).map(note=>({
            title:note.title,body:note.body,tag:note.tag,data:note.data,icon:note.icon,badge:note.badge
        }));
    }""", worker)


def permission_state(page):
    """Capture both real permission APIs without replacing their getters."""
    return page.evaluate("""async () => {
        const result={notification:typeof Notification==='function'?Notification.permission:null,
            origin:location.origin,secureContext:isSecureContext};
        try{result.permissions=(await navigator.permissions.query({name:'notifications'})).state}
        catch(error){result.permissionsError=String(error)}
        return result;
    }""")


def navigation(page, base, actor, width):
    response = page.goto(base + "/")
    check(response.status == 200, actor + " reaches the real public app while signed in")
    fish = page.locator("#siteMenu")
    fish.locator(":scope > summary").focus()
    page.keyboard.press("Enter")
    check(fish.get_attribute("open") is not None, actor + " opens the fish menu with the keyboard")
    administration = fish.get_by_role("link", name="Administration", exact=True)
    if actor == "owner":
        check(administration.count() == 1 and administration.get_attribute("href") == "/app/admin/home.php",
              "Administration shortcut targets the administration hub")
        administration.focus()
        page.keyboard.press("Enter")
        page.wait_for_url("**/admin/home.php")
        groups = page.locator("details.admin-group")
        check(groups.count() == 3 and groups.evaluate_all("nodes=>nodes.every(node=>!node.open)"),
              "the real Administration destination shows three collapsed tool groups")
        theme.controls(page, base, "Administration shortcut")
        theme.fit(page, "Administration shortcut", width)
        response = page.goto(base + "/admin/operations.php")
        check(response.status == 200, "owner can follow through to Operations")
        card = page.locator(".ops-card").filter(has=page.get_by_role("heading", name="Time Cards", exact=True))
        copy = card.inner_text()
        check("completed shifts" in copy and "corrections with a reason" in copy
              and "No submission or approval is needed." in copy and "approve or return" not in copy,
              "Operations describes recorded time and corrections without retired approvals")
    else:
        check(administration.count() == 0, "ordinary member has no Administration shortcut")
        check(fish.get_by_role("link", name="Time clock", exact=True).get_attribute("href") == "/app/member/timeclock.php",
              "member can still find the manual Time clock in the fish menu")


def browser_checks(f, base, output):
    from playwright.sync_api import sync_playwright
    origin = base.rsplit("/", 1)[0]
    worker = base + "/sw.js"
    evidence = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get("KCMC_TEST_CHROMIUM")
            or shutil.which("chromium") or pw.chromium.executable_path,
            headless=True, args=["--no-sandbox"])
        try:
            cases = [("owner", 390, "granted"), ("member", 1365, "granted"),
                     ("owner", 1365, "granted"), ("member", 390, "granted"),
                     ("member", 390, "denied"), ("owner", 1365, "default")]
            for actor, width, permission in cases:
                label = actor + "-" + str(width) + "-" + permission
                context = browser.new_context(viewport=dict(width=width, height=844 if width == 390 else 900),
                    service_workers="allow")
                requests, forbidden, errors = [], [], []

                def network(route):
                    request = route.request
                    if not request.url.startswith(origin + "/"):
                        forbidden.append(dict(url=request.url, method=request.method))
                        route.abort()
                    elif urlparse(request.url).path == "/app/api/push-subscription.php":
                        forbidden.append(dict(url=request.url, method=request.method))
                        route.abort()
                    else:
                        route.continue_()

                context.route("**/*", network)
                context.on("request", lambda request: requests.append(dict(url=request.url, method=request.method)))
                context.add_init_script(SAFETY)
                if permission == "granted":
                    context.grant_permissions(["notifications"], origin=origin)
                elif permission == "denied":
                    # Chromium's grantPermissions command denies permissions
                    # outside this empty allow-list for this exact origin and
                    # isolated context. No browser permission getter is mocked.
                    context.grant_permissions([], origin=origin)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    theme.sign_in(context, base, actor)
                    before = snapshot(f)
                    requests.clear()
                    if permission == "granted":
                        navigation(page, base, actor, width)
                    response = page.goto(base + "/member/notifications.php")
                    check(response.status == 200 and "no-store" in response.headers.get("cache-control", "")
                          and response.headers.get("referrer-policy") == "no-referrer",
                          label + " opens the actual protected notification settings")
                    state = permission_state(page)
                    expected_query = "prompt" if permission == "default" else permission
                    check(state.get("notification") == permission and state.get("permissions") == expected_query,
                          label + " uses the intended native browser permission: " + json.dumps(state, sort_keys=True))
                    page.wait_for_function("document.getElementById('push-status').textContent !== 'Checking this device…'")
                    check(page.evaluate("window.kcmcPushAcceptance.permissionPrompts === 0 && window.kcmcPushAcceptance.subscriptions === 0"),
                          label + " opening settings neither prompts permission nor subscribes")
                    theme.controls(page, base, "device settings " + label)
                    theme.theme(page, "device settings " + label)
                    theme.fit(page, "device settings " + label, width)
                    control = page.locator("details").filter(has=page.locator("#push-display-test"))
                    check(control.count() == 1 and control.get_attribute("open") is None,
                          label + " keeps optional display troubleshooting collapsed")
                    summary = control.locator(":scope > summary")
                    summary.focus()
                    page.keyboard.press("Enter")
                    check(control.get_attribute("open") is not None, label + " opens display troubleshooting with Enter")
                    page.keyboard.press(" ")
                    check(control.get_attribute("open") is None, label + " collapses display troubleshooting with Space")
                    page.keyboard.press("Enter")
                    check(page.locator("#push-display-test").is_visible(), label + " reveals its local test button")
                    calls_before = len(requests)
                    page.locator("#push-display-test").click()
                    if permission == "granted":
                        page.wait_for_function("document.getElementById('push-display-status').textContent.startsWith('Display test requested.')")
                        page.wait_for_function("""async worker => {
                            const registration=await navigator.serviceWorker.getRegistration(worker);
                            return registration?.active?.scriptURL===worker &&
                                (await registration.getNotifications({tag:'kcmc-display-test'})).length===1;
                        }""", arg=worker)
                        notes = observe_notifications(page, worker)
                        check(len(notes) == 1 and notes[0]["title"] == "KCMC display test"
                              and notes[0]["data"] == dict(url=base + "/")
                              and notes[0]["tag"] == "kcmc-display-test",
                              label + " creates a real app-worker notification with the distinct display-test tag")
                        check(notes[0]["body"] == "If you can see this, notifications can appear on this device."
                              and notes[0]["icon"] == base + "/assets/icons/icon-192.png"
                              and notes[0]["badge"] == notes[0]["icon"]
                              and "@example.invalid" not in json.dumps(notes),
                              label + " notification uses public app icons and contains no account payload")
                        check("delivery from KCMC is tested separately" in page.locator("#push-display-status").inner_text(),
                              label + " reports a display request without claiming provider delivery or a visible OS banner")
                    else:
                        page.wait_for_function("document.getElementById('push-display-status').textContent === 'Enable notifications first to allow a display test.'")
                        check(observe_notifications(page, worker) == [], label + " does not create a notification without permission")
                        if permission == "denied":
                            check("permission is blocked" in page.locator("#push-status").inner_text(),
                                  "blocked permission has a clear device-state explanation")
                        check("Do not disturb" in control.inner_text() and "Microsoft Edge" in control.inner_text(),
                              label + " keeps Windows and Edge troubleshooting available")
                    check(page.evaluate("window.kcmcPushAcceptance.permissionPrompts === 0 && window.kcmcPushAcceptance.subscriptions === 0"),
                          label + " display click neither prompts permission nor subscribes")
                    check(not any(item["method"] != "GET" for item in requests[calls_before:]) and not forbidden,
                          label + " local test makes no mutation request, subscription API call or external request")
                    check(snapshot(f) == before, label + " leaves public content, configuration and every private store byte unchanged")
                    check(not errors, label + " has no uncaught page-script error: " + "; ".join(errors))
                    theme.fit(page, "expanded device settings " + label, width)
                    page.screenshot(path=str(output / (label + ".png")), full_page=True)
                    evidence.append(dict(actor=actor, width=width, permission=permission, real_service_worker=True,
                        browser_notification_observed=permission == "granted", permission_prompts=0,
                        subscriptions=0, provider_delivery=False, os_banner_visibility=False, records_changed=False))
                except Exception as error:
                    page.screenshot(path=str(output / ("failure-" + label + ".png")), full_page=True)
                    try:
                        native_permission = permission_state(page)
                    except Exception as diagnostic_error:
                        native_permission = dict(error=str(diagnostic_error))
                    (output / ("failure-" + label + ".json")).write_text(json.dumps(dict(error=str(error),
                        url=page.url, native_permission=native_permission, requests=requests,
                        forbidden=forbidden, script_errors=errors), indent=2) + "\n")
                    raise
                finally:
                    context.close()
        finally:
            browser.close()
    return evidence


def run(app, output):
    output.mkdir(parents=True, exist_ok=True)
    f, server = accounts.Fixture(app), None
    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
        base = "http://127.0.0.1:" + str(port) + "/app"
        env = {key: value for key, value in os.environ.items() if not key.startswith("KCMC_")}
        # A syntactically valid public key exposes the settings controls only.
        # No private key, provider or sending configuration exists in this fixture.
        env.update(KCMC_PRIVATE_DATA_DIR=str(f.private), KCMC_SETUP_KEY="", KCMC_OPERATIONS_OWNER_USER_ID="owner",
            KCMC_INVITATION_MAIL_ENABLED="0", KCMC_PUSH_VAPID_PUBLIC_KEY="A" * 87)
        with (f.root / "server.log").open("w") as log:
            server = subprocess.Popen([accounts.PHP, "-d", "disable_functions=mail,curl_exec,curl_multi_exec",
                "-S", "127.0.0.1:" + str(port), "-t", str(f.root)], env=env, stdout=log, stderr=log)
            for _ in range(60):
                try:
                    urlopen(base + "/member/login.php", timeout=1).close(); break
                except Exception:
                    time.sleep(.1)
            else:
                raise AssertionError("Isolated PHP server did not start")
            evidence = browser_checks(f, base, output)
            (output / "results.json").write_text(json.dumps(dict(cases=evidence, production=False,
                provider_delivery=False, os_banner_visibility=False, records_changed=False), indent=2) + "\n")
    finally:
        if server is not None:
            server.terminate(); server.wait(timeout=10)
        if (f.root / "server.log").is_file():
            shutil.copyfile(f.root / "server.log", output / "php-server.log")
        f.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=APP)
    parser.add_argument("--output", type=Path, default=ROOT / "test-artifacts/push-device")
    args = parser.parse_args()
    run(args.app.resolve(), args.output.resolve())
