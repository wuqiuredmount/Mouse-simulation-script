"""图像读写工具：支持中文路径（cv2.imread/imwrite 在 Windows 上对中文路径支持不佳）。"""

import os

import cv2
import numpy as np


def imread_unicode(path: str) -> "np.ndarray | None":
    """读取图像，支持中文路径。失败返回 None。"""
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def imwrite_unicode(path: str, image: np.ndarray) -> bool:
    """写入图像，支持中文路径。成功返回 True。"""
    ext = os.path.splitext(path)[1] or ".png"
    try:
        ok, buf = cv2.imencode(ext, image)
        if not ok:
            return False
        buf.tofile(path)
        return True
    except Exception:
        return False
