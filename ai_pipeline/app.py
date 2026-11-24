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
from ai_pipeline.ai_advisor import (
    ONLINE_NOTICE, VISIBLE_SUGGESTIONS, format_cleanup_advice, format_online_item,
    get_cleanup_guide, get_online_suggestions, ranked_suggestions, size_label, suggestion_page,
)
from ai_pipeline.installed_apps import read_installed_apps, uninstall_suggestions

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
        "api": "使用 DeepSeek 在线识别（需确认发送目录摘要）",
        "api_consent": "确认发送目录摘要",
        "guide_consent": "确认请求清理指导",
        "guide_notice": "将把这一项的脱敏目录名称、占用和建议类型发给 DeepSeek。\n\n{directory}\n\n目录名称仍可能透露软件或个人信息。请核对 AI 指导，再决定是否清理。",
        "guide": "查看清理步骤", "guide_hide": "收起指导", "guide_loading": "正在生成指导……",
        "guide_error": "暂时无法生成指导。可以再次请求。",
        "guide_verify": "先核实用途", "guide_steps": "清理步骤",
        "guide_impact": "处理前请留意",
        "run": "开始分析", "summary": "扫描结果", "advice": "清理建议",
        "idle": "选择报告并设置参数，然后点击“开始分析”。", "ready": "准备就绪",
        "running": "正在分析……", "failed": "分析出现问题",
        "running_local": "正在分析 · 仅本地", "running_ai": "正在分析 · 已启用 DeepSeek",
        "done_local": "分析完成 · 已显示本地建议", "done_ai": "分析完成 · 已显示 DeepSeek 识别结果",
        "empty_path": "请先选择扫描报告。", "invalid": "请输入有效的文件大小（0 到 1000000 MiB）。",
        "files": "文件总数", "size": "文件总大小", "priority": "重点关注文件",
        "categories": "不同类型占用空间", "category_count": "个", "no_files": "没有可统计的文件。",
        "ai_error": "在线识别暂不可用，已显示本地建议。",
        "advice_count": "共 {count} 项",
        "previous": "上一页", "next": "下一页", "page": "第 {current} / {total} 页",
        "expand": "展开全部", "collapse": "返回分页", "all_items": "已展开全部",
        "browse_title": "选择扫描报告", "file_type": "CSV / JSON 报告",
        "status": "状态", "local": "本地建议", "real_ai": "DeepSeek AI 建议", "report_missing": "扫描报告不存在，请重新从 WinDirStat 打开 AI Analysis，或手动选择报告。",
    },
    "en": {
        "title": "AI Disk Organization Assistant", "subtitle": "Understand disk usage and organize files safely",
        "source": "Scan report", "browse": "Choose file", "source_hint": "The report is filled in automatically from WinDirStat; previous CSV / JSON exports also work.",
        "settings": "Analysis settings", "threshold": "Minimum size of priority files", "threshold_hint": "This only changes the priority count. All files are included in statistics.",
        "api": "Use DeepSeek for online detection (confirm before sending directory summaries)",
        "api_consent": "Confirm sending directory summaries",
        "guide_consent": "Confirm requesting cleanup guidance",
        "guide_notice": "Send this item's redacted directory name, size and review type to DeepSeek?\n\n{directory}\n\nThe directory name may reveal software or personal information. Check the guidance before acting.",
        "guide": "View cleanup steps", "guide_hide": "Hide guidance", "guide_loading": "Getting guidance…",
        "guide_error": "Guidance is unavailable. You can request it again.",
        "guide_verify": "Check what is in this folder", "guide_steps": "Cleanup steps",
        "guide_impact": "Before you proceed",
        "run": "Analyze", "summary": "Scan summary", "advice": "Cleanup suggestions",
        "idle": "Choose a report and settings, then click Analyze.", "ready": "Ready",
        "running": "Analyzing...", "failed": "Analysis encountered a problem",
        "running_local": "Analyzing locally", "running_ai": "Analyzing with DeepSeek enabled",
        "done_local": "Analysis complete · Showing local suggestions",
        "done_ai": "Analysis complete · Showing DeepSeek findings",
        "empty_path": "Please select a scan report.", "invalid": "Enter a valid file size (0 to 1000000 MiB).",
        "files": "Files analyzed", "size": "Total file size", "priority": "Priority files",
        "categories": "Storage by file type", "category_count": "files", "no_files": "No files available for analysis.",
        "ai_error": "Online detection is unavailable. Showing local suggestions.",
        "advice_count": "{count} items",
        "previous": "Previous", "next": "Next", "page": "Page {current} of {total}",
        "expand": "Expand all", "collapse": "Return to pages", "all_items": "Showing all",
        "browse_title": "Choose scan report", "file_type": "CSV / JSON reports",
        "status": "Status", "local": "Local suggestions", "real_ai": "DeepSeek AI advice", "report_missing": "The report is no longer available. Open AI Analysis again from WinDirStat, or choose another report.",
    },
}
CATEGORY = {
    "zh": {"video": "视频", "audio": "音频", "archive": "压缩包", "document": "文档", "installer": "安装程序", "image": "图片", "other": "其他"},
    "en": {"video": "Video", "audio": "Audio", "archive": "Archives", "document": "Documents", "installer": "Installers", "image": "Images", "other": "Other"},
}


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
    def __init__(self, root, initial_report=None, *, live_scan=False):
        self.root = root
        self.root.geometry("900x760")
        self.root.minsize(680, 500)
        self.root.configure(bg=BG)

        self.path = tk.StringVar(value=initial_report or "")
        self.minimum = tk.DoubleVar(value=100)
        self.use_api = tk.BooleanVar(value=False)
        self.language = tk.StringVar(value="中文")
        self.status = tk.StringVar()
        self.status_key = "ready"
        self.messages = queue.Queue()
        self.busy = False
        self.cached_path = None
        self.cached_records = None
        self.initial_temp = str(Path(initial_report).resolve()) if initial_report and is_windirstat_temp(initial_report) else None
        self.live_report = self.initial_temp if live_scan else None
        self.last_summary = None
        self.last_ai_error = None
        self.last_result_language = "zh"
        self.advice_expanded = False
        self.advice_page = 0
        self.guides = {}
        self.open_guides = set()
        self.guide_failures = set()
        self.pending_guide = None
        self.guide_labels = []
        self.advice_wrap = 760
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
        advice_card.pack_configure(before=stats)
        self.advice_title = self.heading(advice_card)
        self.advice_nav = tk.Frame(advice_card, bg=WHITE)
        self.advice_previous = ttk.Button(self.advice_nav, command=lambda: self.change_advice_page(-1))
        self.advice_previous.pack(side="left")
        self.advice_page_label = tk.Label(self.advice_nav, bg=WHITE, fg=MUTED)
        self.advice_page_label.pack(side="left", padx=8)
        self.advice_next = ttk.Button(self.advice_nav, command=lambda: self.change_advice_page(1))
        self.advice_next.pack(side="left")
        self.advice_toggle = ttk.Button(self.advice_nav, command=self.toggle_advice)
        self.advice_toggle.pack(side="left", padx=(12, 0))
        self.online_rows = tk.Frame(advice_card, bg=WHITE)
        self.online_rows.pack(fill="x")
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

    def set_status(self, key):
        self.status_key = key
        self.status.set(self.tr(key))

    def apply_language(self):
        self.root.title(self.tr("title"))
        for widget, key in [
            (self.title_label, "title"), (self.subtitle_label, "subtitle"),
            (self.source_title, "source"), (self.browse_btn, "browse"),
            (self.source_hint, "source_hint"), (self.settings_title, "settings"),
            (self.threshold_title, "threshold"), (self.threshold_hint, "threshold_hint"),
            (self.api_box, "api"), (self.run_button, "run"),
            (self.summary_title, "summary"), (self.categories_title, "categories"),
            (self.advice_title, "advice"), (self.advice_previous, "previous"),
            (self.advice_next, "next")
        ]:
            widget.configure(text=self.tr(key))
        for (name, _), key in zip(self.metric_labels, ["files", "size", "priority"]):
            name.configure(text=self.tr(key))
        self.set_status(self.status_key)
        if self.last_summary is None:
            if self.no_results.winfo_exists():
                self.no_results.configure(text=self.tr("idle"))
            self.advice_body.configure(text=self.tr("running" if self.busy else "idle"))
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
        if self.busy or self.pending_guide is not None:
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
        language = self.lang()
        use_api = self.use_api.get()
        if use_api:
            use_api = messagebox.askyesno(
                self.tr("api_consent"), ONLINE_NOTICE[language],
                icon=messagebox.WARNING, default=messagebox.NO, parent=self.root,
            )
            if not use_api:
                self.use_api.set(False)
        self.busy = True
        self.last_summary = None
        self.last_ai_error = None
        self.advice_expanded = False
        self.advice_page = 0
        self.guides.clear()
        self.open_guides.clear()
        self.guide_failures.clear()
        self.render_online_rows([])
        self.advice_nav.pack_forget()
        self.advice_title.configure(text=self.tr("advice"))
        self.run_button.configure(state="disabled")
        self.api_box.configure(state="disabled")
        self.set_status("running_ai" if use_api else "running_local")
        self.advice_body.configure(text=self.tr("running"))
        threading.Thread(target=self.worker,
                         args=(path, minimum, use_api, language),
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
            if resolved == self.live_report:
                try:
                    apps = read_installed_apps()
                except OSError:
                    apps = []
                summary["uninstall_items"] = uninstall_suggestions(records, apps)
        except Exception as exc:
            self.messages.put(("error", str(exc)))
            return

        self.messages.put(("local", summary))
        try:
            online_items = get_online_suggestions(records, language, confirmed=use_api)
            self.messages.put(("complete", online_items, None, language))
        except Exception as exc:
            self.messages.put(("complete", None, str(exc), language))

    def check_messages(self):
        try:
            while True:
                item = self.messages.get_nowait()
                if item[0] == "local":
                    self.last_summary = item[1]
                    self.render_summary(self.last_summary)
                    self.render_advice()
                    continue
                if item[0] == "guide":
                    _, key, guide = item
                    self.pending_guide = None
                    if guide is None:
                        self.guide_failures.add(key)
                    else:
                        self.guides[key] = guide
                        self.open_guides.add(key)
                    self.run_button.configure(state="normal")
                    self.render_advice()
                    continue
                if item[0] == "error":
                    self.set_status("failed")
                    self.advice_body.configure(text=item[1])
                    messagebox.showerror(self.tr("failed"), item[1])
                else:
                    _, online_items, error, request_language = item
                    if online_items:
                        self.last_summary["online_items"] = online_items
                    self.last_ai_error = error
                    self.last_result_language = request_language
                    self.render_advice()
                    self.set_status("done_ai" if online_items else "done_local")
                self.busy = False
                self.run_button.configure(state="normal")
                self.api_box.configure(state="normal")
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
        items = ranked_suggestions(self.last_summary)
        item_count = len(items)
        total_pages = (item_count + VISIBLE_SUGGESTIONS - 1) // VISIBLE_SUGGESTIONS
        self.advice_page = min(self.advice_page, max(0, total_pages - 1))
        visible = suggestion_page(items, self.advice_expanded, self.advice_page)
        self.render_online_rows([item for item, source in visible if source == "online"])
        content = format_cleanup_advice(
            self.last_summary, self.lang(),
            expanded=self.advice_expanded, page=self.advice_page, include_online=False,
        )
        if self.last_ai_error is not None:
            content += f"\n\n{self.tr('ai_error')}\n{self.last_ai_error}"
        self.advice_body.configure(text=content)
        count = self.tr("advice_count").format(count=item_count)
        self.advice_title.configure(text=f"{self.tr('advice')} · {count}")
        if total_pages > 1:
            paged = not self.advice_expanded
            page_label = self.tr("page").format(current=self.advice_page + 1, total=total_pages)
            self.advice_page_label.configure(text=page_label if paged else self.tr("all_items"))
            self.advice_previous.configure(state="normal" if paged and self.advice_page > 0 else "disabled")
            self.advice_next.configure(state="normal" if paged and self.advice_page + 1 < total_pages else "disabled")
            self.advice_toggle.configure(text=self.tr("expand" if paged else "collapse"))
            self.advice_nav.pack(anchor="w", pady=(8, 0), before=self.online_rows)
        else:
            self.advice_nav.pack_forget()

    def render_online_rows(self, items):
        for child in self.online_rows.winfo_children():
            child.destroy()
        self.guide_labels.clear()
        language = self.lang()
        for item in items:
            key = (item["id"], language)
            row = tk.Frame(self.online_rows, bg=WHITE, highlightbackground=BORDER,
                           highlightthickness=1, padx=12, pady=10)
            row.pack(fill="x", pady=(8, 0))
            description = format_online_item(item, language, language == self.last_result_language)
            self.add_guide_label(row, description)
            label = "guide_hide" if key in self.open_guides else "guide"
            if key == self.pending_guide:
                label = "guide_loading"
            ttk.Button(
                row, text=self.tr(label), command=lambda selected=item: self.show_cleanup_guide(selected),
                state="disabled" if self.pending_guide is not None and key not in self.guides else "normal",
            ).pack(anchor="w", pady=(6, 0))
            if key in self.open_guides:
                guide = self.guides[key]
                heading = self.tr("guide_steps" if guide["mode"] == "cleanup" else "guide_verify")
                steps = "\n".join(f"{index}. {step}" for index, step in enumerate(guide["steps"], 1))
                self.add_guide_label(row, f"{heading}\n{steps}\n\n{self.tr('guide_impact')}\n{guide['impact']}")
            elif key in self.guide_failures:
                self.add_guide_label(row, self.tr("guide_error"))

    def add_guide_label(self, parent, text):
        label = tk.Label(parent, text=text, bg=WHITE, fg=INK, justify="left",
                         anchor="w", wraplength=max(220, self.advice_wrap - 24),
                         font=("Microsoft YaHei UI", 10))
        label.pack(fill="x")
        self.guide_labels.append(label)

    def show_cleanup_guide(self, item):
        key = (item["id"], self.lang())
        if key in self.guides:
            if key in self.open_guides:
                self.open_guides.remove(key)
            else:
                self.open_guides.add(key)
            self.render_advice()
            return
        if self.busy or self.pending_guide is not None:
            return
        confirmed = messagebox.askyesno(
            self.tr("guide_consent"), self.tr("guide_notice").format(directory=item["label"]),
            icon=messagebox.WARNING, default=messagebox.NO, parent=self.root,
        )
        if not confirmed:
            return
        self.guide_failures.discard(key)
        self.pending_guide = key
        self.run_button.configure(state="disabled")
        self.render_advice()
        threading.Thread(target=self.cleanup_guide_worker, args=(item, key, confirmed), daemon=True).start()

    def cleanup_guide_worker(self, item, key, confirmed):
        try:
            guide = get_cleanup_guide(item, key[1], confirmed=confirmed)
        except (OSError, ValueError, RuntimeError):
            guide = None
        self.messages.put(("guide", key, guide))

    def change_advice_page(self, direction):
        self.advice_page += direction
        self.render_advice()

    def toggle_advice(self):
        self.advice_expanded = not self.advice_expanded
        self.render_advice()

    def resize_advice(self, event):
        self.advice_wrap = max(250, event.width - 70)
        self.advice_body.configure(wraplength=self.advice_wrap)
        for label in self.guide_labels:
            label.configure(wraplength=max(220, self.advice_wrap - 24))

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
    parser.add_argument("--live-scan", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = tk.Tk()
    DiskAssistantApp(root, args.report_path, live_scan=args.live_scan)
    root.mainloop()


if __name__ == "__main__":
    main()
