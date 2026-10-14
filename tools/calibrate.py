"""鼠标框选坐标校准工具。

用法：
    python tools/calibrate.py          # 交互式全屏框选
    python tools/calibrate.py --test   # 用假坐标测试保存逻辑（不弹窗）
"""

import argparse
import ctypes
import sys
from pathlib import Path

# Windows 高 DPI：必须在创建任何 GUI 前声明 DPI 感知，否则
# tkinter 报告的坐标与实际屏幕像素不一致。
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGIONS_PATH = ROOT / "config" / "regions.yaml"

# 框选步骤：(结果键, 中文提示)
STEPS = [
    ("question", "题干显示区域"),
    ("option0", "选项 1"),
    ("option1", "选项 2"),
    ("option2", "选项 3"),
    ("option3", "选项 4"),
]


def load_existing(path: Path) -> dict:
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_regions(results: dict, path: Path) -> None:
    """把框选结果写入 regions.yaml，保留 trigger 等其它字段。"""
    data = load_existing(path)
    regions = data.setdefault("regions", {})
    if "question" in results:
        regions["question"] = dict(results["question"])
    options = []
    for i in range(4):
        key = f"option{i}"
        if key in results:
            opt = dict(results[key])
            opt["id"] = i
            options.append(opt)
    if options:
        regions["options"] = options
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def run_test() -> None:
    fake = {
        "question": {"x": 400, "y": 200, "w": 1120, "h": 220},
        "option0": {"x": 450, "y": 480, "w": 1020, "h": 90},
        "option1": {"x": 450, "y": 590, "w": 1020, "h": 90},
        "option2": {"x": 450, "y": 700, "w": 1020, "h": 90},
        "option3": {"x": 450, "y": 810, "w": 1020, "h": 90},
    }
    out = ROOT / "config" / "regions.calibrated.yaml"
    save_regions(fake, out)
    print(f"[test] 已写入 {out}")
    print(out.read_text(encoding="utf-8"))


class Calibrator:
    def __init__(self, root):
        import tkinter as tk
        self.tk = tk
        self.root = root
        self.step_index = 0
        self.start = None
        self.rect_id = None
        self.results = {}

        root.title("坐标校准 - AI 答题助手")
        root.attributes("-fullscreen", True)
        root.attributes("-alpha", 0.35)
        root.attributes("-topmost", True)
        root.configure(bg="black")

        self.canvas = tk.Canvas(root, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        root.bind("<Escape>", lambda e: self._cancel())

        self._draw_prompt()

    def _draw_prompt(self):
        self.canvas.delete("prompt")
        if self.step_index >= len(STEPS):
            return
        _, label = STEPS[self.step_index]
        text = (
            f"第 {self.step_index + 1}/{len(STEPS)} 步：请框选【{label}】\n"
            f"按住鼠标左键拖动画出矩形，松开即确认    |    ESC 取消"
        )
        self.canvas.create_rectangle(0, 0, self.canvas.winfo_screenwidth(), 120,
                                     fill="#0d0d0d", outline="", tags="prompt")
        self.canvas.create_text(24, 60, anchor="w", text=text,
                                fill="#00ff88",
                                font=("Microsoft YaHei", 16, "bold"), tags="prompt")

    def _on_press(self, event):
        if self.step_index >= len(STEPS):
            return
        self.start = (event.x, event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#00ff88", width=2, tags="rect")

    def _on_drag(self, event):
        if self.start is None or self.rect_id is None:
            return
        self.canvas.coords(self.rect_id, self.start[0], self.start[1], event.x, event.y)

    def _on_release(self, event):
        if self.start is None:
            return
        x0, y0 = self.start
        x1, y1 = event.x, event.y
        self.start = None
        x, y = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0), abs(y1 - y0)
        if w < 5 or h < 5:
            return
        key, _ = STEPS[self.step_index]
        self.results[key] = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
        print(f"[{key}] x={x} y={y} w={w} h={h}")
        self.step_index += 1
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        if self.step_index >= len(STEPS):
            self._finish()
        else:
            self._draw_prompt()

    def _finish(self):
        save_regions(self.results, REGIONS_PATH)
        self.canvas.delete("all")
        sw = self.canvas.winfo_screenwidth()
        sh = self.canvas.winfo_screenheight()
        body = "\n".join(f"{k}: {v}" for k, v in self.results.items())
        self.canvas.create_text(
            sw // 2, sh // 2,
            text=f"校准完成，已保存到 regions.yaml\n\n{body}\n\n窗口即将自动关闭…",
            fill="#00ff88", font=("Microsoft YaHei", 18, "bold"), justify="center")
        print(f"\n已保存到 {REGIONS_PATH}")
        self.root.after(2500, self.root.destroy)

    def _cancel(self):
        print("已取消，未保存。")
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="鼠标框选坐标校准工具")
    parser.add_argument("--test", action="store_true", help="用假坐标测试保存逻辑，不弹窗")
    args = parser.parse_args()

    if args.test:
        run_test()
        return

    import tkinter as tk
    root = tk.Tk()
    Calibrator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
