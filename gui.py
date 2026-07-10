"""
微信群发工具 GUI 版
本软件由 淘淘数码 研发，版权归 淘淘数码 所有。
仅限于授权用户内部使用，禁止用于任何商业用途。
未经许可，禁止复制、修改、分发或转售。
解释权归 淘淘数码 所有。
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import logging
import sys
from io import StringIO

import pyautogui
import send_wechat as sw

CONFIG_FIELDS = [
    ("group_prefixes", "群名前缀（逗号分隔）", "str_list"),
    ("groups_per_prefix", "每个前缀群数量", "int"),
    ("send_times", "定时时间（逗号分隔）", "str_list"),
    ("speed_factor", "速度倍率（0.2=极速 0.5=2倍 1.0=正常）", "float"),
    ("interval_between_groups", "前缀间隔秒数", "int"),
    ("log_level", "日志级别", "choice"),
]

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


class LogHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    def emit(self, record):
        msg = self.formatter.format(record)
        self.text_widget.after(0, lambda: (
            self.text_widget.insert("end", msg + "\n"),
            self.text_widget.see("end"),
        ))


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("微信群发工具")
        self.root.geometry("720x750")
        self.root.minsize(600, 600)

        self.file_vars = {}
        self._build_ui()
        self._load_config()
        self._refresh_file_list()
        self._setup_logging()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        # ── 配置区 ──
        cfg_frame = ttk.LabelFrame(main, text="配置参数", padding=10)
        cfg_frame.pack(fill="x", pady=(0, 10))

        self.entries = {}
        for i, (key, label, vtype) in enumerate(CONFIG_FIELDS):
            ttk.Label(cfg_frame, text=label).grid(row=i, column=0, sticky="w", pady=3)
            if vtype == "choice":
                var = tk.StringVar()
                box = ttk.Combobox(cfg_frame, textvariable=var, values=LOG_LEVELS, width=30, state="readonly")
                box.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=3)
                self.entries[key] = var
            else:
                var = tk.StringVar()
                entry = ttk.Entry(cfg_frame, textvariable=var, width=35)
                entry.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=3)
                self.entries[key] = var

        cfg_frame.columnconfigure(1, weight=1)

        # ── 文件选择区 ──
        file_frame = ttk.LabelFrame(main, text="选择发送文件（可多选）", padding=10)
        file_frame.pack(fill="x", pady=(0, 10))

        top_row = ttk.Frame(file_frame)
        top_row.pack(fill="x", pady=(0, 5))
        ttk.Button(top_row, text="全选", command=self._select_all).pack(side="left", padx=(0, 5))
        ttk.Button(top_row, text="取消全选", command=self._deselect_all).pack(side="left", padx=5)
        ttk.Button(top_row, text="刷新列表", command=self._refresh_file_list).pack(side="left", padx=5)

        list_frame = ttk.Frame(file_frame)
        list_frame.pack(fill="x")

        self.file_listbox = tk.Listbox(
            list_frame, selectmode="multiple", height=6,
            font=("Consolas", 10), exportselection=False
        )
        self.file_listbox.pack(side="left", fill="x", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        # ── 按钮区 ──
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(0, 10))

        ttk.Button(btn_frame, text="立即运行", command=self._run_once).pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="定时模式", command=self._run_daemon).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="查看统计", command=self._show_stats).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="保存配置", command=self._save_config).pack(side="left", padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        # ── 日志区 ──
        log_frame = ttk.LabelFrame(main, text="运行日志", padding=5)
        log_frame.pack(fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=15, font=("Consolas", 10), wrap="word", state="normal"
        )
        self.log_text.pack(fill="both", expand=True)

        # ── 版权声明 ──
        notice = ttk.Label(
            main, text="本软件由 淘淘数码 研发，禁止用于商业用途 | 解释权归 淘淘数码 所有",
            foreground="gray", font=("Microsoft YaHei", 8)
        )
        notice.pack(pady=(2, 0))

    # ── 文件列表管理 ──

    def _refresh_file_list(self):
        self.file_listbox.delete(0, "end")
        names = sw.get_available_txt_files()
        selected = sw.CONFIG.get("txt_files", [])
        sel_basenames = {os.path.basename(p) for p in selected}

        self.all_files = []
        for name in names:
            full = os.path.join(sw.SCRIPT_DIR, name)
            if not os.path.exists(full):
                full = os.path.join(r"C:\Users\zcxz\Desktop\脚本test", name)
            self.all_files.append(full)
            self.file_listbox.insert("end", name)

        for i, full in enumerate(self.all_files):
            if os.path.basename(full) in sel_basenames or full in selected:
                self.file_listbox.selection_set(i)

    def _get_selected_files(self):
        return [self.all_files[i] for i in self.file_listbox.curselection()]

    def _select_all(self):
        self.file_listbox.selection_set(0, "end")

    def _deselect_all(self):
        self.file_listbox.selection_clear(0, "end")

    # ── 配置读写 ──

    def _load_config(self):
        cfg = sw.CONFIG
        for key, _, vtype in CONFIG_FIELDS:
            val = cfg[key]
            if vtype == "str_list":
                self.entries[key].set(", ".join(val))
            elif vtype == "str":
                self.entries[key].set(val)
            elif vtype in ("int", "float"):
                self.entries[key].set(str(val))
            elif vtype == "choice":
                self.entries[key].set(str(val))

    def _read_config_from_ui(self):
        new_cfg = {}
        for key, _, vtype in CONFIG_FIELDS:
            raw = self.entries[key].get().strip()
            if vtype == "str_list":
                new_cfg[key] = [s.strip() for s in raw.split(",") if s.strip()]
            elif vtype == "str":
                new_cfg[key] = raw
            elif vtype == "int":
                try:
                    new_cfg[key] = int(raw)
                except ValueError:
                    messagebox.showerror("配置错误", f"{key} 需要填写整数")
                    return None
            elif vtype == "float":
                try:
                    new_cfg[key] = float(raw)
                except ValueError:
                    messagebox.showerror("配置错误", f"{key} 需要填写数字")
                    return None
            elif vtype == "choice":
                new_cfg[key] = raw if raw in LOG_LEVELS else "INFO"
        # 全角冒号转半角
        if "send_times" in new_cfg:
            new_cfg["send_times"] = [t.replace("：", ":") for t in new_cfg["send_times"]]
        new_cfg["txt_files"] = self._get_selected_files()
        return new_cfg

    def _apply_config(self, cfg):
        for key, val in cfg.items():
            sw.CONFIG[key] = val
        sw.pyautogui.PAUSE = sw.CONFIG.get("click_delay", 0.05)
        sw.SPEED_FACTOR = sw.CONFIG.get("speed_factor", 1.0)
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, sw.CONFIG["log_level"]))

    def _save_config(self):
        cfg = self._read_config_from_ui()
        if cfg is None:
            return
        self._apply_config(cfg)
        sw.save_config_to_file()
        messagebox.showinfo("已保存", "配置已保存到文件，重启后生效")

    def _enable_stop(self, enabled=True):
        self.stop_btn.config(state="normal" if enabled else "disabled")

    def _stop(self):
        sw.STOP_EVENT.set()
        sw.logger.warning("已触发停止信号，等待当前操作完成后停止...")
        self._enable_stop(False)

    def _run_once(self):
        sw.STOP_EVENT.clear()
        cfg = self._read_config_from_ui()
        if cfg is None:
            return
        self._apply_config(cfg)
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", ">>> 立即运行中...\n")
        self._enable_stop(True)

        def task():
            try:
                sw.do_send()
            except (SystemExit, pyautogui.FailSafeException):
                sw.logger.warning("已停止")
            except Exception as e:
                sw.logger.error(f"发送失败: {e}")
            finally:
                self.root.after(0, self._enable_stop, False)

        threading.Thread(target=task, daemon=True).start()

    def _run_daemon(self):
        sw.STOP_EVENT.clear()
        cfg = self._read_config_from_ui()
        if cfg is None:
            return
        self._apply_config(cfg)
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", f">>> 定时模式启动，发送时间: {sw.CONFIG['send_times']}\n")
        self._enable_stop(True)

        def task():
            try:
                sw.run_daemon()
            except (SystemExit, pyautogui.FailSafeException):
                sw.logger.warning("已停止")
            except Exception as e:
                sw.logger.error(f"定时任务出错: {e}")
            finally:
                self.root.after(0, self._enable_stop, False)

        threading.Thread(target=task, daemon=True).start()

    def _show_stats(self):
        self.log_text.delete("1.0", "end")
        buf = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            sw.show_stats()
        finally:
            sys.stdout = old_stdout
        self.log_text.insert("end", buf.getvalue())

    def _setup_logging(self):
        handler = LogHandler(self.log_text)
        sw.logger.addHandler(handler)
        logger = logging.getLogger()
        logger.addHandler(handler)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
