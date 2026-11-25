
import csv
import io
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ai_pipeline.ai_advisor import (
    format_cleanup_advice, get_cleanup_guide, get_online_suggestions,
)
from ai_pipeline.disk_analyzer import MB, analyze_disk
from ai_pipeline.candidate_selector import (
    classify_file,
    select_candidates,
)
from ai_pipeline.report_parser import normalize_record, parse_report
from ai_pipeline.installed_apps import UNINSTALL_KEY, read_installed_apps, uninstall_suggestions


class TestCandidateSelection(unittest.TestCase):

    def setUp(self):
        self.records = [
            {
                "file_name": "video.mp4",
                "item_type": "file",
                "file_extension": ".mp4",
                "logical_size_bytes": 500 * 1024 * 1024,
                "physical_size_bytes": 500 * 1024 * 1024,
                "last_change_utc": "",
                "scan_outcome": "complete",
                "scan_error": "",
            },
            {
                "file_name": "notes.txt",
                "item_type": "file",
                "file_extension": ".txt",
                "logical_size_bytes": 1024,
                "physical_size_bytes": 4096,
                "last_change_utc": "",
                "scan_outcome": "complete",
                "scan_error": "",
            },
            {
                "file_name": "Documents",
                "item_type": "directory",
                "file_extension": "",
                "logical_size_bytes": 1000 * 1024 * 1024,
                "physical_size_bytes": 1000 * 1024 * 1024,
                "last_change_utc": "",
                "scan_outcome": "complete",
                "scan_error": "",
            },
            {
                "file_name": "broken.zip",
                "item_type": "file",
                "file_extension": ".zip",
                "logical_size_bytes": 800 * 1024 * 1024,
                "physical_size_bytes": 800 * 1024 * 1024,
                "last_change_utc": "",
                "scan_outcome": "error",
                "scan_error": "Access denied",
            },
        ]

    def test_large_file_selected(self):
        result = select_candidates(self.records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["file_extension"], ".mp4")

    def test_directory_excluded(self):
        result = select_candidates(
            self.records, min_size_mb=0
        )
        extensions = [r["file_extension"] for r in result]
        self.assertNotIn("", extensions)

    def test_scan_error_excluded(self):
        result = select_candidates(
            self.records, min_size_mb=0
        )
        extensions = [r["file_extension"] for r in result]
        self.assertNotIn(".zip", extensions)

    def test_size_threshold(self):
        result = select_candidates(
            self.records, min_size_mb=600
        )
        self.assertEqual(result, [])

    def test_negative_threshold(self):
        with self.assertRaises(ValueError):
            select_candidates(self.records, min_size_mb=-1)

    def test_invalid_top_n(self):
        with self.assertRaises(ValueError):
            select_candidates(self.records, top_n=0)

    def test_privacy(self):
        result = select_candidates(self.records)
        output = json.dumps(result)
        self.assertNotIn("video.mp4", output)
        self.assertNotIn("file_name", output)
        self.assertNotIn("C:\\", output)

    def test_file_classification(self):
        self.assertEqual(classify_file(".MP4"), "video")
        self.assertEqual(classify_file(".pdf"), "document")
        self.assertEqual(classify_file(".zip"), "archive")
        self.assertEqual(classify_file(".unknown"), "other")

    def test_sorting(self):
        records = [
            {**self.records[0],
             "logical_size_bytes": 200 * 1024 * 1024},
            {**self.records[0],
             "file_extension": ".zip",
             "logical_size_bytes": 600 * 1024 * 1024},
        ]
        result = select_candidates(records)
        self.assertEqual(result[0]["file_extension"], ".zip")

    def test_csv_and_json_parsing(self):
        row = {
            "Name": r"C:\test\video.mp4",
            "Logical Size": "524288000",
            "Physical Size": "524288000",
            "Last Change": "2026-11-24T00:00:00Z",
            "WinDirStat Attributes": "8",
            "FileExtension": ".mp4",
            "ScanOutcome": "complete",
            "ScanError": "",
        }

        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / "sample.csv"
            json_path = Path(folder) / "sample.json"

            with csv_path.open(
                "w", encoding="utf-8", newline=""
            ) as file:
                writer = csv.DictWriter(
                    file, fieldnames=list(row.keys())
                )
                writer.writeheader()
                writer.writerow(row)

            json_path.write_text(
                json.dumps([row]), encoding="utf-8"
            )

            csv_result = parse_report(csv_path)
            json_result = parse_report(json_path)

            self.assertEqual(csv_result, json_result)
            self.assertEqual(
                csv_result[0]["file_extension"], ".mp4"
            )
            self.assertEqual(csv_result[0]["file_path"], row["Name"])


class TestCleanupSuggestions(unittest.TestCase):
    local = r"C:\Users\CourseStudent\AppData\Local"
    edge = local + r"\Microsoft\Edge\User Data\Default\Cache\Cache_Data"

    def record(self, path, logical_mb=20, physical_mb=10, flags="8", outcome="complete"):
        return normalize_record({
            "Name": path,
            "Logical Size": logical_mb * MB,
            "Physical Size": None if physical_mb is None else physical_mb * MB,
            "Last Change": "",
            "WinDirStat Attributes": flags,
            "ScanOutcome": outcome,
            "ScanError": "",
        }, 1)

    def summary(self):
        records = [
            self.record(self.edge + r"\unique-file.private"),
            self.record(self.edge.swapcase() + r"\second-file", physical_mb=15),
            self.record(self.edge.swapcase() + r"\UNIQUE-FILE.PRIVATE"),
            self.record(self.edge, physical_mb=500, flags="4"),
            self.record(self.edge + r"\inaccessible", physical_mb=500, outcome="error"),
            self.record(self.edge + r"\..\personal", physical_mb=500),
            self.record(self.local + r"\Temp\partial", logical_mb=30, physical_mb=None),
            self.record(self.local + r"\Temp\empty-allocation", physical_mb=0),
            self.record(self.local + r"\Temperature\personal", physical_mb=500),
            self.record(self.local + r"\pip\Cache\http-v2\download", physical_mb=5),
            self.record(r"C:\Windows\WinSxS\large.dll", physical_mb=800),
            self.record(r"C:\Users\CourseStudent\Downloads\large.exe", physical_mb=900),
        ]
        return analyze_disk(records, min_size_mb=1000)

    def test_cleanup_uses_known_locations_and_scanned_file_sizes(self):
        summary = self.summary()
        self.assertEqual(summary["large_file_count"], 0)
        self.assertEqual(summary["cleanup_items"], [
            {"category": "user_temp", "size_bytes": 30 * MB, "uses_logical_size": True},
            {"category": "edge_cache", "size_bytes": 25 * MB, "uses_logical_size": False},
            {"category": "pip_cache", "size_bytes": 5 * MB, "uses_logical_size": False},
        ])

    def test_local_suggestions_and_empty_scan_skip_api(self):
        with patch("ai_pipeline.ai_advisor.load_api_key") as api_key:
            summary = self.summary()
            english = format_cleanup_advice(summary, language="en")
            chinese = format_cleanup_advice(summary, language="zh")
            records = [self.record(r"C:\Windows\WinSxS\large.dll")]
            self.assertEqual(get_online_suggestions(records, "en", confirmed=True), [])
            empty = format_cleanup_advice(analyze_disk(records), language="en")
            api_key.assert_not_called()

        self.assertIn("Edge browser cache (25.00 MiB size on disk)", english)
        self.assertIn("30.00 MiB estimated size", english)
        self.assertIn("Cached images and files", english)
        self.assertIn("下次打开时可能稍慢", chinese)
        self.assertIn("no common items", empty)

    def test_online_discovery_redacts_paths_and_uses_scanned_sizes(self):
        cache = r"C:\Users\CourseStudent\AppData\Roaming\.minecraft\cache"
        records = [
            self.record(cache + r"\unique-file.private", physical_mb=1700),
            self.record(cache + r"\another-file", physical_mb=1500),
            self.record(cache + r"\unreadable", physical_mb=3000, outcome="error"),
            self.record(r"C:\Users\CourseStudent\Documents\private-file", physical_mb=4000),
            self.record(r"C:\Windows\WinSxS\large.dll", physical_mb=2000),
        ]
        summary = analyze_disk(records)
        self.assertEqual(summary["cleanup_items"], [])
        response_body = {
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": json.dumps({
                    "items": [
                        {"id": "d2", "kind": "cache", "name": "Minecraft data", "reason": "Likely game data."},
                        {"id": "d1", "kind": "cache", "name": "Minecraft cache", "reason": "Likely game cache.",
                         "size_bytes": 1},
                        {"id": "fake", "kind": "cache", "name": "Fake item", "reason": "Fabricated."},
                    ],
                })},
            }],
        }
        response = io.BytesIO(json.dumps(response_body).encode("utf-8"))
        with (patch("ai_pipeline.ai_advisor.load_api_key", return_value="test"),
              patch("ai_pipeline.ai_advisor.urllib.request.urlopen", return_value=response) as send):
            summary["online_items"] = get_online_suggestions(records, "en", confirmed=True)

        request = send.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(json.loads(payload["messages"][1]["content"]), {
            "directories": [
                {"id": "d1", "directory": r"%APPDATA%\.minecraft\cache", "size_bytes": 3200 * MB},
                {"id": "d2", "directory": r"%APPDATA%\.minecraft", "size_bytes": 3200 * MB},
            ],
        })
        for private_text in (b"coursestudent", b"unique-file", b".private", b"winsxs", b"private-file"):
            self.assertNotIn(private_text, request.data.lower())
        advice = format_cleanup_advice(summary, "en")
        self.assertIn("Minecraft cache (3.12 GiB", advice)
        self.assertIn("Confirm these are rebuildable", advice)
        self.assertNotIn("Fake item", advice)
        self.assertNotIn("Minecraft data", advice)

    def test_online_explanations_require_explicit_opt_in(self):
        with (patch("ai_pipeline.ai_advisor.load_api_key") as key,
              patch("ai_pipeline.ai_advisor.urllib.request.urlopen") as send):
            records = [self.record(self.edge + r"\test")]
            self.assertEqual(get_online_suggestions(records, "en"), [])
            self.assertEqual(get_online_suggestions(records, "en", confirmed=False), [])
            self.assertIn("Edge browser cache", format_cleanup_advice(self.summary(), "en"))
            key.assert_not_called()
            send.assert_not_called()

    def test_cleanup_guide_requires_consent_and_sends_only_selected_metadata(self):
        item = {
            "id": "d1", "label": r"%APPDATA%\.minecraft\cache", "size_bytes": 3200 * MB,
            "kind": "cache", "path": r"C:\Users\Private\AppData\Roaming\.minecraft\cache",
            "reason": "First response is not sent back.",
        }
        result = {
            "mode": "cleanup", "steps": ["Open the game launcher.", "Check its cache settings."],
            "impact": "Some files may need to be downloaded again.",
        }
        encoded = json.dumps({"choices": [{"message": {"content": json.dumps(result)}}]}).encode()
        with (patch("ai_pipeline.ai_advisor.load_api_key", return_value="test") as key,
              patch("ai_pipeline.ai_advisor.urllib.request.urlopen", side_effect=lambda *a, **k: io.BytesIO(encoded)) as send):
            self.assertIsNone(get_cleanup_guide(item, "en"))
            self.assertIsNone(get_cleanup_guide(item, "en", confirmed=False))
            key.assert_not_called()
            send.assert_not_called()
            self.assertEqual(get_cleanup_guide(item, "en", confirmed=True), result)
            request = json.loads(send.call_args.args[0].data)
            self.assertEqual(json.loads(request["messages"][1]["content"]), {
                "directory": item["label"], "size_bytes": item["size_bytes"], "mode": "cleanup",
            })
            with self.assertRaisesRegex(RuntimeError, "Unexpected DeepSeek cleanup guidance"):
                get_cleanup_guide({**item, "kind": "review"}, "en", confirmed=True)
            self.assertEqual(json.loads(json.loads(send.call_args.args[0].data)["messages"][1]["content"])["mode"],
                             "verify")

    def test_added_cache_rules_exclude_user_data(self):
        roaming = r"C:\Users\CourseStudent\AppData\Roaming"
        matches = {
            "vscode_cache": roaming + r"\Code\CachedExtensionVSIXs\download",
            "vscode_insiders_cache": roaming + r"\Code - Insiders\CachedExtensionVSIXs\download",
            "discord_cache": roaming + r"\discord\Cache\Cache_Data\temp",
            "npm_cache": self.local + r"\npm-cache\_cacache\content-v2\temp",
            "nuget_cache": self.local + r"\NuGet\v3-cache\feed\package.dat",
        }
        other_paths = [
            roaming + r"\Code\User\workspaceStorage\private",
            roaming + r"\discord\Local Storage\account",
            self.local + r"\npm-cache\_logs\log",
            r"C:\Users\CourseStudent\.nuget\packages\package",
            r"C:\Users\CourseStudent\Downloads\file",
        ]
        summary = analyze_disk([self.record(path) for path in [*matches.values(), *other_paths]])
        self.assertEqual(
            {item["category"]: item["size_bytes"] for item in summary["cleanup_items"]},
            dict.fromkeys(matches, 10 * MB),
        )

    def test_ranked_sections_share_ten_slots_and_expanded_list_keeps_all(self):
        extra_caches = [
            self.local + r"\Microsoft\Edge\User Data\Default\Cache\temp",
            self.local + r"\Google\Chrome\User Data\Default\Cache\file",
            self.local + r"\Mozilla\Firefox\Profiles\demo\cache2\entry",
            self.local + r"\Temp\file",
            self.local + r"\pip\Cache\wheels\file",
            self.local + r"\npm-cache\_cacache\file",
            self.local + r"\NuGet\v3-cache\file",
            r"C:\Users\CourseStudent\AppData\Roaming\discord\Cache\file",
            r"C:\Users\CourseStudent\AppData\Roaming\Code\CachedExtensionVSIXs\file",
            r"C:\Users\CourseStudent\AppData\Roaming\Code - Insiders\CachedExtensionVSIXs\file",
        ]
        summary = analyze_disk([
            self.record(path, physical_mb=10 + index) for index, path in enumerate(extra_caches)
        ])
        self.assertEqual(len(summary["cleanup_items"]), 10)
        summary["uninstall_items"] = [
            {"name": f"Local App {number}", "size_bytes": 1024 * MB,
             "uses_logical_size": False, "path": r"D:\Private\Apps"}
            for number in range(3)
        ]

        collapsed = format_cleanup_advice(summary, "en")
        expanded = format_cleanup_advice(summary, "en", expanded=True)
        self.assertEqual(collapsed.count("size on disk"), 7)
        self.assertEqual(expanded.count("size on disk"), 10)
        self.assertEqual(collapsed.count("scanned installation folder"), 3)
        self.assertNotIn("Edge browser cache", collapsed)
        self.assertIn("Edge browser cache", expanded)
        self.assertIn("确认不用后可考虑卸载", format_cleanup_advice(summary, "zh"))

    def test_advice_page_boundaries_keep_every_item_once(self):
        for count, page_lengths in ((10, [10]), (11, [10, 1]), (21, [10, 10, 1])):
            with self.subTest(count=count):
                summary = {"uninstall_items": [
                    {"name": f"Example app {number:02}", "size_bytes": 1024 * MB,
                     "uses_logical_size": False}
                    for number in range(count)
                ]}
                pages = [format_cleanup_advice(summary, "en", page=page)
                         for page in range(len(page_lengths))]
                self.assertEqual(
                    [page.count("scanned installation folder") for page in pages],
                    page_lengths,
                )
                expanded = format_cleanup_advice(summary, "en", expanded=True)
                for number in range(count):
                    name = f"Example app {number:02} "
                    self.assertEqual(sum(page.count(name) for page in pages), 1)
                    self.assertEqual(expanded.count(name), 1)

    def test_uninstall_suggestions_require_full_unambiguous_scan_coverage(self):
        good = r"D:\Applications\Photo Editor"
        incomplete = r"C:\Program Files\Incomplete"
        partial = r"C:\Program Files\Partial"
        duplicate = r"C:\Program Files\Shared"
        parent = r"C:\Program Files\Suite"
        child = parent + r"\Module"
        protected = r"C:\Windows\Installer"
        paths = [
            (good, "Photo Editor"), (good.upper(), "PHOTO EDITOR"),
            (incomplete, "Incomplete"), (partial, "Partial"),
            (duplicate, "Shared A"), (duplicate, "Shared B"),
            (parent, "Suite"), (child, "Module"), (protected, "Protected"),
        ]
        records = [
            self.record(path, flags="4", outcome="partial" if path == partial else "complete")
            for path in {good, partial, duplicate, parent, child, protected}
        ]
        records += [
            self.record(path + r"\binary.exe", physical_mb=1400)
            for path in {good, incomplete, partial, duplicate, parent, child, protected}
        ]
        records.append(self.record(good.upper() + r"\BINARY.EXE", physical_mb=1400))
        records.append(self.record(good + r"\assets\file", physical_mb=500, outcome="error"))
        apps = [(name, path) for path, name in paths]
        self.assertEqual(uninstall_suggestions(records, apps), [])
        records.pop()
        self.assertEqual(uninstall_suggestions(records, apps), [
            {"name": "Photo Editor", "size_bytes": 1400 * MB, "uses_logical_size": False},
        ])

    def test_windows_uninstall_registry_reads_both_views_and_skips_hidden_records(self):
        def entry(name, folder, **options):
            return {
                "DisplayName": name, "InstallLocation": folder,
                "UninstallString": "stored command that is never run", **options,
            }

        records = {
            ("machine", 64): {
                "editor": entry("Editor", r"C:\Program Files\Editor"),
                "patch": entry("Editor patch", r"C:\Program Files\Patch", ReleaseType="Update"),
                "hidden": entry("Component", r"C:\Program Files\Component", SystemComponent=1),
                "shared": entry("Common", r"C:\Program Files\Common Files\Foo"),
            },
            ("machine", 32): {
                "tool": entry("Tool", r"C:\Program Files (x86)\Tool"),
                "missing": entry("No Path", ""),
            },
            ("user", 64): {
                "chat": entry("Chat", self.local + r"\Programs\Chat"),
                "protected": entry("Locked", self.local + r"\Programs\Locked", NoRemove=1),
            },
        }

        def open_key(base, subkey, reserved, access):
            view = 64 if access & 64 else 32
            if subkey == UNINSTALL_KEY:
                return nullcontext(records[(base, view)]) if (base, view) in records else nullcontext({})
            return nullcontext(base[subkey])

        def query_value(key, name):
            if name not in key:
                raise FileNotFoundError(name)
            return key[name], 0

        registry = SimpleNamespace(
            HKEY_LOCAL_MACHINE="machine", HKEY_CURRENT_USER="user",
            KEY_READ=1, KEY_WOW64_64KEY=64, KEY_WOW64_32KEY=32,
            OpenKey=open_key, QueryValueEx=query_value,
            QueryInfoKey=lambda parent: (len(parent), 0, 0),
            EnumKey=lambda parent, index: list(parent)[index],
        )
        with patch.dict("sys.modules", {"winreg": registry}):
            apps = read_installed_apps()
        self.assertEqual(dict(apps), {
            "Editor": r"c:\program files\editor",
            "Tool": r"c:\program files (x86)\tool",
            "Chat": self.local.lower() + r"\programs\chat",
        })


if __name__ == "__main__":
    unittest.main()
