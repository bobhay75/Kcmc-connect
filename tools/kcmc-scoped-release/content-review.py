#!/usr/bin/env python3
"""Read-only comparison of one approved public event with host content.

Python 3.6 compatible. Reads the fixed host JSON directly, without bootstrapping
the app. Prints only the approved source candidate, file hashes, and verdicts.
It never writes or publishes any content. Examples:
  python3 content-review.py
  python3 content-review.py --as-of 2026-10-07T15:00:00Z
An explicit --as-of must be UTC; a date alone means midnight UTC.
"""

from __future__ import print_function

import argparse
import datetime
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata


HOST_CONTENT_FILE = "/home/bobsome1/public_html/kcmc-connect/data/content.json"
SOURCE_COMMIT = "f4442fc4cce2121828544b79b8ba3591c5fe0dab"
SOURCE_PATH = "KCMC-Connect-Phase6-Recreated/data/content.json"
SOURCE_BLOB_SHA1 = "e7eb008c163a524f036d52b5e8e6203f3c1a60d9"
SOURCE_URL = ("https://github.com/bobhay75/Kcmc-connect/blob/" +
              SOURCE_COMMIT + "/" + SOURCE_PATH)
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
MAX_CONTENT_BYTES = 16 * 1024 * 1024
UTC = datetime.timezone.utc


class ReviewRefusal(Exception):
    """A generic code, never a host value or exception message."""


def _candidate_hash():
    encoded = json.dumps(CANDIDATE, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_text(value):
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_as_of(value):
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            parsed = datetime.datetime.strptime(value, "%Y-%m-%d")
        elif re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", value):
            parsed = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        else:
            raise ValueError()
        return parsed.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ (UTC).")


def _candidate_expiration():
    # Source offset is church local time (-05:00), not an inferred UTC date.
    value = CANDIDATE["expires_at"]
    match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([+-])(\d{2}):(\d{2})$", value)
    if not match:
        raise ReviewRefusal("invalid_source_expiration")
    parsed = datetime.datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S")
    offset = datetime.timedelta(hours=int(match.group(3)), minutes=int(match.group(4)))
    if match.group(2) == "-":
        offset = -offset
    return parsed.replace(tzinfo=datetime.timezone(offset)).astimezone(UTC)


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReviewRefusal("duplicate_json_keys")
        result[key] = value
    return result


def _reject_non_json_number(value):
    raise ReviewRefusal("invalid_json")


def _read_regular_file(path):
    """Open read-only, reject symlinks in any path component and file races."""
    if not os.path.isabs(path):
        raise ReviewRefusal("non_absolute_host_path")
    cursor = os.path.sep
    parts = path.split(os.path.sep)[1:]
    for index, part in enumerate(parts):
        cursor = os.path.join(cursor, part)
        info = os.lstat(cursor)
        if stat.S_ISLNK(info.st_mode):
            raise ReviewRefusal("symlink_refused")
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ReviewRefusal("non_directory_parent")
    if not stat.S_ISREG(info.st_mode):
        raise ReviewRefusal("non_regular_host_file")
    if info.st_size > MAX_CONTENT_BYTES:
        raise ReviewRefusal("host_file_too_large")
    if not hasattr(os, "O_NOFOLLOW"):
        raise ReviewRefusal("nofollow_unavailable")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ReviewRefusal("non_regular_host_file")
        if (before.st_dev, before.st_ino) != (info.st_dev, info.st_ino):
            raise ReviewRefusal("host_file_changed_during_read")
        with os.fdopen(fd, "rb") as handle:
            fd = None
            raw = handle.read(MAX_CONTENT_BYTES + 1)
            after = os.fstat(handle.fileno())
        current = os.lstat(path)
        if (stat.S_ISLNK(current.st_mode) or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or
                (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ReviewRefusal("host_file_changed_during_read")
        if len(raw) > MAX_CONTENT_BYTES:
            raise ReviewRefusal("host_file_too_large")
        return raw
    finally:
        if fd is not None:
            os.close(fd)


def _normalized_title(value):
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"[-\u2010-\u2015\u2212]", " ", text)
    return " ".join(text.split())


def _normalized_date(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", text):
        return None
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _normalized_time(value):
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).casefold())
    match = re.match(r"^(\d{1,2})(?::(\d{2}))?(am|pm)$", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        if not 1 <= hour <= 12 or not 0 <= minute < 60:
            return None
        hour = hour % 12 + (12 if match.group(3) == "pm" else 0)
        return "{:02d}:{:02d}".format(hour, minute)
    match = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour < 24 and 0 <= minute < 60:
            return "{:02d}:{:02d}".format(hour, minute)
    return None


def _signature(event):
    title = _normalized_title(event.get("title"))
    # The short ministry name may be an existing record for this gathering.
    # Only flag it at the identical date/time; never infer other occurrences.
    if title == "hope keepers":
        title = _normalized_title(CANDIDATE["title"])
    return (title,
            _normalized_date(event.get("date")),
            _normalized_time(event.get("time")))


def _base_report(as_of):
    return {
        "read_only": True,
        "source_candidate_only": True,
        "as_of_utc": _utc_text(as_of),
        "source": {
            "commit": SOURCE_COMMIT,
            "path": SOURCE_PATH,
            "content_blob_sha1": SOURCE_BLOB_SHA1,
            "url": SOURCE_URL,
            "rationale": "Approved event in main; September 25 Front Pew / PR #81.",
        },
        "candidate": dict(CANDIDATE),
        "candidate_sha256": _candidate_hash(),
        "candidate_expires_at_utc": _utc_text(_candidate_expiration()),
        "host_file_sha256": None,
        "verdict": "refused",
        "writes_performed": False,
    }


def _review_host_file(path, as_of):
    """Internal path parameter permits isolated fixtures; CLI path is fixed."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ReviewRefusal("as_of_timezone_required")
    report = _base_report(as_of)
    try:
        if as_of.astimezone(UTC) >= _candidate_expiration():
            raise ReviewRefusal("expired_candidate")
        raw = _read_regular_file(path)
        report["host_file_sha256"] = hashlib.sha256(raw).hexdigest()
        try:
            document = json.loads(raw.decode("utf-8"),
                                  object_pairs_hook=_reject_duplicate_keys,
                                  parse_constant=_reject_non_json_number)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ReviewRefusal("invalid_json")
        if not isinstance(document, dict) or not isinstance(document.get("events"), list):
            raise ReviewRefusal("invalid_event_container")
        identifiers = set()
        events = document["events"]
        for event in events:
            if not isinstance(event, dict):
                raise ReviewRefusal("invalid_event_record")
            identifier = event.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                raise ReviewRefusal("invalid_event_id")
            if identifier.strip() in identifiers:
                raise ReviewRefusal("duplicate_event_ids")
            identifiers.add(identifier.strip())
        same_id = [event for event in events
                   if event["id"].strip() == CANDIDATE["id"]]
        possible_duplicates = [event for event in events
                               if event["id"].strip() != CANDIDATE["id"]
                               and _signature(event) == _signature(CANDIDATE)]
        report["possible_duplicate"] = bool(possible_duplicates)
        # Do not output matching host IDs, titles, descriptions or other fields.
        if same_id:
            report["verdict"] = ("already_same" if same_id[0] == CANDIDATE
                                 else "same_id_conflict")
        else:
            report["verdict"] = ("possible_duplicate" if possible_duplicates else "missing")
    except ReviewRefusal as error:
        report["refusal_code"] = str(error)
    except OSError:
        report["refusal_code"] = "host_file_unavailable"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", type=_parse_as_of, default=None,
                        help="UTC date/time; default is the current system UTC clock.")
    args = parser.parse_args(argv)
    as_of = args.as_of or datetime.datetime.now(UTC)
    report = _review_host_file(HOST_CONTENT_FILE, as_of)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 2 if report["verdict"] == "refused" else 0


if __name__ == "__main__":
    sys.exit(main())
