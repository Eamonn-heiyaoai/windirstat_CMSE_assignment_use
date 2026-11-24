
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

from ai_pipeline.report_parser import parse_report
from ai_pipeline.disk_analyzer import analyze_disk


API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-flash"

CONFIG_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_api_key():
    """Read the API key from the local .env file."""

    if not CONFIG_FILE.is_file():
        raise ValueError(
            "Missing .env file. Copy .env.example to .env "
            "and configure your API key."
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

    raise ValueError(
        "DeepSeek API key is missing. "
        "Please fill in DEEPSEEK_API_KEY in .env."
    )


def prepare_ai_summary(summary):
    """
    Prepare anonymous statistics for DeepSeek.

    No original file names, paths or contents are included.
    """

    return {
        "total_files": summary["total_files"],
        "total_size_mb": summary["total_size_mb"],
        "minimum_size_mb": summary["minimum_size_mb"],
        "large_file_count": summary["large_file_count"],

        "large_file_total_mb": summary.get(
            "large_file_total_mb", 0
        ),
        "large_file_percentage": summary.get(
            "large_file_percentage", 0
        ),

        "file_categories": summary["file_categories"],

        "top_extensions": summary.get(
            "top_extensions", []
        )[:20],

        "size_distribution": summary.get(
            "size_distribution", {}
        ),

        "top_large_files": summary.get(
            "top_large_files", []
        )[:15]
    }


def get_advice(summary, use_api=False, language="zh"):
    """Generate detailed and cautious disk organization advice."""

    if language not in ("zh", "en"):
        raise ValueError("Unsupported language")

    safe_summary = prepare_ai_summary(summary)

    # Local mode: no network request is sent.
    if not use_api:
        if language == "zh":
            return (
                "本地统计已完成。\n\n"
                "建议先查看占用空间最大的文件类型，"
                "并结合大文件数量决定检查顺序。\n\n"
                "不要仅凭文件扩展名或大小判断文件是否"
                "可以删除，尤其需要谨慎处理系统文件。"
            )

        return (
            "Local analysis is complete.\n\n"
            "Review the file types using the most storage space "
            "and prioritize large files.\n\n"
            "Do not assume a file is safe to delete based only "
            "on its extension or size."
        )

    api_key = load_api_key()

    output_language = (
        "Simplified Chinese"
        if language == "zh"
        else "English"
    )

    system_prompt = (
        "You are a professional Windows disk organization assistant. "
        f"Write entirely in {output_language}. "
        "Your audience consists of ordinary computer users "
        "with little technical knowledge. "
        "Use friendly, clear, practical language. "

        "The input contains anonymous disk scan statistics: "
        "file counts, total sizes, categories, extension rankings, "
        "file size distribution, and large-file metadata. "

        "Analyze all available statistics carefully. "
        "Prioritize findings by storage impact. "
        "Explain which types occupy the most space, "
        "what these file types commonly represent, "
        "and what the user should check first. "

        "Provide an organized report with: "
        "1. A brief overall storage assessment. "
        "2. Three to five important findings with numbers. "
        "3. A prioritized list of practical review steps. "
        "4. Warnings about files that may be important "
        "to Windows, installed applications, or user data. "

        "Use the actual numbers provided, with sensible rounding. "
        "Use GiB for large sizes and MiB for smaller sizes. "
        "Do not invent statistics. "
        "Do not treat all files in a category as disposable. "
        "Extensions only indicate possible file types. "
        "A file's size alone cannot establish whether it is safe "
        "or useful to delete. "

        "You do not know exact file names, locations, contents, "
        "or whether an application currently uses a file. "
        "Never invent these details. "
        "Never say that a particular file is safe to delete. "
        "Never recommend automatically deleting or moving files. "
        "Always ask the user to confirm a file's purpose "
        "before modifying it. "

        "Avoid generic advice when the available statistics "
        "support a more specific observation. "
        "Keep the report useful rather than excessively long. "
        "Use plain text, numbered points and short paragraphs. "
        "Do not use Markdown symbols such as **, # or tables."
    )

    user_prompt = (
        "Please analyze my Windows disk scan report.\n\n"
        "I want to understand:\n"
        "- What is taking up the most space?\n"
        "- Which file types and extensions deserve attention?\n"
        "- How are large files distributed?\n"
        "- What should I inspect first to organize storage safely?\n"
        "- Which types require extra caution?\n\n"
        "Here are the anonymous statistics:\n"
        + json.dumps(
            safe_summary,
            ensure_ascii=False,
            indent=2
        )
    )

    payload = {
        "model": MODEL_NAME,
        "thinking": {
            "type": "disabled"
        },
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "max_tokens": 2500,
        "stream": False
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            payload,
            ensure_ascii=False
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=90
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
            message = f"DeepSeek API error: HTTP {error.code}"

        raise RuntimeError(message) from error

    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(
            "Cannot connect to DeepSeek. Check your network."
        ) from error

    try:
        choices = result.get("choices", [])

        if not choices:
            raise RuntimeError(
                "DeepSeek returned no answer choices."
            )

        choice = choices[0]
        finish_reason = choice.get(
            "finish_reason", "unknown"
        )

        message = choice.get("message") or {}
        content = message.get("content")

        if isinstance(content, str) and content.strip():
            return content.strip()

        if finish_reason == "length":
            raise RuntimeError(
                "DeepSeek output exceeded the token limit. "
                "Please try again."
            )

        raise RuntimeError(
            "DeepSeek returned an empty answer "
            f"(finish_reason={finish_reason})."
        )

    except (AttributeError, TypeError) as error:
        raise RuntimeError(
            "Unexpected DeepSeek response structure."
        ) from error


def main():
    parser = argparse.ArgumentParser(
        description="Detailed AI Disk Organization Assistant"
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

    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
