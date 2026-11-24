
import argparse
import json
import os
import urllib.request
import urllib.error

from ai_pipeline.report_parser import parse_report
from ai_pipeline.disk_analyzer import analyze_disk


API_URL = "https://api.deepseek.com/chat/completions"


def get_advice(summary, use_api=False):
    """Generate disk organization advice from aggregate statistics."""

    # Only send aggregate statistics; no original file paths or names.
    safe_summary = {
        "total_files": summary["total_files"],
        "total_size_mb": summary["total_size_mb"],
        "minimum_size_mb": summary["minimum_size_mb"],
        "large_file_count": summary["large_file_count"],
        "file_categories": summary["file_categories"],
    }

    if not use_api:
        return (
            "[Demo Mode - No API request sent]\n\n"
            f"Total files: {safe_summary['total_files']}\n"
            f"Total size: {safe_summary['total_size_mb']} MiB\n"
            f"Files above threshold: {safe_summary['large_file_count']}\n\n"
            "Suggestion: Review large files and categories using "
            "the most space. Confirm their importance before "
            "archiving or deleting anything."
        )

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not configured.")

    payload = {
        "model": "deepseek-flash",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a cautious Windows disk organization assistant. "
                    "Answer in Chinese. Analyze only the provided statistics. "
                    "Give practical, category-level storage organization advice. "
                    "Do not claim to know individual files. "
                    "Never recommend automatic deletion. "
                    "Do not invent file names, locations, or contents."
                )
            },
            {
                "role": "user",
                "content": (
                    "Please analyze these disk statistics and provide "
                    "five concise organization suggestions:\n"
                    + json.dumps(safe_summary, ensure_ascii=False)
                )
            }
        ],
        "max_tokens": 800,
        "stream": False
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"DeepSeek API returned HTTP {error.code}"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(
            f"DeepSeek connection failed: {error}"
        ) from error

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Unexpected DeepSeek response.") from error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report_path")
    parser.add_argument("--min-mb", type=float, default=100)
    parser.add_argument("--api", action="store_true")
    args = parser.parse_args()

    try:
        records = parse_report(args.report_path)
        summary = analyze_disk(records, args.min_mb)
        advice = get_advice(summary, use_api=args.api)
        print(advice)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
