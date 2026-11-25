"""Build a bounded, path-redacted sample of AppData directories for online review."""

import re
from collections import defaultdict

PROFILE_PATH = re.compile(r"^[a-z]:\\users\\[^\\]+\\appdata\\(local|roaming|locallow)\\", re.I)
APPDATA_LABELS = {"local": "%LOCALAPPDATA%", "roaming": "%APPDATA%", "locallow": "%USERPROFILE%\\AppData\\LocalLow"}
MAX_DIRECTORIES = 24
MAX_DEPTH = 4
MIN_SIZE_BYTES = 16 * 1024 ** 2


def directory_candidates(records):
    totals = defaultdict(int)
    estimated = set()
    seen = set()
    for record in records:
        if (record["item_type"] != "file" or record["scan_outcome"] != "complete"
                or record["scan_error"]):
            continue
        path = record.get("file_path", "").replace("/", "\\").removeprefix("\\\\?\\")
        match = PROFILE_PATH.match(path)
        if not match:
            continue
        parts = path[match.end():].split("\\")
        if len(parts) < 2 or any(part in ("", ".", "..") for part in parts):
            continue
        physical = record.get("physical_size_bytes")
        size = record["logical_size_bytes"] if physical is None else physical
        key = path.lower()
        if size <= 0 or key in seen:
            continue
        seen.add(key)
        for depth in range(1, min(len(parts) - 1, MAX_DEPTH) + 1):
            directory = key.rsplit("\\", len(parts) - depth)[0]
            totals[directory] += size
            if physical is None:
                estimated.add(directory)

    # Prefer more specific directories on a tie and reserve room for other apps.
    ordered = sorted(
        (path for path, size in totals.items() if size >= MIN_SIZE_BYTES),
        key=lambda path: (-totals[path], -path.count("\\"), path),
    )
    by_app = defaultdict(int)
    candidates = {}
    for path in ordered:
        match = PROFILE_PATH.match(path)
        parts = path[match.end():].split("\\")
        app_root = path[:match.end()] + parts[0]
        if by_app[app_root] >= 3:
            continue
        # Windows account and drive are omitted. Avoid sending long or unusual labels.
        labels = [part if re.fullmatch(r"[\w .()&+-]{1,48}", part) else "[redacted]" for part in parts]
        if all(label == "[redacted]" for label in labels):
            continue
        label = "\\".join([APPDATA_LABELS[match[1]], *labels])
        by_app[app_root] += 1
        candidates[f"d{len(candidates) + 1}"] = {
            "path": path, "label": label, "size_bytes": totals[path],
            "uses_logical_size": path in estimated,
            "review_only": len(parts) == 1 or any(
                part in {"saves", "worlds", "projects", "settings", "downloads"} for part in parts[1:]
            ),
        }
        if len(candidates) >= MAX_DIRECTORIES:
            break
    return candidates
