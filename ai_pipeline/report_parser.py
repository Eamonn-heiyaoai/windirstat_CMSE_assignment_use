import csv
import json
import sys
from pathlib import Path, PureWindowsPath

# WinDirStat item type flags
TYPE_MASK = 0x00003FFF
IT_DIRECTORY = 1 << 2
IT_FILE = 1 << 3

REQUIRED_FIELDS = [
    "Name",
    "Logical Size",
    "Physical Size",
    "Last Change",
    "WinDirStat Attributes",
    "ScanOutcome",
    "ScanError",
]


def parse_size(value, field, row_number):
    try:
        size = int(str(value).strip().replace(",", ""))
        if size < 0:
            raise ValueError
        return size
    except (ValueError, TypeError):
        raise ValueError(
            f"Row {row_number}: invalid {field}: {value}"
        )


def parse_item_type(value, row_number):
    try:
        flags = int(str(value).strip(), 0)
    except (ValueError, TypeError):
        raise ValueError(
            f"Row {row_number}: invalid WinDirStat Attributes"
        )

    item_type = flags & TYPE_MASK

    if item_type & IT_DIRECTORY:
        return "directory"
    if item_type & IT_FILE:
        return "file"

    return "other"


def normalize_record(row, row_number):
    missing = [
        field for field in REQUIRED_FIELDS
        if field not in row
    ]

    if missing:
        raise ValueError(
            f"Row {row_number}: missing fields {missing}"
        )

    raw_name = str(row["Name"]).strip()

    if not raw_name:
        raise ValueError(
            f"Row {row_number}: empty file name"
        )

    item_type = parse_item_type(
        row["WinDirStat Attributes"], row_number
    )

    # Keep only the local filename, not the absolute path.
    file_name = PureWindowsPath(raw_name).name

    extension = str(
        row.get("FileExtension", "")
    ).strip().lower()

    if not extension and item_type == "file":
        extension = PureWindowsPath(file_name).suffix.lower()

    return {
        "file_name": file_name,
        "item_type": item_type,
        "file_extension": extension,
        "logical_size_bytes": parse_size(
            row["Logical Size"], "Logical Size", row_number
        ),
        "physical_size_bytes": parse_size(
            row["Physical Size"], "Physical Size", row_number
        ),
        "last_change_utc": str(row["Last Change"]).strip(),
        "scan_outcome": str(row["ScanOutcome"]).strip().lower(),
        "scan_error": str(row["ScanError"]).strip()
    }


def parse_report(report_path):
    path = Path(report_path)

    if not path.is_file():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()

    if suffix == ".csv":
        with path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                raise ValueError("CSV has no header")

            rows = list(reader)

    elif suffix == ".json":
        with path.open(
            "r", encoding="utf-8-sig"
        ) as file:
            rows = json.load(file)

        if not isinstance(rows, list):
            raise ValueError("JSON must contain a list")

    else:
        raise ValueError("Only CSV and JSON are supported")

    return [
        normalize_record(row, index + 1)
        for index, row in enumerate(rows)
    ]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python report_parser.py <report_path>")
        sys.exit(1)

    try:
        result = parse_report(sys.argv[1])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\nSuccessfully parsed {len(result)} records.")

    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Error: {error}")
        sys.exit(1)
