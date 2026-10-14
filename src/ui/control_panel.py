"""可视化控制面板：显示进程状态 + 启动/暂停开关 + 规则操作。"""

import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from src.core.status import EngineStatus
from src.learn.rule_engine import ROOT, RuleEngine
from src.utils.hotkey import HotkeyWatcher
from src.utils.logger import get_logger

log = get_logger("quiz.ui.panel")

RULES_PATH = ROOT / "config" / "rules.yaml"

STATE_STYLE = {
    "idle":    ("#888888", "未启动"),
    "running": ("#00c853", "运行中"),
    "paused":  ("#ff9800", "已暂停"),
    "unknown": ("#e53935", "未知情况"),
    "stopped": ("#607d8b", "已停止"),
}


class ControlPanel:
    def __init__(self, root: tk.Tk, settings: dict):
        self.root = root
        self.settings = settings
        self.status = EngineStatus()
        self.engine: RuleEngine | None = None
        self.thread: threading.Thread | None = None
        self._busy = False
        self.exit_hotkey = HotkeyWatcher(
            settings.get("safety", {}).get("hotkey_exit", "f1"))

        root.title("AI 丝绸之路助手")
        root.attributes("-topmost", True)
        root.geometry("400x340+40+40")
        root.configure(bg="#1e1e1e")
        root.resizable(False, False)

        self._build()
        self._poll()

    # ---------- 界面 ----------

    def _build(self):
        pad = {"padx": 12, "pady": 4}

        tk.Label(self.root, text="进程状态", bg="#1e1e1e", fg="#9e9e9e",
                 font=("Microsoft YaHei", 10)).pack(anchor="w", **pad)
        self.state_lbl = tk.Label(self.root, text="未启动", bg="#1e1e1e",
                                  fg="#888888", font=("Microsoft YaHei", 20, "bold"))
        self.state_lbl.pack(anchor="w", padx=12)

        self.msg_lbl = tk.Label(self.root, text="", bg="#1e1e1e", fg="#e0e0e0",
                                font=("Microsoft YaHei", 10), wraplength=350, justify="left")
        self.msg_lbl.pack(anchor="w", padx=12, pady=(0, 6))

        self.info_lbl = tk.Label(self.root, text="", bg="#1e1e1e", fg="#80cbc4",
                                 font=("Consolas", 9), justify="left")
        self.info_lbl.pack(anchor="w", padx=12)

        # 开关
        btn_row = tk.Frame(self.root, bg="#1e1e1e")
        btn_row.pack(fill="x", padx=12, pady=10)
        self.toggle_btn = tk.Button(btn_row, text="▶ 启动", command=self.toggle,
                                    bg="#00c853", fg="white",
                                    font=("Microsoft YaHei", 12, "bold"),
                                    relief="flat", height=1, width=10)
        self.toggle_btn.pack(side="left")
        self.once_btn = tk.Button(btn_row, text="单次", command=self.once,
                                  bg="#2979ff", fg="white",
                                  font=("Microsoft YaHei", 12, "bold"),
                                  relief="flat", height=1, width=6)
        self.once_btn.pack(side="left", padx=6)
        tk.Button(btn_row, text="重新载入规则", command=self.reload_rules,
                  bg="#455a64", fg="white", relief="flat",
                  font=("Microsoft YaHei", 10)).pack(side="left", padx=6)
        tk.Button(btn_row, text="打开规则", command=self.open_rules,
                  bg="#455a64", fg="white", relief="flat",
                  font=("Microsoft YaHei", 10)).pack(side="left")

        tip = ("提示：遇到未知情况会自动暂停并存截图到 data/unknown/。\n"
               "按 F1 键随时退出脚本。（鼠标快速甩到屏幕左上角也可紧急停止）")
        tk.Label(self.root, text=tip, bg="#1e1e1e", fg="#757575",
                 font=("Microsoft YaHei", 9), wraplength=350,
                 justify="left").pack(anchor="w", padx=12, pady=(0, 6))

    # ---------- 逻辑 ----------

    def toggle(self):
        if self.engine is None or not (self.thread and self.thread.is_alive()):
            self._start()
        elif self.engine.paused:
            self.engine.resume()
        else:
            self.engine.pause()
        self._sync_button()

    def _start(self):
        self.status.set(state="running", message="启动中…")
        self.engine = RuleEngine(self.settings, self.status, RULES_PATH)
        self.thread = threading.Thread(target=self.engine.run, daemon=True)
        self.thread.start()
        log.info("引擎线程已启动")

    def once(self):
        """单次执行：检测一次并按规则动作一次，不进入循环，不抢占鼠标。"""
        if self._busy:
            return
        self._busy = True
        if self.engine is None:
            self.engine = RuleEngine(self.settings, self.status, RULES_PATH)

        def worker():
            try:
                self.engine.run_once()
            except Exception as e:  # noqa
                log.error("单次执行异常: %s", e)
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    def reload_rules(self):
        if self.engine is not None:
            # 触发引擎在下一轮自动重载
            try:
                RULES_PATH.touch()
            except OSError:
                pass
            self.status.set(message="已请求重新载入规则")
        else:
            messagebox.showinfo("提示", "引擎尚未启动。")

    def open_rules(self):
        try:
            subprocess.Popen(["cmd", "/c", "start", "", str(RULES_PATH)])
        except Exception as e:  # noqa
            messagebox.showerror("错误", str(e))

    def _sync_button(self):
        if self.engine is None or not (self.thread and self.thread.is_alive()):
            self.toggle_btn.config(text="▶ 启动", bg="#00c853")
        elif self.engine.paused:
            self.toggle_btn.config(text="▶ 继续", bg="#00c853")
        else:
            self.toggle_btn.config(text="⏸ 暂停", bg="#ff9800")

    def _poll(self):
        if self.exit_hotkey.pressed():
            log.info("检测到 F1，退出脚本。")
            self._shutdown()
            return
        s = self.status.snapshot()
        color, label = STATE_STYLE.get(s["state"], ("#888888", s["state"]))
        self.state_lbl.config(text=label, fg=color)
        self.msg_lbl.config(text=s["message"])
        vis = ", ".join(s["visible"]) or "-"
        self.info_lbl.config(text=(
            "规则: %s\n可见: %s\n执行: %d 次   未知: %d 次" % (
                s["current_rule"] or "-", vis, s["count_exec"], s["count_unknown"])))
        self._sync_button()
        self.root.after(300, self._poll)

    def _shutdown(self):
        try:
            if self.engine is not None:
                self.engine.stop()
        except Exception:
            pass
        self.root.destroy()


def launch(settings: dict) -> None:
    root = tk.Tk()
    ControlPanel(root, settings)
    root.mainloop()
