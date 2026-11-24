
import argparse
import json

from ai_pipeline.report_parser import parse_report


# File categories based on extensions.
# These categories describe file types, not deletion safety.
FILE_CATEGORIES = {
    "video": {
        ".mp4", ".mkv", ".avi", ".mov", ".wmv",
        ".flv", ".webm", ".mpeg", ".mpg", ".m4v"
    },

    "audio": {
        ".mp3", ".wav", ".flac", ".aac", ".ogg",
        ".m4a", ".wma", ".aiff"
    },

    "archive": {
        ".zip", ".rar", ".7z", ".tar", ".gz",
        ".bz2", ".xz", ".iso", ".cab"
    },

    "document": {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".ppt", ".pptx", ".txt", ".csv", ".rtf",
        ".md", ".odt", ".epub"
    },

    "installer": {
        ".exe", ".msi", ".msix", ".msixbundle"
    },

    "image": {
        ".jpg", ".jpeg", ".png", ".webp",
        ".bmp", ".gif", ".tiff", ".svg",
        ".heic", ".raw", ".psd"
    },

    "system_component": {
        ".dll", ".sys", ".drv", ".mui", ".ocx"
    },

    "virtual_disk": {
        ".vhd", ".vhdx", ".vmdk", ".vdi",
        ".qcow2"
    },

    "backup": {
        ".bak", ".backup", ".bkf", ".wbcat"
    },

    "database": {
        ".db", ".sqlite", ".sqlite3",
        ".mdb", ".accdb", ".db3"
    },

    "data": {
        ".dat", ".bin", ".pak", ".pck"
    },

    "log": {
        ".log", ".etl", ".trace"
    },

    "temporary": {
        ".tmp", ".temp", ".part", ".crdownload"
    },

    "code": {
        ".py", ".cpp", ".c", ".h", ".hpp",
        ".java", ".js", ".ts", ".html",
        ".css", ".cs", ".json", ".xml",
        ".yaml", ".yml", ".sql"
    },

    "font": {
        ".ttf", ".otf", ".woff", ".woff2"
    }
}


def classify_file(extension):
    """Classify a file using only its extension."""

    if not isinstance(extension, str):
        return "other"

    extension = extension.strip().lower()

    for category, extensions in FILE_CATEGORIES.items():
        if extension in extensions:
            return category

    return "other"


def select_candidates(
    records,
    min_size_mb=100,
    top_n=20
):
    """Select large files without exposing names or paths."""

    if min_size_mb < 0:
        raise ValueError(
            "Minimum size cannot be negative"
        )

    if top_n <= 0:
        raise ValueError(
            "top_n must be greater than zero"
        )

    min_size_bytes = min_size_mb * 1024 * 1024
    candidates = []

    for record in records:
        if record["item_type"] != "file":
            continue

        if record["scan_outcome"] != "complete":
            continue

        if record["scan_error"]:
            continue

        size_bytes = record["logical_size_bytes"]

        if size_bytes <= 0:
            continue

        if size_bytes < min_size_bytes:
            continue

        extension = record["file_extension"].lower()

        candidates.append({
            "file_extension": extension,
            "category": classify_file(extension),
            "size_mb": round(
                size_bytes / (1024 * 1024), 4
            )
        })

    candidates.sort(
        key=lambda item: item["size_mb"],
        reverse=True
    )

    return candidates[:top_n]


def main():
    parser = argparse.ArgumentParser(
        description="Select large file candidates"
    )

    parser.add_argument("report_path")

    parser.add_argument(
        "--min-mb",
        type=float,
        default=100
    )

    parser.add_argument(
        "--top",
        type=int,
        default=20
    )

    args = parser.parse_args()

    try:
        records = parse_report(args.report_path)

        candidates = select_candidates(
            records,
            min_size_mb=args.min_mb,
            top_n=args.top
        )

    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")

    print(
        json.dumps(
            candidates,
            indent=2,
            ensure_ascii=False
        )
    )

    print(
        f"\nSelected {len(candidates)} candidate(s)."
    )


if __name__ == "__main__":
    main()
