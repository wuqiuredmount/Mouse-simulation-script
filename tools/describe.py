"""界面自动描述工具：截图 + OCR + 输出文字描述，供 AI 学习。

用法：
    python tools/describe.py --window 三国

输出：
    data/monitor/latest.png    最新截图（AI 看这个）
    data/monitor/latest.txt    最新文字描述（AI 读这个）
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
from src.vision.ocr_engine import create_ocr

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "monitor"
OUT.mkdir(parents=True, exist_ok=True)


def find_window_rect(keyword: str):
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
    box = sct.monitors[1] if region is None else {
        "left": region[0], "top": region[1],
        "width": region[2], "height": region[3]}
    raw = np.array(sct.grab(box))
    return raw[:, :, :3].copy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", default=None, help="窗口标题关键字")
    args = parser.parse_args()

    region = find_window_rect(args.window) if args.window else None
    if args.window and region is None:
        print("[warn] 没找到窗口，改截全屏")

    img = capture(region)
    imwrite_unicode(str(OUT / "latest.png"), img)

    print("正在 OCR 识别文字…")
    # 大图先降采样，显著加快 OCR（保持宽高比）
    max_w = 1280
    if img.shape[1] > max_w:
        scale = max_w / img.shape[1]
        import cv2
        img_small = cv2.resize(img, (max_w, int(img.shape[0] * scale)))
    else:
        img_small = img
    ocr = create_ocr("paddle", "ch")
    text = ocr.read_text(img_small)

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    desc = (
        "时间: %s\n窗口区域: %s\n图像尺寸: %dx%d\n"
        "----- OCR 识别到的文字 -----\n%s\n"
        % (ts, region, img.shape[1], img.shape[0], text)
    )
    (OUT / "latest.txt").write_text(desc, encoding="utf-8")
    print("已保存: data/monitor/latest.txt")
    print("--- 识别文字 ---")
    print(text)


if __name__ == "__main__":
    main()
