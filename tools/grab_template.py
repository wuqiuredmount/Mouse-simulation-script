"""模板抓取工具。

用法：
    python tools/grab_template.py              # 自由框选，每次手输名字
    python tools/grab_template.py --preset     # 按 silkroad.yaml 的按钮依次框选

流程：
  1. 先切到游戏界面（按钮要显示出来），再运行本工具
  2. 屏幕冻结当前画面
  3. 用鼠标框选一个按钮 -> 松开
     - 自由模式：弹窗输入文件名
     - 预设模式：自动用下一个按钮名保存
  4. 按空格 = 重新截屏（换界面后刷新）；按 ESC = 退出

保存位置：data/assets/<名字>.png
"""

import argparse
import ctypes
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tkinter as tk
from tkinter import simpledialog

import cv2
import mss
import numpy as np
import yaml
from PIL import Image, ImageTk

from src.utils.imaging import imwrite_unicode

ASSETS = ROOT / "data" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
CONFIG = ROOT / "config" / "silkroad.yaml"


# 模板文件名(去掉.png) -> 中文名，仅用于预设模式提示
PRESET_ORDER = [
    ("sr_shang", "左下角圆圈里的 商 按钮"),
    ("sr_dispatch", "派遣 按钮"),
    ("sr_cart_event", "马车上方的 事件? 图标"),
    ("sr_question", "右下角 问号? 按钮"),
    ("sr_start", "开始吧 按钮"),
    ("sr_confirm", "确定 按钮"),
    ("sr_help", "求助锦囊 按钮"),
    ("sr_option_a", "选项A（答案选项）"),
    ("sr_event", "事件图标"),
    ("sr_exclaim", "感叹号"),
    ("sr_chest_left", "宝箱（左）"),
    ("sr_chest_right", "宝箱（右）"),
]


class Grabber:
    def __init__(self, root, preset: bool):
        self.root = root
        self.preset = preset
        self.sct = mss.mss()
        self.start = None
        self.rect_id = None
        self.count = 0
        self.preset_index = 0

        root.title("模板抓取")
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        root.configure(bg="black")
        root.bind("<Escape>", lambda e: self._quit())

        self.canvas = tk.Canvas(root, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        root.bind("<space>", lambda e: self._snapshot())

        self._snapshot()

    def _snapshot(self):
        mon = self.sct.monitors[1]
        raw = np.array(self.sct.grab(mon))
        self.bgr = raw[:, :, :3].copy()
        rgb = cv2.cvtColor(self.bgr, cv2.COLOR_BGR2RGB)
        self.pil = Image.fromarray(rgb)
        self.tk_img = ImageTk.PhotoImage(self.pil)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self._hint()

    def _hint(self):
        self.canvas.delete("hint")
        if self.preset and self.preset_index < len(PRESET_ORDER):
            _, label = PRESET_ORDER[self.preset_index]
            task = "请框选：%s" % label
        elif self.preset:
            task = "预设已全部完成！"
        else:
            task = "框选按钮后输入名字保存"
        txt = "%s    |    空格=重新截屏   ESC=退出    |    已保存: %d" % (task, self.count)
        self.canvas.create_rectangle(0, 0, self.pil.width, 40,
                                     fill="#111111", outline="", tags="hint")
        self.canvas.create_text(12, 20, anchor="w", text=txt, fill="#00ff88",
                                font=("Microsoft YaHei", 13, "bold"), tags="hint")

    def _on_press(self, event):
        self.start = (event.x, event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#ff3333", width=2)

    def _on_drag(self, event):
        if self.start and self.rect_id:
            self.canvas.coords(self.rect_id, self.start[0], self.start[1], event.x, event.y)

    def _on_release(self, event):
        if not self.start:
            return
        x0, y0 = self.start
        x1, y1 = event.x, event.y
        self.start = None
        x, y = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0), abs(y1 - y0)
        if w < 5 or h < 5:
            return

        if self.preset:
            if self.preset_index >= len(PRESET_ORDER):
                return
            name = PRESET_ORDER[self.preset_index][0]
        else:
            name = simpledialog.askstring("保存模板", "文件名（英文/拼音）：", parent=self.root)
            if not name:
                self.canvas.delete(self.rect_id)
                self.rect_id = None
                return
            name = name.strip()

        crop = self.bgr[y:y + h, x:x + w]
        out = ASSETS / (name + ".png")
        imwrite_unicode(str(out), crop)
        self.count += 1
        print("已保存: %s  (%dx%d)" % (out, w, h))
        self.canvas.delete(self.rect_id)
        self.rect_id = None

        if self.preset:
            self.preset_index += 1
            if self.preset_index >= len(PRESET_ORDER):
                print("\n预设全部完成！共 %d 个模板。" % self.count)
        self._hint()

    def _quit(self):
        print("共保存 %d 个模板到 %s" % (self.count, ASSETS))
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", action="store_true",
                        help="按预设按钮清单依次框选")
    args = parser.parse_args()
    root = tk.Tk()
    Grabber(root, preset=args.preset)
    root.mainloop()


if __name__ == "__main__":
    main()
