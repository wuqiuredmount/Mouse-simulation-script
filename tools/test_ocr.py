"""OCR 后端自测：生成一张含中英文的图片，调用 PaddleOCR 识别并打印结果。"""

import sys
from pathlib import Path

# 允许以 `python tools/test_ocr.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import cv2

from src.vision.ocr_engine import create_ocr


def make_image() -> np.ndarray:
    img = np.full((120, 640, 3), 255, dtype=np.uint8)
    cv2.putText(img, "Hello 12", (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 0), 4)
    return img


def main() -> None:
    ocr = create_ocr("paddle", "ch")
    img = make_image()
    text = ocr.read_text(img)
    print("=== OCR RESULT ===")
    print(repr(text))


if __name__ == "__main__":
    main()
