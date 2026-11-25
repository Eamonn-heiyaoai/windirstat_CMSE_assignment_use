import argparse
import queue
import re
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk

from ai_pipeline.report_parser import parse_report
from ai_pipeline.appearance import (
    EDGE, FRAME, GRAPH_BLUE, SELECTION, SELECTION_TEXT, TEXT as WINDOW_TEXT, WINDOW,
    apply_dark_theme,
)
from ai_pipeline.disk_analyzer import SIZE_RANGES, analyze_disk
from ai_pipeline.ai_advisor import (
    CLEANUP_TEXT, ONLINE_NOTICE, VISIBLE_SUGGESTIONS, format_local_item, format_online_item,
    get_cleanup_guide, get_online_suggestions, ranked_suggestions, size_label,
    suggestion_page, suggestion_size,
)
from ai_pipeline.installed_apps import read_installed_apps, uninstall_suggestions

TEXT = {
    "zh": {
        "title": "WinDirStat - AI 分析",
        "source": "扫描报告", "browse": "选择文件…", "settings": "分析设置",
        "threshold": "重点文件大小下限", "language": "语言",
        "api": "使用 DeepSeek 在线识别",
        "api_consent": "确认发送目录摘要",
        "guide_consent": "确认请求清理指导",
        "guide_notice": "将把这一项的脱敏目录名称、占用和建议类型发给 DeepSeek。\n\n{directory}\n\n目录名称仍可能透露软件或个人信息。请核对 AI 指导，再决定是否清理。",
        "guide": "查看清理步骤", "guide_hide": "收起指导", "guide_loading": "正在生成指导…",
        "guide_error": "暂时无法生成指导。可以再次请求。",
        "guide_verify": "先核实用途", "guide_steps": "清理步骤",
        "guide_impact": "处理前请留意",
        "run": "开始分析", "close": "关闭", "summary": "扫描结果", "advice": "清理建议",
        "details": "建议详情", "item": "名称", "advice_source": "建议来源",
        "idle": "选择报告，然后点击“开始分析”。", "ready": "准备就绪",
        "failed": "分析出现问题",
        "running_local": "正在分析（本地）…", "running_ai": "正在分析（DeepSeek 已启用）…",
        "done_local": "分析完成，已显示本地建议", "done_ai": "分析完成，已显示 DeepSeek 识别结果",
        "empty_path": "请先选择扫描报告。", "invalid": "请输入有效的文件大小（0 到 1000000 MiB）。",
        "files_total": "文件总数", "size_total": "文件总大小", "priority": "重点文件数",
        "categories": "不同类型占用空间", "category": "文件类型", "files": "文件数",
        "size_distribution": "各文件大小区间占总大小的比例",
        "size": "大小", "share": "占比", "no_files": "没有可统计的文件。",
        "no_advice": "本次扫描中没有找到可提供明确清理建议的常见项目。",
        "ai_error": "在线识别暂不可用，已显示本地建议。",
        "advice_count": "共 {count} 项",
        "previous": "上一页", "next": "下一页", "page": "第 {current} / {total} 页",
        "expand": "展开全部", "collapse": "返回分页", "all_items": "已展开全部",
        "browse_title": "选择扫描报告", "file_type": "CSV / JSON 报告", "all_files": "所有文件",
        "cleanup": "本地规则", "online": "DeepSeek", "uninstall": "已安装的应用",
    },
    "en": {
        "title": "WinDirStat - AI Analysis",
        "source": "Scan report", "browse": "Choose file…", "settings": "Analysis settings",
        "threshold": "Minimum priority file size", "language": "Language",
        "api": "Use DeepSeek for online detection",
        "api_consent": "Confirm sending directory summaries",
        "guide_consent": "Confirm requesting cleanup guidance",
        "guide_notice": "Send this item's redacted directory name, size and review type to DeepSeek?\n\n{directory}\n\nThe directory name may reveal software or personal information. Check the guidance before acting.",
        "guide": "View cleanup steps", "guide_hide": "Hide guidance", "guide_loading": "Getting guidance…",
        "guide_error": "Guidance is unavailable. You can request it again.",
        "guide_verify": "Check what is in this folder", "guide_steps": "Cleanup steps",
        "guide_impact": "Before you proceed",
        "run": "Analyze", "close": "Close", "summary": "Scan summary", "advice": "Cleanup suggestions",
        "details": "Suggestion details", "item": "Name", "advice_source": "Source",
        "idle": "Choose a report, then click Analyze.", "ready": "Ready",
        "failed": "Analysis encountered a problem",
        "running_local": "Analyzing locally…", "running_ai": "Analyzing with DeepSeek enabled…",
        "done_local": "Analysis complete. Local suggestions shown.",
        "done_ai": "Analysis complete. DeepSeek findings shown.",
        "empty_path": "Please select a scan report.", "invalid": "Enter a valid file size (0 to 1000000 MiB).",
        "files_total": "Files analyzed", "size_total": "Total file size", "priority": "Priority files",
        "categories": "Storage by file type", "category": "File type", "files": "Files",
        "size_distribution": "Share of total size by file size range",
        "size": "Size", "share": "Share", "no_files": "No files available for analysis.",
        "no_advice": "This scan found no common items with a clear cleanup method.",
        "ai_error": "Online detection is unavailable. Showing local suggestions.",
        "advice_count": "{count} items",
        "previous": "Previous", "next": "Next", "page": "Page {current} of {total}",
        "expand": "Expand all", "collapse": "Return to pages", "all_items": "Showing all",
        "browse_title": "Choose scan report", "file_type": "CSV / JSON reports", "all_files": "All files",
        "cleanup": "Local rules", "online": "DeepSeek", "uninstall": "Installed apps",
    },
}
CATEGORY = {
    "zh": {
        "video": "视频", "audio": "音频", "archive": "压缩包", "document": "文档",
        "installer": "安装程序", "image": "图片", "system_component": "系统组件",
        "virtual_disk": "虚拟磁盘", "backup": "备份", "database": "数据库", "data": "数据文件",
        "log": "日志", "temporary": "临时文件", "code": "代码", "font": "字体", "other": "其他",
    },
    "en": {
        "video": "Video", "audio": "Audio", "archive": "Archives", "document": "Documents",
        "installer": "Installers", "image": "Images", "system_component": "System components",
        "virtual_disk": "Virtual disks", "backup": "Backups", "database": "Databases", "data": "Data files",
        "log": "Logs", "temporary": "Temporary files", "code": "Code", "font": "Fonts", "other": "Other",
    },
}
SIZE_RANGE_LABELS = {
    "under_1mb": "< 1 MiB",
    "1mb_to_100mb": "1–100 MiB",
    "100mb_to_1gb": "100 MiB–1 GiB",
    "1gb_to_10gb": "1–10 GiB",
    "over_10gb": "≥ 10 GiB",
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
        self.root.geometry("820x620")
        self.root.minsize(690, 565)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda _event: self.close())

        apply_dark_theme(root)
        icon = Path(__file__).resolve().parent.parent / "windirstat" / "res" / "WinDirStat.ico"
        try:
            root.iconbitmap(default=str(icon))
        except tk.TclError:
            pass

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
        self.advice_items = {}
        self.guides = {}
        self.open_guides = set()
        self.guide_failures = set()
        self.pending_guide = None

        outer = ttk.Frame(root, padding=10)
        outer.pack(fill="both", expand=True)

        settings = self.settings = ttk.LabelFrame(outer, padding=(8, 6))
        settings.pack(fill="x", pady=(0, 8))
        settings.columnconfigure(1, weight=1)
        self.source_title = ttk.Label(settings)
        self.source_title.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.path_entry = ttk.Entry(settings, textvariable=self.path)
        self.path_entry.grid(row=0, column=1, sticky="ew")
        self.browse_btn = ttk.Button(settings, command=self.browse)
        self.browse_btn.grid(row=0, column=2, sticky="e", padx=(8, 0))
        self.threshold_title = ttk.Label(settings)
        self.threshold_title.grid(row=1, column=0, sticky="w")
        options = ttk.Frame(settings)
        options.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        self.spinbox = ttk.Spinbox(options, from_=0, to=1000000, increment=10,
                                   textvariable=self.minimum, width=9)
        self.spinbox.pack(side="left")
        ttk.Label(options, text="MiB").pack(side="left", padx=(5, 0))
        self.language_label = ttk.Label(options)
        self.language_box = ttk.Combobox(options, textvariable=self.language,
                                         values=("中文", "English"), state="readonly", width=10)
        self.language_box.pack(side="right")
        self.language_label.pack(side="right", padx=(0, 6))
        self.language_box.bind("<<ComboboxSelected>>", self.change_language)
        self.api_box = ttk.Checkbutton(settings, variable=self.use_api)
        self.api_box.grid(row=2, column=1, columnspan=2, sticky="w", pady=(6, 0))

        self.results = ttk.Notebook(outer)
        self.results.pack(fill="both", expand=True)
        self.advice_tab = ttk.Frame(self.results, padding=8)
        self.summary_tab = ttk.Frame(self.results, padding=8)
        self.results.add(self.advice_tab)
        self.results.add(self.summary_tab)
        self.results.enable_traversal()

        self.advice_list = self.make_list(self.advice_tab, ("name", "size", "source"), height=5)
        self.advice_list.column("size", width=110, minwidth=90, stretch=False, anchor="e")
        self.advice_list.column("source", width=140, minwidth=105, stretch=False)
        self.advice_list.bind("<<TreeviewSelect>>", self.render_details)

        nav = ttk.Frame(self.advice_tab)
        nav.pack(fill="x", pady=(5, 8))
        self.advice_count = ttk.Label(nav)
        self.advice_count.pack(side="left")
        self.advice_previous = ttk.Button(nav, command=lambda: self.change_advice_page(-1))
        self.advice_next = ttk.Button(nav, command=lambda: self.change_advice_page(1))
        self.advice_toggle = ttk.Button(nav, command=self.toggle_advice)
        self.advice_toggle.pack(side="right")
        self.advice_next.pack(side="right", padx=6)
        self.advice_page_label = ttk.Label(nav)
        self.advice_page_label.pack(side="right", padx=4)
        self.advice_previous.pack(side="right")

        details = self.details = ttk.LabelFrame(self.advice_tab, padding=(6, 5))
        details.pack(fill="both", expand=True)
        self.guide_button = ttk.Button(details, command=self.show_selected_guide)
        self.guide_button.pack(side="bottom", anchor="e", pady=(5, 0))
        text_scroll = ttk.Scrollbar(details, orient="vertical")
        text_scroll.pack(side="right", fill="y")
        self.advice_body = tk.Text(
            details, height=5, wrap="word", state="disabled", font="TkDefaultFont",
            padx=5, pady=4, background=WINDOW, foreground=WINDOW_TEXT,
            selectbackground=SELECTION, selectforeground=SELECTION_TEXT,
            highlightbackground=EDGE, highlightcolor=GRAPH_BLUE, highlightthickness=1,
            borderwidth=0, yscrollcommand=text_scroll.set,
        )
        self.advice_body.pack(fill="both", expand=True)
        text_scroll.configure(command=self.advice_body.yview)

        metrics = ttk.Frame(self.summary_tab)
        metrics.pack(fill="x", pady=(0, 8))
        self.metric_labels = []
        for index in range(3):
            metrics.columnconfigure(index * 2 + 1, weight=1)
            name = ttk.Label(metrics)
            name.grid(row=0, column=index * 2, sticky="w", padx=(0, 6))
            value = ttk.Label(metrics, text="—")
            value.grid(row=0, column=index * 2 + 1, sticky="w", padx=(0, 12))
            self.metric_labels.append((name, value))
        category_group = self.category_group = ttk.LabelFrame(self.summary_tab, padding=6)
        category_group.pack(fill="both", expand=True)
        self.category_list = self.make_list(category_group, ("name", "files", "size", "share"), height=5)
        for column in ("files", "size", "share"):
            self.category_list.column(column, width=110, minwidth=85, stretch=False, anchor="e")
        self.summary_state = ttk.Label(self.summary_tab)
        self.summary_state.pack(anchor="w", pady=(6, 0))
        self.distribution_group = ttk.LabelFrame(self.summary_tab, padding=6)
        self.chart_font = font.nametofont("TkDefaultFont", root=root)
        self.chart_row_height = self.chart_font.metrics("linespace") + 5
        self.distribution_chart = tk.Canvas(
            self.distribution_group, background=WINDOW, highlightthickness=0,
            height=self.chart_row_height * len(SIZE_RANGES),
        )
        self.distribution_chart.pack(fill="x")
        self.distribution_chart.bind("<Configure>", self.draw_size_distribution)

        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x", pady=(8, 0), before=self.results)
        ttk.Label(footer, textvariable=self.status).pack(side="left")
        self.run_button = ttk.Button(footer, command=self.start_analysis, width=11, default="active")
        self.close_button = ttk.Button(footer, command=self.close, width=11)
        self.close_button.pack(side="right")
        self.run_button.pack(side="right", padx=(0, 6))
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=85)
        self.path_entry.bind("<Return>", lambda _event: self.start_analysis())
        self.spinbox.bind("<Return>", lambda _event: self.start_analysis())

        self.apply_language()
        self.path_entry.focus_set()
        self.root.after(100, self.check_messages)

    def make_list(self, parent, columns, *, height):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings",
                            selectmode="browse", height=height)
        tree.column("name", width=310, minwidth=175)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        return tree

    def lang(self):
        return "zh" if self.language.get() == "中文" else "en"

    def tr(self, key):
        return TEXT[self.lang()][key]

    def set_status(self, key):
        self.status_key = key
        self.status.set(self.tr(key))

    def apply_language(self):
        self.root.title(self.tr("title"))
        for widget, key in (
            (self.source_title, "source"), (self.browse_btn, "browse"),
            (self.settings, "settings"), (self.threshold_title, "threshold"),
            (self.language_label, "language"), (self.api_box, "api"),
            (self.run_button, "run"), (self.close_button, "close"),
            (self.details, "details"), (self.category_group, "categories"),
            (self.distribution_group, "size_distribution"),
            (self.advice_previous, "previous"), (self.advice_next, "next"),
        ):
            widget.configure(text=self.tr(key))
        self.results.tab(self.advice_tab, text=self.tr("advice"))
        self.results.tab(self.summary_tab, text=self.tr("summary"))
        for tree, headings in (
            (self.advice_list, {"name": "item", "size": "size", "source": "advice_source"}),
            (self.category_list, {"name": "category", "files": "files", "size": "size", "share": "share"}),
        ):
            for column, key in headings.items():
                tree.heading(column, text=self.tr(key), anchor="w" if column in ("name", "source") else "e")
        for (name, _), key in zip(self.metric_labels, ("files_total", "size_total", "priority")):
            name.configure(text=self.tr(key))
        self.set_status(self.status_key)
        self.render_summary()
        self.render_advice()

    def change_language(self, _event=None):
        self.apply_language()

    def browse(self):
        path = filedialog.askopenfilename(
            parent=self.root, title=self.tr("browse_title"),
            filetypes=[(self.tr("file_type"), "*.csv *.json"), (self.tr("all_files"), "*.*")]
        )
        if path:
            self.path.set(path)

    def start_analysis(self):
        if self.busy or self.pending_guide is not None:
            return
        path = self.path.get().strip()
        if not path:
            messagebox.showwarning(self.tr("source"), self.tr("empty_path"), parent=self.root)
            return
        try:
            minimum = self.minimum.get()
            if not 0 <= minimum <= 1000000:
                raise ValueError()
        except (ValueError, tk.TclError):
            messagebox.showerror(self.tr("settings"), self.tr("invalid"), parent=self.root)
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
        self.api_box.state(["disabled"])
        self.set_status("running_ai" if use_api else "running_local")
        self.results.select(self.advice_tab)
        self.update_activity()
        self.render_summary()
        self.render_advice()
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

    def update_activity(self):
        active = self.busy or self.pending_guide is not None
        self.run_button.configure(state="disabled" if active else "normal")
        if active:
            if not self.progress.winfo_manager():
                self.progress.pack(side="left", padx=8)
                self.progress.start()
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def check_messages(self):
        try:
            while True:
                item = self.messages.get_nowait()
                if item[0] == "local":
                    self.last_summary = item[1]
                    self.render_summary()
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
                    self.set_status("done_ai")
                    self.update_activity()
                    self.render_details(reveal_guide=key)
                    continue

                self.busy = False
                self.api_box.state(["!disabled"])
                self.update_activity()
                if item[0] == "error":
                    self.set_status("failed")
                    self.render_summary()
                    self.render_details()
                    messagebox.showerror(self.tr("failed"), item[1], parent=self.root)
                else:
                    _, online_items, error, request_language = item
                    if online_items:
                        self.last_summary["online_items"] = online_items
                    self.last_ai_error = error
                    self.last_result_language = request_language
                    self.set_status("done_ai" if online_items else "done_local")
                    self.render_advice()
        except queue.Empty:
            pass
        self.root.after(100, self.check_messages)

    def render_summary(self):
        summary = self.last_summary
        values = (
            f"{summary['total_files']:,}", size_label(summary["total_size_mb"]),
            f"{summary['large_file_count']:,}",
        ) if summary is not None else ("—", "—", "—")
        for (_, value), new in zip(self.metric_labels, values):
            value.configure(text=new)
        self.category_list.delete(*self.category_list.get_children())
        categories = summary["file_categories"] if summary is not None else {}
        for key, info in categories.items():
            name = CATEGORY[self.lang()].get(key, key)
            values = (f"{info['count']:,}", size_label(info["size_mb"]), f"{info['percentage']:.1f}%")
            self.category_list.insert("", "end", values=(name, *values))
        if summary is None:
            state = self.empty_state()
        else:
            state = "" if categories else self.tr("no_files")
        self.summary_state.configure(text=state)
        if categories:
            self.summary_state.pack_forget()
            self.distribution_group.pack(side="bottom", fill="x", pady=(8, 0), before=self.category_group)
        else:
            self.distribution_group.pack_forget()
            self.summary_state.pack(anchor="w", pady=(6, 0))
        self.draw_size_distribution()

    def draw_size_distribution(self, _event=None):
        chart = self.distribution_chart
        chart.delete("all")
        if not self.last_summary or not self.last_summary["file_categories"]:
            return

        padding = 8
        left = max(map(self.chart_font.measure, SIZE_RANGE_LABELS.values())) + padding * 3
        label_x = chart.winfo_width() - padding
        right = label_x - self.chart_font.measure("100.0%") - padding
        if right <= left:
            return

        distribution = self.last_summary["size_distribution"]
        for index, (key, _, _) in enumerate(SIZE_RANGES):
            percent = distribution[key]["percentage"]
            y = (index + 0.5) * self.chart_row_height
            top, bottom = y - 4, y + 4
            chart.create_text(padding, y, anchor="w", text=SIZE_RANGE_LABELS[key],
                              font=self.chart_font, fill=WINDOW_TEXT)
            chart.create_rectangle(left, top, right, bottom, fill=FRAME, width=0)
            if percent > 0:
                end = left + (right - left) * percent / 100
                chart.create_rectangle(left, top, end, bottom, fill=GRAPH_BLUE, width=0)
            chart.create_text(label_x, y, anchor="e", text=f"{percent:.1f}%",
                              font=self.chart_font, fill=WINDOW_TEXT)

    def selected_suggestion(self):
        selection = self.advice_list.selection()
        return self.advice_items.get(selection[0]) if selection else None

    def empty_state(self):
        if self.busy or self.status_key == "failed":
            return self.status.get()
        return self.tr("idle")

    def render_advice(self):
        selected = self.selected_suggestion()
        items = ranked_suggestions(self.last_summary) if self.last_summary is not None else []
        item_count = len(items)
        total_pages = (item_count + VISIBLE_SUGGESTIONS - 1) // VISIBLE_SUGGESTIONS
        self.advice_page = min(self.advice_page, max(0, total_pages - 1))
        visible = suggestion_page(items, self.advice_expanded, self.advice_page)
        self.advice_count.configure(text=self.tr("advice_count").format(count=item_count))

        self.advice_list.delete(*self.advice_list.get_children())
        self.advice_items.clear()
        language = self.lang()
        current = None
        for item, source in visible:
            if source == "cleanup":
                name = CLEANUP_TEXT[item["category"]][language][0]
            elif source == "online" and language != self.last_result_language:
                name = item["label"]
            else:
                name = item["name"]
            row = self.advice_list.insert("", "end", values=(name, suggestion_size(item), self.tr(source)))
            self.advice_items[row] = (item, source)
            if selected is not None and selected[0] is item and selected[1] == source:
                current = row

        if visible:
            row = current or next(iter(self.advice_items))
            self.advice_list.selection_set(row)
            self.advice_list.focus(row)
            self.advice_list.see(row)

        paged = not self.advice_expanded
        page_label = self.tr("page").format(current=self.advice_page + 1, total=total_pages)
        self.advice_page_label.configure(
            text=(page_label if paged else self.tr("all_items")) if total_pages > 1 else "",
        )
        self.advice_previous.configure(state="normal" if paged and self.advice_page > 0 else "disabled")
        self.advice_next.configure(state="normal" if paged and self.advice_page + 1 < total_pages else "disabled")
        self.advice_toggle.configure(text=self.tr("expand" if paged else "collapse"),
                                     state="normal" if total_pages > 1 else "disabled")
        self.render_details()

    def render_details(self, _event=None, *, reveal_guide=None):
        selected = self.selected_suggestion()
        button_label = "guide"
        can_request = False
        guidance = ""
        scroll_to_guide = False
        if selected is None:
            content = self.empty_state() if self.last_summary is None else self.tr("no_advice")
        else:
            item, source = selected
            language = self.lang()
            if source == "online":
                key = (item["id"], language)
                content = format_online_item(item, language, language == self.last_result_language)
                can_request = not self.busy and self.pending_guide is None
                if key == self.pending_guide:
                    button_label = "guide_loading"
                    content += "\n\n" + self.tr(button_label)
                elif key in self.open_guides:
                    guide = self.guides[key]
                    button_label = "guide_hide"
                    heading = self.tr("guide_steps" if guide["mode"] == "cleanup" else "guide_verify")
                    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(guide["steps"], 1))
                    guidance = f"{heading}\n{steps}\n\n{self.tr('guide_impact')}\n{guide['impact']}"
                    scroll_to_guide = key == reveal_guide
                elif key in self.guide_failures:
                    content += "\n\n" + self.tr("guide_error")
            else:
                content = format_local_item(item, source, language)

        if self.last_ai_error is not None:
            content = f"{self.tr('ai_error')}\n{self.last_ai_error}\n\n{content}"
        self.guide_button.configure(text=self.tr(button_label), state="normal" if can_request else "disabled")
        self.advice_body.configure(state="normal")
        self.advice_body.delete("1.0", "end")
        self.advice_body.insert("1.0", content)
        if guidance:
            self.advice_body.insert("end", "\n\n")
            guide_start = self.advice_body.index("end-1c")
            self.advice_body.insert("end", guidance)
            if scroll_to_guide:
                self.advice_body.yview(guide_start)
        self.advice_body.configure(state="disabled")

    def show_selected_guide(self):
        selected = self.selected_suggestion()
        if selected is None or selected[1] != "online" or self.busy or self.pending_guide is not None:
            return
        item = selected[0]
        key = (item["id"], self.lang())
        if key in self.guides:
            if key in self.open_guides:
                self.open_guides.remove(key)
            else:
                self.open_guides.add(key)
            self.render_details(reveal_guide=key)
            return
        confirmed = messagebox.askyesno(
            self.tr("guide_consent"), self.tr("guide_notice").format(directory=item["label"]),
            icon=messagebox.WARNING, default=messagebox.NO, parent=self.root,
        )
        if not confirmed:
            return
        self.guide_failures.discard(key)
        self.pending_guide = key
        self.set_status("guide_loading")
        self.update_activity()
        self.render_details()
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
