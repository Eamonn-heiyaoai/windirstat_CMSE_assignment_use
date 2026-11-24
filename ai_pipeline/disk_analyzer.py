
import argparse
import json

from ai_pipeline.report_parser import parse_report
from ai_pipeline.candidate_selector import classify_file


MB = 1024 * 1024


def analyze_disk(records, min_size_mb=100):
    """Analyse all valid files in a WinDirStat report."""

    if min_size_mb < 0:
        raise ValueError("Minimum file size cannot be negative")

    total_files = 0
    total_bytes = 0
    large_files = 0
    categories = {}

    for record in records:
        if record["item_type"] != "file":
            continue

        if record["scan_outcome"] != "complete":
            continue

        if record["scan_error"]:
            continue

        size = record["logical_size_bytes"]
        extension = record["file_extension"]
        category = classify_file(extension)

        total_files += 1
        total_bytes += size

        if size > 0 and size >= min_size_mb * MB:
            large_files += 1

        if category not in categories:
            categories[category] = {
                "count": 0,
                "size_bytes": 0
            }

        categories[category]["count"] += 1
        categories[category]["size_bytes"] += size

    category_results = {}

    for category, values in categories.items():
        size_bytes = values["size_bytes"]

        category_results[category] = {
            "count": values["count"],
            "size_mb": round(size_bytes / MB, 2),
            "percentage": round(
                size_bytes / total_bytes * 100, 2
            ) if total_bytes > 0 else 0
        }

    category_results = dict(
        sorted(
            category_results.items(),
            key=lambda item: item[1]["size_mb"],
            reverse=True
        )
    )

    return {
        "total_files": total_files,
        "total_size_mb": round(total_bytes / MB, 2),
        "minimum_size_mb": min_size_mb,
        "large_file_count": large_files,
        "file_categories": category_results
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyse a complete WinDirStat report"
    )

    parser.add_argument("report_path")
    parser.add_argument(
        "--min-mb", type=float, default=100
    )

    args = parser.parse_args()

    try:
        records = parse_report(args.report_path)
        result = analyze_disk(records, args.min_mb)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
