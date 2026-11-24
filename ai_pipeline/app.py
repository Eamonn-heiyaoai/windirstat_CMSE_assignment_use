
import argparse
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ai_pipeline.report_parser import parse_report
from ai_pipeline.disk_analyzer import analyze_disk
from ai_pipeline.ai_advisor import get_advice


CATEGORY_NAMES = {
    "video": "视频",
    "audio": "音频",
    "archive": "压缩包",
    "document": "文档",
    "installer": "安装程序",
    "image": "图片",
    "other": "其他文件",
}


def format_size(mib):
    if mib >= 1024:
        return f"{mib / 1024:,.2f} GiB"
    return f"{mib:,.2f} MiB"


class DiskAssistantApp:
    def __init__(self, root, initial_report=None):
        self.root = root
        self.root.title("WinDirStat AI 磁盘整理助手")
        self.root.geometry("850x700")
        self.root.minsize(680, 550)

        self.path = tk.StringVar(value=initial_report or "")
        self.minimum = tk.DoubleVar(value=100)
        self.use_api = tk.BooleanVar(value=False)
        self.messages = queue.Queue()
        self.busy = False

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="AI 磁盘整理助手",
            font=("Microsoft YaHei UI", 19, "bold")
        ).pack(anchor="w")

        ttk.Label(
            frame,
            text="分析磁盘空间使用情况，帮助你安全地整理文件。"
        ).pack(anchor="w", pady=(5, 18))

        # Report source
        source = ttk.LabelFrame(
            frame, text="当前扫描结果", padding=12
        )
        source.pack(fill="x", pady=5)

        ttk.Entry(
            source, textvariable=self.path
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))

        ttk.Button(
            source,
            text="选择报告",
            command=self.browse
        ).pack(side="right")

        # Settings
        settings = ttk.LabelFrame(
            frame, text="分析设置", padding=12
        )
        settings.pack(fill="x", pady=10)

        ttk.Label(
            settings, text="重点关注大于以下大小的文件："
        ).pack(anchor="w")

        setting_row = ttk.Frame(settings)
        setting_row.pack(fill="x", pady=8)

        tk.Scale(
            setting_row,
            from_=0,
            to=2048,
            resolution=10,
            orient="horizontal",
            variable=self.minimum,
            showvalue=False
        ).pack(side="left", fill="x", expand=True)

        ttk.Spinbox(
            setting_row,
            from_=0,
            to=1000000,
            increment=10,
            textvariable=self.minimum,
            width=10
        ).pack(side="left", padx=8)

        ttk.Label(
            setting_row, text="MiB"
        ).pack(side="left")

        ttk.Label(
            settings,
            text="所有文件都会参与统计，此设置只影响重点文件数量。"
        ).pack(anchor="w")

        ttk.Checkbutton(
            settings,
            text="使用 DeepSeek AI 生成建议（需要网络和 API 额度）",
            variable=self.use_api
        ).pack(anchor="w", pady=(12, 0))

        self.button = ttk.Button(
            frame, text="开始分析", command=self.start_analysis
        )
        self.button.pack(fill="x", pady=10)

        # Statistics
        stats = ttk.LabelFrame(
            frame, text="磁盘空间使用情况", padding=12
        )
        stats.pack(fill="both", expand=True, pady=5)

        self.stats_text = tk.Text(
            stats,
            height=12,
            wrap="word",
            font=("Microsoft YaHei UI", 11)
        )
        self.stats_text.pack(fill="both", expand=True)

        # Advice
        advice_frame = ttk.LabelFrame(
            frame, text="整理建议", padding=12
        )
        advice_frame.pack(fill="both", expand=True, pady=5)

        self.advice_text = tk.Text(
            advice_frame,
            height=7,
            wrap="word",
            font=("Microsoft YaHei UI", 11)
        )
        self.advice_text.pack(fill="both", expand=True)

        self.status = tk.StringVar(value="准备就绪")
        ttk.Label(
            frame, textvariable=self.status
        ).pack(anchor="w", pady=(8, 0))

        # Poll results on the main UI thread.
        self.root.after(100, self.check_messages)

    def browse(self):
        filename = filedialog.askopenfilename(
            title="选择磁盘扫描报告",
            filetypes=[
                ("扫描报告", "*.csv *.json"),
                ("所有文件", "*.*")
            ]
        )
        if filename:
            self.path.set(filename)

    def write(self, widget, text):
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)

    def start_analysis(self):
        if self.busy:
            return

        report = self.path.get().strip()

        if not report:
            messagebox.showwarning(
                "提示", "请先选择扫描报告。"
            )
            return

        try:
            minimum = self.minimum.get()
            if not 0 <= minimum <= 1000000:
                raise ValueError()
        except (ValueError, tk.TclError):
            messagebox.showerror(
                "参数错误", "请输入有效的最小文件大小。"
            )
            return

        self.busy = True
        self.button.config(state="disabled")
        self.status.set("正在分析，请稍候……")
        self.write(self.stats_text, "")
        self.write(self.advice_text, "")

        threading.Thread(
            target=self.worker,
            args=(report, minimum, self.use_api.get()),
            daemon=True
        ).start()

    def worker(self, report, minimum, use_api):
        try:
            records = parse_report(report)
            summary = analyze_disk(records, minimum)
            advice = get_advice(summary, use_api=use_api)
            self.messages.put(("success", summary, advice, use_api))
        except Exception as error:
            self.messages.put(("error", str(error)))

    def check_messages(self):
        try:
            while True:
                result = self.messages.get_nowait()

                if result[0] == "success":
                    _, summary, advice, use_api = result
                    self.show_results(summary, advice, use_api)
                else:
                    self.status.set("分析失败")
                    messagebox.showerror("分析失败", result[1])

                self.busy = False
                self.button.config(state="normal")

        except queue.Empty:
            pass

        self.root.after(100, self.check_messages)

    def show_results(self, summary, advice, use_api):
        lines = [
            f"已分析文件：{summary['total_files']:,} 个",
            f"文件总大小：{format_size(summary['total_size_mb'])}",
            "",
            f"重点关注文件：{summary['large_file_count']:,} 个",
            f"（大小不低于 {summary['minimum_size_mb']:g} MiB 的非空文件）",
            "",
            "各类文件占用情况：",
            ""
        ]

        categories = summary["file_categories"]

        if not categories:
            lines.append("没有可统计的文件。")

        for category, info in categories.items():
            name = CATEGORY_NAMES.get(category, category)
            lines.append(
                f"{name}：{format_size(info['size_mb'])}"
                f"  |  {info['count']:,} 个"
                f"  |  占 {info['percentage']:.1f}%"
            )

        self.write(self.stats_text, "\n".join(lines))

        if use_api:
            self.write(self.advice_text, advice)
        else:
            local_advice = (
                "本地分析已完成。\n\n"
                "建议优先查看占用空间较大的文件类型，"
                "再结合上方的重点文件数量，决定哪些文件值得检查。\n\n"
                "删除或移动任何文件前，请先确认它是否仍然需要。"
                "\n\n当前未连接 AI，以上是本地规则提示。"
            )
            self.write(self.advice_text, local_advice)

        self.status.set("分析完成")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "report_path", nargs="?", default=None
    )
    args = parser.parse_args()

    root = tk.Tk()
    app = DiskAssistantApp(root, args.report_path)
    root.mainloop()


if __name__ == "__main__":
    main()
