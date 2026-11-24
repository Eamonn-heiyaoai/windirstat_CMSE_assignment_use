
import argparse
import json

from ai_pipeline.report_parser import parse_report


# Classify files using their extensions.
FILE_CATEGORIES = {
    "video": {".mp4", ".mkv", ".avi", ".mov"},
    "audio": {".mp3", ".wav", ".flac"},
    "archive": {".zip", ".rar", ".7z", ".iso"},
    "document": {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv"},
    "installer": {".exe", ".msi"},
    "image": {".jpg", ".jpeg", ".png", ".webp"},
}


def classify_file(extension):
    extension = extension.lower()

    for category, extensions in FILE_CATEGORIES.items():
        if extension in extensions:
            return category

    return "other"


def select_candidates(records, min_size_mb=100, top_n=20):
    """Select large files and prepare privacy-safe metadata."""
    if min_size_mb < 0:
        raise ValueError("Minimum size cannot be negative")
    if top_n <= 0:
        raise ValueError("top_n must be greater than zero")

    min_size_bytes = min_size_mb * 1024 * 1024
    candidates = []

    for record in records:
        # Exclude directories and other non-file items.
        if record["item_type"] != "file":
            continue

        # Exclude incomplete scans or records with errors.
        if record["scan_outcome"] != "complete":
            continue
        if record["scan_error"]:
            continue

        size_bytes = record["logical_size_bytes"]

        # Ignore empty or undersized files.
        if size_bytes <= 0 or size_bytes < min_size_bytes:
            continue

        extension = record["file_extension"].lower()

        # Do not include file names or absolute paths.
        candidates.append({
            "file_extension": extension,
            "category": classify_file(extension),
            "size_mb": round(size_bytes / (1024 * 1024), 4)
        })

    # Prioritize larger files.
    candidates.sort(key=lambda item: item["size_mb"], reverse=True)

    return candidates[:top_n]


def main():
    parser = argparse.ArgumentParser(
        description="Select file candidates from a WinDirStat report"
    )
    parser.add_argument("report_path", help="CSV or JSON report path")
    parser.add_argument(
        "--min-mb",
        type=float,
        default=100,
        help="Minimum file size in MiB (default: 100)"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Maximum number of candidates (default: 20)"
    )

    args = parser.parse_args()

    try:
        records = parse_report(args.report_path)
        candidates = select_candidates(
            records,
            min_size_mb=args.min_mb,
            top_n=args.top
        )
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f"Error: {error}\n")

    print(json.dumps(candidates, indent=2, ensure_ascii=False))
    print(f"\nSelected {len(candidates)} candidate(s).")


if __name__ == "__main__":
    main()
