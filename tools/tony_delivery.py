#!/usr/bin/env python3
"""Scoped KCMC photo/staff-entry delivery. No password or private-record changes.

Default: inspect and install in the owner's existing cPanel deployment.
--check: stage/lint/check only; no live writes.
--rollback PATH: restore only this run's files, refusing concurrent edits.
Source commits are fixed and fetched into the existing repository, not checked out.
"""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import http.cookiejar

BASE = "2146af219d2fd23136eae1685f91a2a2caec030e"
PHOTOS = "225c564138242f699a1bd31c75b5c78e65268ca7"
PREFIX = "KCMC-Connect-Phase6-Recreated/"
PUBLIC_URL = "https://bobsome1.com/kcmc-connect/"
PHOTO_FILES = ("public-presentation.js", "public-presentation.css", "sw.js")
EDIT_FILES = ("index.php", "care.php", "member/login.php")
TARGETS = PHOTO_FILES + EDIT_FILES
PRESERVE = ("admin/health.php", "admin/audit.php", "admin/timecards.php", "member/timeclock.php", "data/content.json")
CACHE_OLD = "kcmc-connect-v3.0.3-public-only-photos-20261001"
CACHE_NEW = "kcmc-connect-v3.0.3-public-only-tony-staff-20261001"

class Stop(RuntimeError):
    pass

def run(args: list[str], cwd: Path | None = None) -> bytes:
    p = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    if p.returncode:
        # Never echo potentially sensitive program output.
        raise Stop(f"Command failed: {args[0]} {args[1] if len(args)>1 else ''} (exit {p.returncode}).")
    return p.stdout

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def replace_once(text: str, old: str, new: str, name: str) -> str:
    if text.count(old) != 1:
        raise Stop(f"Unexpected {name} source: required anchor was not unique. Nothing installed.")
    return text.replace(old, new, 1)

def transform(base: dict[str, bytes], photos: dict[str, bytes]) -> dict[str, bytes]:
    result = {name: photos[name] for name in PHOTO_FILES}
    sw = photos["sw.js"].decode("utf-8")
    result["sw.js"] = replace_once(sw, CACHE_OLD, CACHE_NEW, "service worker").encode()
    index = base["index.php"].decode("utf-8")
    index = replace_once(index, "$member ? 'member/' : 'member/login.php'", "$member ? 'member/' : 'admin/login.php'", "public staff destination")
    index = replace_once(index, "$member ? 'My account' : 'Sign in'", "$member ? 'My account' : 'Staff Sign In'", "public staff label")
    # Version both public assets so an existing HTTP cache cannot hide the photos.
    import re
    for asset in ("public-presentation.css", "public-presentation.js"):
        pattern = re.escape(asset) + r'\?v=[^"\s]+'
        if len(re.findall(pattern, index)) != 1:
            raise Stop(f"Unexpected asset reference: {asset}.")
        index = re.sub(pattern, asset + "?v=tony-staff-20261001", index)
    result["index.php"] = index.encode()
    care = base["care.php"].decode("utf-8")
    old = '<a class="btn gold" href="<?=kcmc_h(kcmc_url(\'member/login.php\'))?>">Member sign in</a>'
    new = '<a class="btn gold" href="<?=kcmc_h(kcmc_url())?>">Explore KCMC Connect</a>'
    care = replace_once(care, old, new, "public care entry")
    care = replace_once(care, "You do not need an app account to call the church office.", "The public app is free to use. No account is needed to call the church office for prayer or support.", "public care wording")
    result["care.php"] = care.encode()
    login = base["member/login.php"].decode("utf-8")
    for old, new in (
        ("<title>Member Sign In • KCMC Connect</title>", "<title>Staff Sign In • KCMC Connect</title>"),
        (">KCMC MEMBERS</p>", ">KCMC STAFF</p>"),
        ("Prayer and member information stay behind verified sign-in.", "Staff and authorized ministry teams sign in here. Everyone can use the public app for free without an account. Private records remain protected."),
        ("<strong>New pastor administrator or member?</strong>", "<strong>Need staff or authorized ministry access?</strong>"),
    ):
        login = replace_once(login, old, new, "staff sign-in wording")
    # Authentication, CSRF, password verification, rate limiting, roles, invites,
    # recovery and legacy private-account access are deliberately not changed.
    if login.split("?><!doctype html>", 1)[0] != base["member/login.php"].decode().split("?><!doctype html>", 1)[0]:
        raise Stop("Authentication logic changed unexpectedly.")
    result["member/login.php"] = login.encode()
    return result

def read_git(repo: Path, ref: str, name: str) -> bytes:
    return run(["git", "show", f"{ref}:{PREFIX}{name}"], cwd=repo)

def sources(repo: Path, fetch: bool = True) -> tuple[dict[str, bytes], dict[str, bytes], bytes]:
    remote = run(["git", "remote", "get-url", "origin"], cwd=repo).decode().strip()
    allowed = {"https://github.com/bobhay75/Kcmc-connect.git", "https://github.com/bobhay75/Kcmc-connect", "git@github.com:bobhay75/Kcmc-connect.git"}
    if remote not in allowed:
        raise Stop("Repository origin does not match the approved KCMC repository.")
    if fetch:
        run(["git", "fetch", "--no-tags", "origin", PHOTOS], cwd=repo)
    base = {name: read_git(repo, BASE, name) for name in TARGETS}
    photos = {name: read_git(repo, PHOTOS, name) for name in PHOTO_FILES}
    dependency = read_git(repo, BASE, "lib/public-presentation.php")
    return base, photos, dependency

def safe_path(root: Path, relative: str, must_exist: bool = True) -> Path:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise Stop("Unsafe relative path.")
    path = root / relative
    for part in [root, *root.parents]:
        if part.is_symlink():
            raise Stop("Symbolic links are not allowed in the installation path.")
    cursor = root
    for part in Path(relative).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise Stop(f"Symbolic link found: {relative}.")
    if must_exist and not path.is_file():
        raise Stop(f"Required file is missing: {relative}. Install the reviewed cleanup first.")
    if path.exists() and not stat.S_ISREG(path.stat().st_mode):
        raise Stop(f"Not a regular file: {relative}.")
    return path

def plan(root: Path, base: dict[str, bytes], photos: dict[str, bytes], dependency: bytes) -> tuple[dict[str, bytes], dict[str, bytes]]:
    if safe_path(root, "lib/public-presentation.php").read_bytes() != dependency:
        raise Stop("Live cleanup dependency differs from reviewed main. No live files changed.")
    wanted = transform(base, photos)
    before: dict[str, bytes] = {}
    changes: dict[str, bytes] = {}
    for name, content in wanted.items():
        path = safe_path(root, name)
        current = path.read_bytes()
        allowed = [base[name], content]
        if name in photos:
            allowed.append(photos[name])
        if current not in allowed:
            raise Stop(f"Unreviewed live change in {name}. It was preserved; nothing installed.")
        if current != content:
            before[name] = current
            changes[name] = content
    return before, changes

def tracked_hashes(root: Path) -> dict[str, str | None]:
    return {name: digest(safe_path(root, name).read_bytes()) if (root / name).exists() else None for name in PRESERVE}

def atomic(path: Path, data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".kcmc-delivery-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def lint(stage: Path, changes: dict[str, bytes]) -> None:
    for name, content in changes.items():
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if name.endswith(".php"):
            run(["php", "-l", str(path)])
        elif name.endswith(".js") and shutil.which("node"):
            run(["node", "--check", str(path)])

def restore(backup: Path, expected_root: Path | None = None) -> int:
    if backup.is_symlink() or not backup.is_dir():
        raise Stop("Invalid rollback directory.")
    manifest_path = backup / "manifest.json"
    if manifest_path.is_symlink():
        raise Stop("Invalid rollback manifest.")
    manifest = json.loads(manifest_path.read_text())
    root = Path(manifest["root"])
    if expected_root is not None and root != expected_root:
        raise Stop("Rollback target does not match the KCMC deployment.")
    pending = []
    for name, row in manifest["files"].items():
        if name not in TARGETS:
            raise Stop("Rollback manifest contains an unapproved path.")
        current = safe_path(root, name).read_bytes()
        saved = safe_path(backup / "before", name).read_bytes()
        if digest(saved) != row["old_sha256"]:
            raise Stop("Backup integrity check failed.")
        if digest(current) == row["old_sha256"]:
            continue
        if digest(current) != row["new_sha256"]:
            raise Stop(f"Rollback stopped: {name} changed after installation. Nothing restored.")
        pending.append((name, saved, row["mode"]))
    for name, saved, mode in pending:
        atomic(safe_path(root, name), saved, mode)
    return len(pending)

def web_check() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    checks = (("", "Staff Sign In"), ("care.php", "No account is needed"), ("public-presentation.js", "data-family-welcome"), ("member/login.php", "Staff Sign In"))
    for suffix, expected in checks:
        req = urllib.request.Request(PUBLIC_URL + suffix + "?tony_verify=" + stamp, headers={"Cache-Control": "no-cache", "User-Agent": "KCMC-owner-delivery-check/1.0"})
        with opener.open(req, timeout=20) as response:
            if response.status != 200:
                raise Stop(f"Live HTTP check failed: {suffix or 'homepage'}.")
            text = response.read(2_000_000).decode("utf-8", "replace")
            if expected not in text:
                raise Stop(f"Live response has not accepted the update: {suffix or 'homepage'}.")
            if suffix == "member/login.php":
                if 'name="csrf"' not in text or 'autocomplete="current-password"' not in text:
                    raise Stop("Live staff form did not render correctly.")
                if "no-store" not in response.headers.get("Cache-Control", ""):
                    raise Stop("Live sign-in page is not marked no-store.")
    if not any(cookie.name == "KCMC_CONNECT_V3" and cookie.secure for cookie in jar):
        # Session names may be legitimately configured differently: do not assume.
        if not any(cookie.secure and "/kcmc-connect/" in cookie.path for cookie in jar):
            raise Stop("No secure KCMC session cookie was observed on the live sign-in form.")

def install(root: Path, backup_base: Path, before: dict[str, bytes], changes: dict[str, bytes], verify_web: bool) -> Path | None:
    if not changes:
        print("Already installed. No live files changed.")
        return None
    protected = tracked_hashes(root)
    backup = Path(tempfile.mkdtemp(prefix="delivery-", dir=backup_base))
    os.chmod(backup, 0o700)
    (backup / "before").mkdir(mode=0o700)
    manifest = {"version": 1, "root": str(root), "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "files": {}}
    for name, old in before.items():
        path = safe_path(root, name)
        if path.read_bytes() != old:
            raise Stop(f"Concurrent change in {name}; nothing installed.")
        saved = backup / "before" / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(old)
        os.chmod(saved, 0o600)
        manifest["files"][name] = {"old_sha256": digest(old), "new_sha256": digest(changes[name]), "mode": stat.S_IMODE(path.stat().st_mode)}
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="lint-", dir=backup_base) as stage:
        lint(Path(stage), changes)
    try:
        # Complete preflight precedes all writes. Recheck every file at the commit boundary.
        for name, old in before.items():
            if safe_path(root, name).read_bytes() != old:
                raise Stop(f"Concurrent change in {name} before installation.")
        for name, content in changes.items():
            path = safe_path(root, name)
            if path.read_bytes() != before[name]:
                raise Stop(f"Concurrent change in {name} during installation.")
            atomic(path, content, manifest["files"][name]["mode"])
        if tracked_hashes(root) != protected:
            raise Stop("A preserved file changed concurrently. Review the deployment.")
        if verify_web:
            web_check()
    except Exception:
        try:
            restored = restore(backup, root)
            print(f"Delivery failed; restored {restored} changed code files.", file=sys.stderr)
        except Exception:
            print(f"Automatic rollback needs review. Private backup: {backup}", file=sys.stderr)
        raise
    print(f"Installed {len(changes)} scoped code files. Private backup: {backup}")
    print("Existing private records, content.json and four readability hotfix files were not edited.")
    print("Staff form is relabeled; authentication, passwords, account roles and private access remain unchanged.")
    print("Real staff sign-in still requires a successful credential test; this script does not reset passwords.")
    return backup

def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rollback", type=Path)
    parser.add_argument("--fixture-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--repo", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    home = Path.home()
    root = home / "public_html/kcmc-connect"
    repo = home / "repositories/Kcmc-connect-live"
    fixture = args.fixture_root is not None
    if fixture:
        if os.environ.get("KCMC_DELIVERY_TEST") != "1":
            raise Stop("Fixture mode requires the explicit test environment.")
        root, repo = args.fixture_root.absolute(), args.repo.absolute()
    backup_base = (root.parent / ".tony-test-backups") if fixture else home / ".kcmc-tony-backups"
    for path in (root, repo, backup_base):
        if path.is_symlink():
            raise Stop("Symbolic-link root, repository or backup location is not supported.")
    if not root.is_dir() or not repo.is_dir():
        raise Stop("Expected KCMC deployment or repository directory is missing.")
    if not shutil.which("php") or not shutil.which("git"):
        raise Stop("PHP CLI and git are required. Nothing changed.")
    backup_base.mkdir(mode=0o700, exist_ok=True)
    os.chmod(backup_base, 0o700)
    lock_path = backup_base / ".lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            backup = args.rollback.absolute()
            if backup.parent != backup_base:
                raise Stop("Rollback must use a backup from this delivery's private backup folder.")
            print(f"Restored {restore(backup, root)} code files.")
            return 0
        base, photo, dependency = sources(repo, fetch=not fixture)
        before, changes = plan(root, base, photo, dependency)
        print("Reviewed cleanup: " + BASE)
        print("Reviewed photos: " + PHOTOS)
        print("Planned files: " + (", ".join(changes) or "none"))
        if args.check:
            with tempfile.TemporaryDirectory(prefix="check-", dir=backup_base) as stage:
                lint(Path(stage), changes)
            print("Preflight and syntax checks passed. No live files changed.")
            return 0
        backup = install(root, backup_base, before, changes, verify_web=not fixture)
        if backup:
            import shlex
            print("Rollback: python3 " + shlex.quote(str(Path(__file__).absolute())) + " --rollback " + shlex.quote(str(backup)))
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Stop, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("STOP: " + str(exc), file=sys.stderr)
        sys.exit(1)
