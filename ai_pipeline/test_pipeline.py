
import csv
import json
import tempfile
import unittest
from pathlib import Path

from ai_pipeline.report_parser import parse_report
from ai_pipeline.candidate_selector import (
    classify_file,
    select_candidates,
)


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


if __name__ == "__main__":
    unittest.main()
