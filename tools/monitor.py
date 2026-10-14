"""界面监控工具：截取游戏窗口/全屏，保存到 data/monitor/，供 AI 查看与学习。

用法：
    python tools/monitor.py                  # 截一次全屏 -> latest.png
    python tools/monitor.py --window 三国     # 截标题含“三国”的窗口
    python tools/monitor.py --watch 2        # 每 2 秒截一张（持续监控）

截出的图保存到：data/monitor/
  latest.png         最新一张（AI 读这个）
  shot_日期_时间.png  带时间戳的历史
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.winenv import ensure_dpi_aware

ensure_dpi_aware()

import mss
import numpy as np

from src.utils.imaging import imwrite_unicode

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "monitor"
OUT.mkdir(parents=True, exist_ok=True)


def find_window_rect(keyword: str):
    """找标题含关键字的窗口，返回 (left, top, width, height)；找不到返回 None。"""
    try:
        import pygetwindow as gw
    except Exception:
        return None
    for w in gw.getAllWindows():
        if keyword in (w.title or "") and w.width > 100 and w.height > 100:
            return (w.left, w.top, w.width, w.height)
    return None


def capture(region=None) -> np.ndarray:
    sct = mss.mss()
    if region is None:
        mon = sct.monitors[1]
        box = mon
    else:
        left, top, width, height = region
        box = {"left": left, "top": top, "width": width, "height": height}
    raw = np.array(sct.grab(box))
    return raw[:, :, :3].copy()


def save(img: np.ndarray) -> None:
    latest = OUT / "latest.png"
    imwrite_unicode(str(latest), img)
    ts = time.strftime("%Y%m%d_%H%M%S")
    imwrite_unicode(str(OUT / ("shot_" + ts + ".png")), img)
    print("已保存:", latest, "尺寸:", img.shape[1], "x", img.shape[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", default=None, help="窗口标题关键字，如 三国")
    parser.add_argument("--watch", type=float, default=None, help="每隔 N 秒截一张")
    args = parser.parse_args()

    region = None
    if args.window:
        region = find_window_rect(args.window)
        if region is None:
            print("[warn] 没找到窗口:", args.window, "-> 改为截全屏")
        else:
            print("找到窗口区域:", region)

    if args.watch:
        print("持续监控中，每 %.1f 秒一张。Ctrl+C 停止。" % args.watch)
        try:
            while True:
                save(capture(region))
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("已停止。")
        return

    save(capture(region))


if __name__ == "__main__":
    main()
