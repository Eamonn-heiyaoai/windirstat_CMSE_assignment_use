
import argparse
import heapq
import json
from collections import defaultdict

from ai_pipeline.report_parser import parse_report
from ai_pipeline.candidate_selector import classify_file


MB = 1024 * 1024
GB = 1024 * MB

# File size intervals in bytes.
SIZE_RANGES = [
    ("under_1mb", 0, MB),
    ("1mb_to_100mb", MB, 100 * MB),
    ("100mb_to_1gb", 100 * MB, GB),
    ("1gb_to_10gb", GB, 10 * GB),
    ("over_10gb", 10 * GB, None),
]


def analyze_disk(records, min_size_mb=100):
    """
    Analyze all successfully scanned files.

    Returns summary statistics without exposing
    file names or absolute paths.
    """

    if min_size_mb < 0:
        raise ValueError("Minimum file size cannot be negative")

    total_files = 0
    total_bytes = 0
    large_files = 0
    large_file_bytes = 0

    categories = defaultdict(
        lambda: {"count": 0, "size_bytes": 0}
    )

    extensions = defaultdict(
        lambda: {"count": 0, "size_bytes": 0}
    )

    size_distribution = {
        name: {"count": 0, "size_bytes": 0}
        for name, _, _ in SIZE_RANGES
    }

    # Store only the largest 15 anonymous file records.
    top_files_heap = []
    next_id = 0
    minimum_bytes = min_size_mb * MB

    for record in records:
        if record["item_type"] != "file":
            continue

        if record["scan_outcome"] != "complete":
            continue

        if record["scan_error"]:
            continue

        size = record["logical_size_bytes"]

        if size < 0:
            continue

        extension = str(
            record["file_extension"] or ""
        ).strip().lower()

        if not extension:
            extension = "(no extension)"

        category = classify_file(
            "" if extension == "(no extension)" else extension
        )

        # All valid files participate in the total statistics.
        total_files += 1
        total_bytes += size

        categories[category]["count"] += 1
        categories[category]["size_bytes"] += size

        extensions[extension]["count"] += 1
        extensions[extension]["size_bytes"] += size

        # The user's threshold affects priority files only.
        if size > 0 and size >= minimum_bytes:
            large_files += 1
            large_file_bytes += size

            next_id += 1
            item = (size, next_id, extension, category)

            if len(top_files_heap) < 15:
                heapq.heappush(top_files_heap, item)
            elif size > top_files_heap[0][0]:
                heapq.heapreplace(top_files_heap, item)

        for name, lower, upper in SIZE_RANGES:
            if size >= lower and (
                upper is None or size < upper
            ):
                size_distribution[name]["count"] += 1
                size_distribution[name]["size_bytes"] += size
                break

    def size_mb(size_bytes):
        return round(size_bytes / MB, 2)

    def percentage(size_bytes):
        if total_bytes == 0:
            return 0.0
        return round(size_bytes / total_bytes * 100, 2)

    # Category statistics.
    category_results = {}

    for category, values in sorted(
        categories.items(),
        key=lambda item: item[1]["size_bytes"],
        reverse=True
    ):
        category_results[category] = {
            "count": values["count"],
            "size_mb": size_mb(values["size_bytes"]),
            "percentage": percentage(values["size_bytes"])
        }

    # Keep the 20 extensions using the most space.
    extension_results = []

    for extension, values in sorted(
        extensions.items(),
        key=lambda item: item[1]["size_bytes"],
        reverse=True
    )[:20]:
        extension_results.append({
            "extension": extension,
            "category": classify_file(
                "" if extension == "(no extension)" else extension
            ),
            "count": values["count"],
            "size_mb": size_mb(values["size_bytes"]),
            "percentage": percentage(values["size_bytes"])
        })

    # Distribution of file sizes.
    distribution_results = {}

    for name, _, _ in SIZE_RANGES:
        values = size_distribution[name]
        distribution_results[name] = {
            "count": values["count"],
            "size_mb": size_mb(values["size_bytes"]),
            "percentage": percentage(values["size_bytes"])
        }

    # Largest files above the chosen threshold.
    top_large_files = []

    for size, _, extension, category in sorted(
        top_files_heap,
        reverse=True
    ):
        top_large_files.append({
            "extension": extension,
            "category": category,
            "size_mb": size_mb(size)
        })

    return {
        # Existing fields: keep compatibility with app.py.
        "total_files": total_files,
        "total_size_mb": size_mb(total_bytes),
        "minimum_size_mb": min_size_mb,
        "large_file_count": large_files,
        "file_categories": category_results,

        # New detailed statistics.
        "large_file_total_mb": size_mb(large_file_bytes),
        "large_file_percentage": percentage(large_file_bytes),
        "top_extensions": extension_results,
        "size_distribution": distribution_results,
        "top_large_files": top_large_files
    }


def main():
    parser = argparse.ArgumentParser(
        description="Detailed WinDirStat disk analysis"
    )

    parser.add_argument("report_path")

    parser.add_argument(
        "--min-mb",
        type=float,
        default=100
    )

    args = parser.parse_args()

    try:
        records = parse_report(args.report_path)

        result = analyze_disk(
            records,
            min_size_mb=args.min_mb
        )

    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
