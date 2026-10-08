#!/usr/bin/env python3
"""Insert exactly one approved event, preserving every existing content byte.

Python 3.6 / Linux. Default: check only. --apply uses the fixed observed host
SHA and shared PHP content.json.lock, a private exact backup and atomic replace.
Close Publishing Desk tabs and finish/drain saves before use; keep publishing
idle through the public-feed verification. An old in-flight PHP save can still
overwrite content after the shared lock is released.
No app bootstrap, bulletin, statistics, recurrence, metadata or private-store
updates. --verify-source FILE is a read-only CI check of the canonical event.
"""
from __future__ import print_function

import argparse
import datetime
import decimal
import errno
import fcntl
import hashlib
import json
import os
import re
import signal
import stat
import sys
import unicodedata

HOST_FILE = "/home/bobsome1/public_html/kcmc-connect/data/content.json"
BACKUP_DIR = "/home/bobsome1/kcmc-content-backups"
PUBLIC_ROOT = "/home/bobsome1/public_html"
EXPECTED_HOST_SHA256 = "dc3e671177f2d92096da7c0f5e174883492513261649508921a5ce9875ebe5a6"
OBSERVED_AT_UTC = "2026-10-08T02:51:15Z"
SOURCE_COMMIT = "61c70f590735522adbfd6be02dab6888924a54fd"
SOURCE_PATH = "KCMC-Connect-Phase6-Recreated/data/content.json"
SOURCE_BLOB_SHA1 = "e7eb008c163a524f036d52b5e8e6203f3c1a60d9"
EXPECTED_CANDIDATE_SHA256 = "db8f03453cc87791029e486192268cd265d3d120e9314d43fdca40b0b412d98b"
CANDIDATE = {
    "id": "hope-keepers-20261013",
    "title": "Hope Keepers — First Gathering",
    "date": "2026-10-13",
    "time": "1:00 PM",
    "location": "KCMC Fellowship Hall",
    "description": "A welcoming community for widows to share friendship, encouragement and hope. Contact the church office for more information.",
    "status": "published",
    "expires_at": "2026-10-14T00:00:00-05:00",
}
UTC = datetime.timezone.utc
EXPIRES_AT = datetime.datetime(2026, 10, 14, 5, 0, 0, tzinfo=UTC)
MAX_BYTES = 16 * 1024 * 1024
JSON_WHITESPACE = " \t\r\n"


class Refusal(Exception):
    pass


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _candidate_bytes():
    raw = json.dumps(CANDIDATE, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    if _hash(raw) != EXPECTED_CANDIDATE_SHA256:
        raise Refusal("candidate_integrity_failed")
    return raw


def _utc_now():
    return datetime.datetime.now(UTC)


def _signal_interrupt(signum, frame):
    raise KeyboardInterrupt()


def _check_expiration(clock):
    now = clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise Refusal("clock_timezone_required")
    if now.astimezone(UTC) >= EXPIRES_AT:
        raise Refusal("expired_candidate")
    return now


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Refusal("duplicate_json_keys")
        result[key] = value
    return result


def _bad_constant(value):
    raise Refusal("invalid_json")


def _decoder():
    return json.JSONDecoder(object_pairs_hook=_pairs,
                            parse_constant=_bad_constant, parse_float=decimal.Decimal)


def _decode(raw):
    try:
        text = raw.decode("utf-8")
        data = _decoder().decode(text)
    except (ValueError, UnicodeDecodeError, RecursionError, decimal.InvalidOperation):
        raise Refusal("invalid_json")
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise Refusal("invalid_event_container")
    identifiers = set()
    for event in data["events"]:
        if not isinstance(event, dict):
            raise Refusal("invalid_event_record")
        identifier = event.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise Refusal("invalid_event_id")
        if identifier.strip() in identifiers:
            raise Refusal("duplicate_event_ids")
        identifiers.add(identifier.strip())
    return text, data


def _title(value):
    if not isinstance(value, str):
        return None
    value = unicodedata.normalize("NFKC", value).casefold()
    value = " ".join(re.sub(r"[-\u2010-\u2015\u2212]", " ", value).split())
    return "hope keepers first gathering" if value == "hope keepers" else value


def _date(value):
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", value.strip()):
        return None
    try:
        return datetime.datetime.strptime(value.strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _time(value):
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).casefold())
    match = re.match(r"^(\d{1,2})(?::(\d{2}))?(am|pm)$", value)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        if 1 <= hour <= 12 and 0 <= minute < 60:
            return (hour % 12 + (12 if match.group(3) == "pm" else 0), minute)
    match = re.match(r"^(\d{1,2}):(\d{2})$", value)
    if match and 0 <= int(match.group(1)) < 24 and 0 <= int(match.group(2)) < 60:
        return (int(match.group(1)), int(match.group(2)))
    return None


def _signature(event):
    return (_title(event.get("title")), _date(event.get("date")), _time(event.get("time")))


def _verdict(data):
    matches = [event for event in data["events"] if event["id"].strip() == CANDIDATE["id"]]
    duplicates = [event for event in data["events"]
                  if event["id"].strip() != CANDIDATE["id"] and _signature(event) == _signature(CANDIDATE)]
    if matches:
        if matches[0] != CANDIDATE:
            return "same_id_conflict"
        return "possible_duplicate" if duplicates else "already_same"
    return "possible_duplicate" if duplicates else "missing"


def _skip(text, index):
    while index < len(text) and text[index] in JSON_WHITESPACE:
        index += 1
    return index


def _insert_bytes(raw, text, data):
    """Use decoded top-level value spans, then map the offset back to UTF-8."""
    decoder = _decoder()
    index = _skip(text, 0) + 1  # _decode already requires a valid top-level object.
    while True:
        index = _skip(text, index)
        if text[index] == "}":
            raise Refusal("events_span_missing")
        key, index = decoder.raw_decode(text, index)
        index = _skip(text, index)
        if text[index] != ":":
            raise Refusal("events_span_invalid")
        start = _skip(text, index + 1)
        value, end = decoder.raw_decode(text, start)
        if key == "events":
            if text[start] != "[" or text[end - 1] != "]":
                raise Refusal("events_span_invalid")
            insertion = end - 1
            while insertion > start + 1 and text[insertion - 1] in JSON_WHITESPACE:
                insertion -= 1
            byte_offset = len(text[:insertion].encode("utf-8"))
            token = (b"," if data["events"] else b"") + _candidate_bytes()
            patched = raw[:byte_offset] + token + raw[byte_offset:]
            _, actual = _decode(patched)
            expected = dict(data)
            expected["events"] = data["events"] + [dict(CANDIDATE)]
            if actual != expected:
                raise Refusal("preservation_check_failed")
            # The original bytes are a literal prefix/suffix, not reserialized.
            if patched[:byte_offset] != raw[:byte_offset] or patched[byte_offset + len(token):] != raw[byte_offset:]:
                raise Refusal("preservation_check_failed")
            return patched
        index = _skip(text, end)
        if text[index] == ",":
            index += 1
        elif text[index] == "}":
            raise Refusal("events_span_missing")
        else:
            raise Refusal("events_span_invalid")


def _open_directory(path):
    if not os.path.isabs(path) or os.path.normpath(path) != path:
        raise Refusal("unsafe_directory_path")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise Refusal("nofollow_unavailable")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(os.path.sep, flags)
    try:
        for part in path.split(os.path.sep)[1:]:
            if not part:
                continue
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _parent_current(path, parent_fd):
    check = _open_directory(os.path.dirname(path))
    try:
        first, second = os.fstat(parent_fd), os.fstat(check)
        if (first.st_dev, first.st_ino) != (second.st_dev, second.st_ino):
            raise Refusal("host_parent_changed")
    finally:
        os.close(check)


def _fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_nlink, info.st_size,
            info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode),
            info.st_mtime_ns, info.st_ctime_ns)


def _safe_info(info):
    if not stat.S_ISREG(info.st_mode):
        raise Refusal("non_regular_file")
    if info.st_nlink != 1:
        raise Refusal("hardlinked_file")
    if info.st_uid != os.geteuid():
        raise Refusal("unexpected_file_owner")
    if stat.S_IMODE(info.st_mode) & 0o022:
        raise Refusal("writable_by_other_users")
    if info.st_size > MAX_BYTES:
        raise Refusal("file_too_large")


def _read_fd(fd):
    before = os.fstat(fd)
    _safe_info(before)
    os.lseek(fd, 0, os.SEEK_SET)
    chunks, total = [], 0
    while True:
        block = os.read(fd, min(65536, MAX_BYTES + 1 - total))
        if not block:
            break
        chunks.append(block)
        total += len(block)
        if total > MAX_BYTES:
            raise Refusal("file_too_large")
    after = os.fstat(fd)
    if _fingerprint(before) != _fingerprint(after):
        raise Refusal("file_changed_during_read")
    return b"".join(chunks), before


def _open_content(parent_fd, filename):
    info = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
    if stat.S_ISLNK(info.st_mode):
        raise Refusal("symlink_refused")
    _safe_info(info)
    fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    try:
        if _fingerprint(info) != _fingerprint(os.fstat(fd)):
            raise Refusal("file_changed_during_open")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _lock_content(parent_fd, filename):
    lockname = filename + ".lock"
    created = False
    before_open = None
    try:
        fd = os.open(lockname, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent_fd)
        created = True
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise
        info = os.stat(lockname, dir_fd=parent_fd, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            raise Refusal("symlink_lock_refused")
        _safe_info(info)
        before_open = info
        fd = os.open(lockname, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    try:
        info = os.fstat(fd)
        _safe_info(info)
        if before_open is not None and _fingerprint(info) != _fingerprint(before_open):
            raise Refusal("lock_changed_during_open")
        if created:
            os.fchmod(fd, 0o600)
            os.fsync(fd)
            os.fsync(parent_fd)
            info = os.fstat(fd)
        path_info = os.stat(lockname, dir_fd=parent_fd, follow_symlinks=False)
        if _fingerprint(info) != _fingerprint(path_info):
            raise Refusal("lock_path_changed")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN):
                raise Refusal("content_lock_busy")
            raise
        return fd, lockname, os.fstat(fd)
    except BaseException:
        os.close(fd)
        raise


def _lock_current(parent_fd, lockname, lock_fd, expected):
    current = os.stat(lockname, dir_fd=parent_fd, follow_symlinks=False)
    if (_fingerprint(current) != _fingerprint(expected) or
            _fingerprint(os.fstat(lock_fd)) != _fingerprint(expected)):
        raise Refusal("lock_path_changed")


def _backup_directory(path):
    parent = _open_directory(os.path.dirname(path))
    try:
        try:
            os.mkdir(os.path.basename(path), 0o700, dir_fd=parent)
            os.fsync(parent)
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise
        fd = os.open(os.path.basename(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                     dir_fd=parent)
        try:
            info = os.fstat(fd)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise Refusal("backup_directory_not_private")
            return fd
        except BaseException:
            os.close(fd)
            raise
    finally:
        os.close(parent)


def _write_all(fd, raw):
    offset = 0
    while offset < len(raw):
        written = os.write(fd, raw[offset:])
        if written <= 0:
            raise Refusal("short_file_write")
        offset += written


def _private_backup(backup_fd, raw, clock):
    now = _check_expiration(clock)
    basename = "content-before-{}-{}-{}.json".format(
        _hash(raw)[:12], now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ"), os.urandom(8).hex())
    fd = os.open(basename, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=backup_fd)
    try:
        os.fchmod(fd, 0o600)
        _write_all(fd, raw)
        os.fsync(fd)
        reread, info = _read_fd(fd)
        if stat.S_IMODE(info.st_mode) != 0o600 or reread != raw:
            raise Refusal("backup_verification_failed")
        os.fsync(backup_fd)
        return basename
    finally:
        os.close(fd)


def _check_host_unchanged(parent_fd, filename, content_fd, original_info, raw):
    path_info = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
    if _fingerprint(path_info) != _fingerprint(original_info):
        raise Refusal("host_changed_before_replace")
    reread, reread_info = _read_fd(content_fd)
    if _fingerprint(reread_info) != _fingerprint(original_info) or reread != raw:
        raise Refusal("host_changed_before_replace")


def _report():
    return {
        "candidate_id": CANDIDATE["id"],
        "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
        "source_commit": SOURCE_COMMIT,
        "observed_at_utc": OBSERVED_AT_UTC,
        "expected_host_sha256": EXPECTED_HOST_SHA256,
        "host_sha256_before": None,
        "host_sha256_after": None,
        "write_committed": False,
        "verdict": "refused",
    }


def _execute(apply=False, host_file=HOST_FILE, backup_dir=BACKUP_DIR,
             expected_sha256=EXPECTED_HOST_SHA256, clock=None, checkpoint=None,
             report_state=None):
    """Internal parameters are for isolated tests; CLI host paths/SHA are fixed."""
    clock = clock or _utc_now
    checkpoint = checkpoint or (lambda phase: None)
    report = report_state if report_state is not None else _report()
    parent_fd = lock_fd = content_fd = backup_fd = temp_fd = None
    tempname = None
    try:
        now = _check_expiration(clock)
        report["as_of_utc"] = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        _candidate_bytes()
        if not os.path.isabs(host_file) or os.path.normpath(host_file) != host_file:
            raise Refusal("unsafe_host_path")
        if not re.match(r"^[0-9a-f]{64}$", expected_sha256):
            raise Refusal("invalid_expected_hash")
        report["expected_host_sha256"] = expected_sha256
        if os.path.commonpath([PUBLIC_ROOT, backup_dir]) == PUBLIC_ROOT:
            raise Refusal("backup_inside_webroot")
        if os.path.commonpath([os.path.dirname(host_file), backup_dir]) == os.path.dirname(host_file):
            raise Refusal("backup_inside_content_directory")
        parent_fd = _open_directory(os.path.dirname(host_file))
        filename = os.path.basename(host_file)
        if apply:
            if not hasattr(signal, "pthread_sigmask"):
                raise Refusal("signal_deferral_unavailable")
            lock_fd, lockname, lock_info = _lock_content(parent_fd, filename)
        content_fd = _open_content(parent_fd, filename)
        raw, original_info = _read_fd(content_fd)
        report["host_sha256_before"] = _hash(raw)
        if report["host_sha256_before"] != expected_sha256:
            raise Refusal("host_sha256_drift")
        text, data = _decode(raw)
        report["event_count_before"] = len(data["events"])
        verdict = _verdict(data)
        if verdict == "already_same":
            report["verdict"] = "already_same"
            report["event_count_after"] = len(data["events"])
            report["host_sha256_after"] = _hash(raw)
            return report
        if verdict != "missing":
            raise Refusal(verdict)
        meta = data.get("meta")
        if not isinstance(meta, dict) or meta.get("content_release") != "3.0.0":
            raise Refusal("content_release_unexpected")
        patched = _insert_bytes(raw, text, data)
        if len(patched) > MAX_BYTES:
            raise Refusal("planned_file_too_large")
        report["planned_host_sha256_after"] = _hash(patched)
        report["existing_bytes_preserved"] = True
        if not apply:
            report["verdict"] = "ready_to_append"
            return report
        # Shared lock protects app writers while every write precondition is checked.
        if lock_info.st_uid != original_info.st_uid:
            raise Refusal("lock_owner_mismatch")
        if hasattr(os, "listxattr") and os.listxattr(content_fd):
            raise Refusal("extended_file_metadata_refused")
        backup_fd = _backup_directory(backup_dir)
        report["backup_basename"] = _private_backup(backup_fd, raw, clock)
        report["backup_sha256"] = _hash(raw)
        checkpoint("after_backup")
        tempname = ".content-hopekeepers-{}.tmp".format(os.urandom(12).hex())
        temp_fd = os.open(tempname, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=parent_fd)
        _write_all(temp_fd, patched)
        os.fchown(temp_fd, original_info.st_uid, original_info.st_gid)
        os.fchmod(temp_fd, stat.S_IMODE(original_info.st_mode))
        if hasattr(os, "listxattr") and os.listxattr(temp_fd):
            raise Refusal("staged_extended_metadata_refused")
        os.fsync(temp_fd)
        staged, staged_info = _read_fd(temp_fd)
        if (staged != patched or staged_info.st_uid != original_info.st_uid or
                staged_info.st_gid != original_info.st_gid or
                stat.S_IMODE(staged_info.st_mode) != stat.S_IMODE(original_info.st_mode)):
            raise Refusal("staged_verification_failed")
        checkpoint("before_replace")
        _check_expiration(clock)
        _parent_current(host_file, parent_fd)
        _lock_current(parent_fd, lockname, lock_fd, lock_info)
        _check_host_unchanged(parent_fd, filename, content_fd, original_info, raw)
        staged_path = os.stat(tempname, dir_fd=parent_fd, follow_symlinks=False)
        if _fingerprint(staged_path) != _fingerprint(staged_info):
            raise Refusal("staged_path_changed")
        # A delivered SIGINT/SIGTERM must not separate rename from its receipt.
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            os.replace(tempname, filename, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            report["write_committed"] = True
            tempname = None
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        checkpoint("after_replace")
        os.fsync(parent_fd)
        _parent_current(host_file, parent_fd)
        _lock_current(parent_fd, lockname, lock_fd, lock_info)
        final_fd = _open_content(parent_fd, filename)
        try:
            final, final_info = _read_fd(final_fd)
        finally:
            os.close(final_fd)
        if (final != patched or final_info.st_uid != original_info.st_uid or
                final_info.st_gid != original_info.st_gid or
                stat.S_IMODE(final_info.st_mode) != stat.S_IMODE(original_info.st_mode)):
            raise Refusal("committed_verification_failed")
        _, final_data = _decode(final)
        if len(final_data["events"]) != len(data["events"]) + 1 or _verdict(final_data) != "already_same":
            raise Refusal("committed_candidate_verification_failed")
        _parent_current(host_file, parent_fd)
        report["host_sha256_after"] = _hash(final)
        report["event_count_after"] = len(final_data["events"])
        report["verdict"] = "appended"
    except Refusal as error:
        report["refusal_code"] = str(error)
    except KeyboardInterrupt:
        report["refusal_code"] = "interrupted"
    except OSError:
        report["refusal_code"] = "filesystem_operation_failed"
    except Exception:
        report["refusal_code"] = "unexpected_operation_failed"
    finally:
        cleanup_mask = (signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
                        if hasattr(signal, "pthread_sigmask") else None)
        try:
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except OSError:
                    report["descriptor_cleanup_incomplete"] = True
            if tempname is not None and parent_fd is not None:
                try:
                    os.unlink(tempname, dir_fd=parent_fd)
                except OSError:
                    report["temporary_cleanup_incomplete"] = True
            for fd in (backup_fd, content_fd, lock_fd, parent_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        report["descriptor_cleanup_incomplete"] = True
        finally:
            if cleanup_mask is not None:
                signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)
    if report["write_committed"] and report["verdict"] != "appended":
        report["verdict"] = "committed_verification_incomplete"
    return report


def verify_source(path):
    """Read-only CI gate: the sole bundled candidate must match canonical main."""
    report = {"candidate_id": CANDIDATE["id"], "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
              "source_commit": SOURCE_COMMIT, "source_path": SOURCE_PATH, "verified": False}
    parent = content = None
    try:
        _candidate_bytes()
        absolute = os.path.abspath(path)
        parent = _open_directory(os.path.dirname(absolute))
        content = _open_content(parent, os.path.basename(absolute))
        raw, _ = _read_fd(content)
        _, data = _decode(raw)
        candidates = [event for event in data["events"] if event["id"] == CANDIDATE["id"]]
        if len(candidates) != 1 or candidates[0] != CANDIDATE:
            raise Refusal("canonical_candidate_mismatch")
        report["verified"] = True
        report["source_file_sha256"] = _hash(raw)
    except Refusal as error:
        report["refusal_code"] = str(error)
    except (OSError, ValueError):
        report["refusal_code"] = "canonical_source_unavailable"
    finally:
        for fd in (content, parent):
            if fd is not None:
                os.close(fd)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Append only if fixed observed SHA and every guard still match.")
    mode.add_argument("--verify-source", metavar="FILE", help="Read-only CI verification against canonical source content.json.")
    args = parser.parse_args(argv)
    previous_term_handler = signal.signal(signal.SIGTERM, _signal_interrupt)
    # Shared receipt survives an interrupt in cleanup or the return assignment.
    result = _report()
    try:
        result = (verify_source(args.verify_source) if args.verify_source
                  else _execute(apply=args.apply, report_state=result))
    except KeyboardInterrupt:
        result["refusal_code"] = "interrupted"
        if result.get("write_committed"):
            result["verdict"] = "committed_verification_incomplete"
        else:
            result["verdict"] = "refused"
    finally:
        signal.signal(signal.SIGTERM, previous_term_handler)
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, indent=2))
    return 0 if result.get("verified") or result.get("verdict") in ("ready_to_append", "already_same", "appended") else 2


if __name__ == "__main__":
    sys.exit(main())
