"""Match locally registered desktop apps to a fresh WinDirStat scan."""

import re
from collections import defaultdict


UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
MIN_INSTALL_SIZE = 1024 ** 3
SHARED_DIRECTORIES = {
    "appdata", "applications", "apps", "common files", "desktop", "documents",
    "downloads", "games", "local", "locallow", "microsoft shared", "modifiablewindowsapps",
    "packages", "program files", "program files (x86)", "programs", "public",
    "roaming", "software", "users", "windowsapps",
}
SYSTEM_DIRECTORIES = {"windows", "windows.old", "programdata", "recovery", "system volume information"}
SHARED_SUBTREES = {"common files", "microsoft shared", "windowsapps", "modifiablewindowsapps"}
UPDATE_TYPES = {"update", "hotfix", "security update", "service pack", "update rollup"}


def local_path(value):
    path = value.strip().replace("/", "\\").lower().removeprefix("\\\\?\\").rstrip("\\")
    if not re.fullmatch(r"[a-z]:(?:\\[^\\:*?\"<>|]+)+", path):
        return ""
    if any(part in (".", "..") for part in path.split("\\")):
        return ""
    return path


def app_install_path(value):
    path = local_path(value)
    if not path:
        return ""
    parts = path.split("\\")[1:]
    if (parts[0] in SYSTEM_DIRECTORIES or parts[0].startswith("$")
            or parts[-1] in SHARED_DIRECTORIES
            or any(part in SHARED_SUBTREES for part in parts)
            or (parts[0] == "users" and (len(parts) < 4 or parts[2] != "appdata"))):
        return ""
    return path


def read_installed_apps():
    """Read names and install directories from the current machine only."""
    try:
        import winreg
    except ImportError:
        return []

    def value(key, name, default=None):
        try:
            return winreg.QueryValueEx(key, name)[0]
        except OSError:
            return default

    apps = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, UNINSTALL_KEY, 0, winreg.KEY_READ | view) as parent:
                    count = winreg.QueryInfoKey(parent)[0]
                    for index in range(count):
                        try:
                            name = winreg.EnumKey(parent, index)
                            with winreg.OpenKey(parent, name, 0, winreg.KEY_READ | view) as key:
                                display = value(key, "DisplayName")
                                location = value(key, "InstallLocation")
                                if not isinstance(display, str) or not isinstance(location, str):
                                    continue
                                if (value(key, "SystemComponent") in (1, "1")
                                        or value(key, "NoRemove") in (1, "1")
                                        or value(key, "ParentKeyName")
                                        or str(value(key, "ReleaseType", "")).strip().casefold() in UPDATE_TYPES
                                        or not (value(key, "UninstallString")
                                                or value(key, "QuietUninstallString"))):
                                    continue
                                display = " ".join(display.split())
                                install_path = app_install_path(location)
                                if display and install_path:
                                    apps.append((display, install_path))
                        except OSError:
                            continue
            except OSError:
                continue
    return apps


def uninstall_suggestions(records, apps):
    """Measure only complete, unambiguously owned installation directories."""
    names_by_path = defaultdict(dict)
    for name, location in apps:
        path = app_install_path(location)
        if path:
            names_by_path[path].setdefault(name.casefold(), name)

    excluded = {path for path, names in names_by_path.items() if len(names) != 1}
    for path in names_by_path:
        parent = path.rpartition("\\")[0]
        while parent:
            if parent in names_by_path:
                excluded.update((path, parent))
            parent = parent.rpartition("\\")[0]
    eligible = names_by_path.keys() - excluded
    if not eligible:
        return []

    complete_dirs = set()
    incomplete_dirs = set()
    totals = defaultdict(int)
    estimated = set()
    counted = set()
    for record in records:
        path = local_path(record.get("file_path", ""))
        if not path:
            continue
        directory = path
        while directory and directory not in eligible:
            directory = directory.rpartition("\\")[0]
        if not directory:
            continue
        if record["scan_outcome"] != "complete" or record["scan_error"]:
            incomplete_dirs.add(directory)
            continue
        if path == directory and record["item_type"] == "directory":
            complete_dirs.add(directory)
        elif path != directory and record["item_type"] == "file" and path not in counted:
            counted.add(path)
            size = record.get("physical_size_bytes")
            if size is None:
                size = record["logical_size_bytes"]
                estimated.add(directory)
            totals[directory] += size

    return [
        {"name": next(iter(names_by_path[path].values())), "size_bytes": totals[path],
         "uses_logical_size": path in estimated}
        for path in sorted(complete_dirs - incomplete_dirs)
        if totals[path] >= MIN_INSTALL_SIZE
    ]
