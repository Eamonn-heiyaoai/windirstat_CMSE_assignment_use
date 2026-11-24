
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

from ai_pipeline.report_parser import parse_report
from ai_pipeline.disk_analyzer import analyze_disk


API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-flash"

# The .env file is located in the repository root.
CONFIG_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_api_key():
    """Read the API key from the local .env file."""

    if not CONFIG_FILE.is_file():
        raise ValueError(
            "DeepSeek API key is not configured. "
            "Please create a .env file from .env.example."
        )

    try:
        lines = CONFIG_FILE.read_text(
            encoding="utf-8-sig"
        ).splitlines()
    except OSError as error:
        raise RuntimeError(
            "Cannot read the local API configuration."
        ) from error

    for line in lines:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("DEEPSEEK_API_KEY="):
            key = line.split("=", 1)[1].strip()
            key = key.strip('"').strip("'")

            if key:
                return key

            break

    raise ValueError(
        "DeepSeek API key is missing. "
        "Please fill in DEEPSEEK_API_KEY in the .env file."
    )


def get_advice(summary, use_api=False, language="zh"):
    """Generate safe disk organization advice."""

    if language not in ("zh", "en"):
        raise ValueError("Unsupported language")

    safe_summary = {
        "total_files": summary["total_files"],
        "total_size_mb": summary["total_size_mb"],
        "minimum_size_mb": summary["minimum_size_mb"],
        "large_file_count": summary["large_file_count"],
        "file_categories": summary["file_categories"],
    }

    # Local mode does not require an API key.
    if not use_api:
        if language == "zh":
            return (
                "Local analysis completed. "
                "Please review large files before organizing them."
            )

        return (
            "Local analysis completed. "
            "Review large files before organizing them."
        )

    # Read the local key each time AI analysis is requested.
    api_key = load_api_key()

    output_language = (
        "Simplified Chinese"
        if language == "zh"
        else "English"
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful Windows disk organization "
                    "assistant. "
                    f"Respond entirely in {output_language}. "
                    "Use clear and simple language for ordinary users. "
                    "Give five short and practical suggestions. "
                    "Only analyze the provided disk statistics. "
                    "You do not know individual files, names, paths, "
                    "or file contents. Never invent those details. "
                    "Never recommend blindly deleting system files. "
                    "Remind users to review files before deleting "
                    "or moving anything. "
                    "Do not suggest automatic deletion."
                )
            },
            {
                "role": "user",
                "content": (
                    "Analyze these disk statistics and give "
                    "practical organization advice:\n"
                    + json.dumps(
                        safe_summary,
                        ensure_ascii=False
                    )
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
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=40
        ) as response:
            result = json.load(response)

    except urllib.error.HTTPError as error:
        if error.code == 401:
            message = "Invalid DeepSeek API key."
        elif error.code == 402:
            message = "Insufficient DeepSeek account balance."
        elif error.code == 429:
            message = "Too many requests. Please try again later."
        else:
            message = (
                f"DeepSeek API error: HTTP {error.code}"
            )

        raise RuntimeError(message) from error

    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(
            "Cannot connect to DeepSeek. Check your network."
        ) from error

    try:
        advice = result["choices"][0]["message"]["content"]

        if not isinstance(advice, str) or not advice.strip():
            raise ValueError("Empty AI response")

        return advice.strip()

    except (
        KeyError, IndexError, TypeError, ValueError
    ) as error:
        raise RuntimeError(
            "Unexpected DeepSeek response format."
        ) from error


def main():
    parser = argparse.ArgumentParser(
        description="AI disk organization assistant"
    )

    parser.add_argument("report_path")
    parser.add_argument(
        "--min-mb",
        type=float,
        default=100
    )
    parser.add_argument(
        "--api",
        action="store_true"
    )
    parser.add_argument(
        "--language",
        choices=["zh", "en"],
        default="zh"
    )

    args = parser.parse_args()

    try:
        records = parse_report(args.report_path)
        summary = analyze_disk(
            records,
            args.min_mb
        )

        advice = get_advice(
            summary,
            use_api=args.api,
            language=args.language
        )

        print(advice)

    except (
        ValueError, OSError, RuntimeError
    ) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
