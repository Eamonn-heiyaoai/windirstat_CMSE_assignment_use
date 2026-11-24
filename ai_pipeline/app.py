import argparse
import queue
import re
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ai_pipeline.report_parser import parse_report
from ai_pipeline.disk_analyzer import analyze_disk
from ai_pipeline.ai_advisor import get_advice

BG = "#f4f7fb"
WHITE = "#ffffff"
INK = "#17253d"
MUTED = "#64748b"
BLUE = "#2563eb"
BORDER = "#e0e7ef"
TRACK = "#e8eef7"

TEXT = {
    "zh": {
        "title": "AI 磁盘整理助手", "subtitle": "看懂空间占用，安心整理文件",
        "source": "扫描报告", "browse": "选择文件", "source_hint": "从 WinDirStat 打开时自动填写；也可以分析以前导出的 CSV / JSON。",
        "settings": "分析设置", "threshold": "重点关注的文件大小下限", "threshold_hint": "下限只影响重点文件数量；全部文件始终参与统计。",
        "api": "使用 DeepSeek 生成 AI 建议（将发送匿名汇总统计，不发送文件名和路径）",
        "run": "开始分析", "summary": "扫描结果", "advice": "整理建议",
        "idle": "选择报告并设置参数，然后点击“开始分析”。", "ready": "准备就绪",
        "running": "正在分析……", "done": "分析完成", "failed": "分析出现问题",
        "empty_path": "请先选择扫描报告。", "invalid": "请输入有效的文件大小（0 到 1000000 MiB）。",
        "files": "文件总数", "size": "文件总大小", "priority": "重点关注文件",
        "categories": "不同类型占用空间", "category_count": "个", "no_files": "没有可统计的文件。",
        "general": "本地分析已完成。建议优先检查占用最多的文件类型，确认用途后再考虑归档或转移。不要随意删除系统文件。\n\n当前未启用 AI；程序不会自动删除或移动文件。",
        "ai_wait": "AI 请求正在处理……", "ai_error": "AI 建议暂时无法生成：", "retry": "语言已切换。请重新点击“开始分析”，生成该语言的 AI 建议。",
        "browse_title": "选择扫描报告", "file_type": "CSV / JSON 报告",
        "status": "状态", "local": "本地建议", "real_ai": "DeepSeek AI 建议", "report_missing": "扫描报告不存在，请重新从 WinDirStat 打开 AI Analysis，或手动选择报告。",
    },
    "en": {
        "title": "AI Disk Organization Assistant", "subtitle": "Understand disk usage and organize files safely",
        "source": "Scan report", "browse": "Choose file", "source_hint": "The report is filled in automatically from WinDirStat; previous CSV / JSON exports also work.",
        "settings": "Analysis settings", "threshold": "Minimum size of priority files", "threshold_hint": "This only changes the priority count. All files are included in statistics.",
        "api": "Use DeepSeek AI (only anonymous statistics are sent; no file names or paths)",
        "run": "Analyze", "summary": "Scan summary", "advice": "Organization advice",
        "idle": "Choose a report and settings, then click Analyze.", "ready": "Ready",
        "running": "Analyzing...", "done": "Analysis complete", "failed": "Analysis encountered a problem",
        "empty_path": "Please select a scan report.", "invalid": "Enter a valid file size (0 to 1000000 MiB).",
        "files": "Files analyzed", "size": "Total file size", "priority": "Priority files",
        "categories": "Storage by file type", "category_count": "files", "no_files": "No files available for analysis.",
        "general": "Local analysis is complete. Start by reviewing the file categories taking the most space. Check their purpose before archiving or moving files. Never delete system files without understanding what they do.\n\nAI is disabled. This app never automatically deletes or moves files.",
        "ai_wait": "Waiting for the AI response...", "ai_error": "AI advice could not be generated: ", "retry": "Language changed. Click Analyze again to generate AI advice in this language.",
        "browse_title": "Choose scan report", "file_type": "CSV / JSON reports",
        "status": "Status", "local": "Local suggestions", "real_ai": "DeepSeek AI advice", "report_missing": "The report is no longer available. Open AI Analysis again from WinDirStat, or choose another report.",
    },
}
CATEGORY = {
    "zh": {"video": "视频", "audio": "音频", "archive": "压缩包", "document": "文档", "installer": "安装程序", "image": "图片", "other": "其他"},
    "en": {"video": "Video", "audio": "Audio", "archive": "Archives", "document": "Documents", "installer": "Installers", "image": "Images", "other": "Other"},
}


def size_label(mib):
    if mib >= 1024 * 1024:
        return f"{mib / (1024 * 1024):,.2f} TiB"
    if mib >= 1024:
        return f"{mib / 1024:,.2f} GiB"
    return f"{mib:,.2f} MiB"


def is_windirstat_temp(path):
    """A narrow check; only applied to the path passed at startup."""
    try:
        p = Path(path).resolve()
        return (p.parent == Path(tempfile.gettempdir()).resolve()
                and re.fullmatch(r"WDA[0-9a-f]{4}\.json", p.name, re.IGNORECASE) is not None)
    except (OSError, ValueError):
        return False


def remove_temp_file(path):
    if path and is_windirstat_temp(path):
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass


class DiskAssistantApp:
    def __init__(self, root, initial_report=None):
        self.root = root
        self.root.geometry("900x760")
        self.root.minsize(680, 500)
        self.root.configure(bg=BG)

        self.path = tk.StringVar(value=initial_report or "")
        self.minimum = tk.DoubleVar(value=100)
        self.use_api = tk.BooleanVar(value=False)
        self.language = tk.StringVar(value="中文")
        self.status = tk.StringVar()
        self.messages = queue.Queue()
        self.busy = False
        self.cached_path = None
        self.cached_records = None
        self.initial_temp = str(Path(initial_report).resolve()) if initial_report and is_windirstat_temp(initial_report) else None
        self.last_summary = None
        self.last_advice = None
        self.last_ai = False
        self.last_result_language = "zh"
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 11, "bold"),
                        background=BLUE, foreground=WHITE, padding=(16, 10), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#1d4ed8"), ("disabled", "#a1b6dc")])
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=5)
        style.configure("Horizontal.TProgressbar", troughcolor=TRACK, background=BLUE,
                        bordercolor=TRACK, lightcolor=BLUE, darkcolor=BLUE, thickness=9)

        outer = tk.Frame(root, bg=BG)
        outer.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.page = tk.Frame(self.canvas, bg=BG, padx=24, pady=20)
        self.page_id = self.canvas.create_window((0, 0), window=self.page, anchor="nw")
        self.page.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.page_id, width=e.width))
        self.root.bind_all("<MouseWheel>", self.scroll_page)

        header = tk.Frame(self.page, bg=BG)
        header.pack(fill="x", pady=(0, 8))
        self.title_label = tk.Label(header, bg=BG, fg=INK, font=("Microsoft YaHei UI", 21, "bold"))
        self.title_label.pack(side="left")
        self.language_box = ttk.Combobox(header, textvariable=self.language,
                                         values=["中文", "English"], state="readonly", width=11)
        self.language_box.pack(side="right", pady=8)
        self.language_box.bind("<<ComboboxSelected>>", self.change_language)
        self.subtitle_label = tk.Label(self.page, bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 10))
        self.subtitle_label.pack(anchor="w", pady=(0, 16))

        source = self.card()
        self.source_title = self.heading(source)
        file_row = tk.Frame(source, bg=WHITE)
        file_row.pack(fill="x", pady=(8, 5))
        self.path_entry = ttk.Entry(file_row, textvariable=self.path)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.browse_btn = ttk.Button(file_row, command=self.browse)
        self.browse_btn.pack(side="right")
        self.source_hint = self.muted(source)

        settings = self.card()
        self.settings_title = self.heading(settings)
        setting_row = tk.Frame(settings, bg=WHITE)
        setting_row.pack(fill="x", pady=(12, 4))
        self.threshold_title = tk.Label(setting_row, bg=WHITE, fg=INK,
                                        font=("Microsoft YaHei UI", 10))
        self.threshold_title.pack(side="left")
        control_row = tk.Frame(settings, bg=WHITE)
        control_row.pack(fill="x", pady=(4, 7))
        self.scale = tk.Scale(control_row, from_=0, to=2048, resolution=10,
                              orient="horizontal", variable=self.minimum, showvalue=False,
                              bg=WHITE, highlightthickness=0, bd=0, troughcolor=TRACK,
                              activebackground=BLUE)
        self.scale.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.spinbox = ttk.Spinbox(control_row, from_=0, to=1000000, increment=10,
                                   textvariable=self.minimum, width=9)
        self.spinbox.pack(side="left")
        tk.Label(control_row, text="MiB", bg=WHITE, fg=MUTED).pack(side="left", padx=(6, 0))
        self.threshold_hint = self.muted(settings)
        self.api_box = tk.Checkbutton(
    		settings,
   	 	variable=self.use_api,
    		bg=WHITE,
    		fg=INK,
    		activebackground=WHITE,
    		activeforeground=INK,
    		selectcolor=WHITE,
   	 	font=("Microsoft YaHei UI", 10),
    		anchor="w"
		)
        self.api_box.pack(anchor="w", pady=(12, 0))
        self.run_button = ttk.Button(self.page, style="Accent.TButton", command=self.start_analysis)
        self.run_button.pack(fill="x", pady=(2, 12))
        self.status_label = tk.Label(self.page, textvariable=self.status, bg=BG, fg=MUTED,
                                     font=("Microsoft YaHei UI", 10), anchor="w")
        self.status_label.pack(fill="x", pady=(0, 12))

        stats = self.card()
        self.summary_title = self.heading(stats)
        metrics = tk.Frame(stats, bg=WHITE)
        metrics.pack(fill="x", pady=(12, 16))
        self.metric_labels = []
        for index in range(3):
            c = tk.Frame(metrics, bg="#eff5ff", padx=12, pady=12)
            c.pack(side="left", fill="both", expand=True, padx=(0 if index == 0 else 5, 0))
            name = tk.Label(c, bg="#eff5ff", fg=MUTED, font=("Microsoft YaHei UI", 9))
            name.pack(anchor="w")
            value = tk.Label(c, text="—", bg="#eff5ff", fg=INK,
                             font=("Microsoft YaHei UI", 15, "bold"))
            value.pack(anchor="w", pady=(7, 0))
            self.metric_labels.append((name, value))
        self.categories_title = tk.Label(stats, bg=WHITE, fg=INK,
                                         font=("Microsoft YaHei UI", 11, "bold"))
        self.categories_title.pack(anchor="w", pady=(0, 8))
        self.categories_frame = tk.Frame(stats, bg=WHITE)
        self.categories_frame.pack(fill="x")
        self.no_results = tk.Label(self.categories_frame, bg=WHITE, fg=MUTED)
        self.no_results.pack(anchor="w", pady=5)

        advice_card = self.card()
        self.advice_title = self.heading(advice_card)
        self.advice_body = tk.Label(advice_card, bg=WHITE, fg=INK, justify="left",
                                    anchor="nw", font=("Microsoft YaHei UI", 10),
                                    wraplength=760, text="", pady=12)
        self.advice_body.pack(fill="x")
        self.advice_card = advice_card
        self.advice_card.bind("<Configure>", self.resize_advice)

        self.apply_language()
        self.root.after(100, self.check_messages)

    def card(self):
        frame = tk.Frame(self.page, bg=WHITE, highlightbackground=BORDER,
                         highlightthickness=1, padx=17, pady=15)
        frame.pack(fill="x", pady=(0, 12))
        return frame

    def heading(self, parent):
        label = tk.Label(parent, bg=WHITE, fg=INK,
                         font=("Microsoft YaHei UI", 12, "bold"))
        label.pack(anchor="w")
        return label

    def muted(self, parent):
        label = tk.Label(parent, bg=WHITE, fg=MUTED,
                         font=("Microsoft YaHei UI", 9), anchor="w", justify="left")
        label.pack(anchor="w")
        return label

    def lang(self):
        return "zh" if self.language.get() == "中文" else "en"

    def tr(self, key):
        return TEXT[self.lang()][key]

    def apply_language(self):
        self.root.title(self.tr("title"))
        for widget, key in [
            (self.title_label, "title"), (self.subtitle_label, "subtitle"),
            (self.source_title, "source"), (self.browse_btn, "browse"),
            (self.source_hint, "source_hint"), (self.settings_title, "settings"),
            (self.threshold_title, "threshold"), (self.threshold_hint, "threshold_hint"),
            (self.api_box, "api"), (self.run_button, "run"),
            (self.summary_title, "summary"), (self.categories_title, "categories"),
            (self.advice_title, "advice")
        ]:
            widget.configure(text=self.tr(key))
        for (name, _), key in zip(self.metric_labels, ["files", "size", "priority"]):
            name.configure(text=self.tr(key))
        if not self.busy:
            self.status.set(self.tr("ready"))
        if self.last_summary is None:
            self.no_results.configure(text=self.tr("idle"))
            self.advice_body.configure(text=self.tr("idle"))
        else:
            self.render_summary(self.last_summary)
            self.render_advice()

    def change_language(self, _event=None):
        self.apply_language()

    def browse(self):
        path = filedialog.askopenfilename(
            title=self.tr("browse_title"),
            filetypes=[(self.tr("file_type"), "*.csv *.json"), ("All files", "*.*")]
        )
        if path:
            self.path.set(path)

    def start_analysis(self):
        if self.busy:
            return
        path = self.path.get().strip()
        if not path:
            messagebox.showwarning(self.tr("source"), self.tr("empty_path"))
            return
        try:
            minimum = self.minimum.get()
            if not 0 <= minimum <= 1000000:
                raise ValueError()
        except (ValueError, tk.TclError):
            messagebox.showerror(self.tr("settings"), self.tr("invalid"))
            return
        self.busy = True
        self.run_button.configure(state="disabled")
        self.status.set(self.tr("running"))
        self.advice_body.configure(text=self.tr("ai_wait"))
        threading.Thread(target=self.worker,
                         args=(path, minimum, self.use_api.get(), self.lang()),
                         daemon=True).start()

    def worker(self, path, minimum, use_api, language):
        try:
            resolved = str(Path(path).resolve())
            if resolved == self.cached_path and self.cached_records is not None:
                records = self.cached_records
            else:
                try:
                    records = parse_report(path)
                finally:
                    if resolved == self.initial_temp:
                        remove_temp_file(path)
                self.cached_path = resolved
                self.cached_records = records
            summary = analyze_disk(records, minimum)
        except Exception as exc:
            self.messages.put(("error", str(exc)))
            return

        try:
            advice = get_advice(summary, use_api=use_api, language=language)
            self.messages.put(("success", summary, advice, None, use_api, language))
        except Exception as exc:
            # The local statistics remain useful even when the API is unavailable.
            self.messages.put(("success", summary, None, str(exc), use_api, language))

    def check_messages(self):
        try:
            while True:
                item = self.messages.get_nowait()
                if item[0] == "error":
                    self.status.set(self.tr("failed"))
                    self.advice_body.configure(text=item[1])
                    messagebox.showerror(self.tr("failed"), item[1])
                else:
                    _, summary, advice, error, is_ai, request_language = item
                    self.last_summary = summary
                    self.last_advice = advice if error is None else error
                    self.last_error = error is not None
                    self.last_ai = is_ai
                    self.last_result_language = request_language
                    self.render_summary(summary)
                    self.render_advice()
                    self.status.set(self.tr("done") if error is None else self.tr("failed"))
                self.busy = False
                self.run_button.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self.check_messages)

    def render_summary(self, summary):
        for (_, value), new in zip(self.metric_labels, [
            f"{summary['total_files']:,}",
            size_label(summary["total_size_mb"]),
            f"{summary['large_file_count']:,}"
        ]):
            value.configure(text=new)
        for child in self.categories_frame.winfo_children():
            child.destroy()
        cats = summary["file_categories"]
        if not cats:
            tk.Label(self.categories_frame, text=self.tr("no_files"),
                     bg=WHITE, fg=MUTED).pack(anchor="w")
            return
        for key, info in cats.items():
            name = CATEGORY[self.lang()].get(key, key)
            row = tk.Frame(self.categories_frame, bg=WHITE)
            row.pack(fill="x", pady=(0, 12))
            top = tk.Frame(row, bg=WHITE)
            top.pack(fill="x")
            tk.Label(top, text=f"{name}  ·  {info['count']:,} {self.tr('category_count')}",
                     bg=WHITE, fg=INK, font=("Microsoft YaHei UI", 10)).pack(side="left")
            tk.Label(top, text=f"{size_label(info['size_mb'])}  ({info['percentage']:.1f}%)",
                     bg=WHITE, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(side="right")
            ttk.Progressbar(row, orient="horizontal", mode="determinate",
                            maximum=100, value=max(0, min(100, info["percentage"]))).pack(fill="x", pady=(5, 0))

    def render_advice(self):
        if not self.last_ai:
            content = self.tr("general")
        elif self.lang() != self.last_result_language:
            content = self.tr("retry")
        elif getattr(self, "last_error", False):
            content = self.tr("ai_error") + (self.last_advice or "")
        else:
            content = self.last_advice or ""
        self.advice_body.configure(text=content)

    def resize_advice(self, event):
        self.advice_body.configure(wraplength=max(250, event.width - 70))

    def scroll_page(self, event):
        if self.canvas.winfo_height() < self.page.winfo_height():
            self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def close(self):
        if self.initial_temp:
            remove_temp_file(self.initial_temp)
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report_path", nargs="?", default=None)
    args = parser.parse_args()
    root = tk.Tk()
    DiskAssistantApp(root, args.report_path)
    root.mainloop()


if __name__ == "__main__":
    main()
