"""屏幕截图模块：把指定区域抓成 numpy 图像。"""

from typing import Optional

import numpy as np

from src.utils.logger import get_logger

log = get_logger("quiz.capture")


class ScreenCapture:
    """封装截图后端，统一返回 BGR numpy 数组。"""

    def __init__(self, backend: str = "mss", monitor: int = 1):
        self.backend = backend
        self.monitor = monitor
        self._sct = None
        self._pg = None

        if backend == "mss":
            import mss  # 延迟导入，未安装时不影响其他后端
            self._sct = mss.mss()
        elif backend == "pyautogui":
            import pyautogui
            self._pg = pyautogui
        else:
            raise ValueError(f"未知截图后端: {backend}")

    def grab(self, region: Optional[dict] = None) -> np.ndarray:
        """抓取 region={x,y,w,h} 区域；region=None 时抓整个屏幕。
        返回 BGR 顺序的 numpy 数组（cv2 默认顺序）。
        """
        if self.backend == "mss":
            if region is None:
                mon = self._sct.monitors[self.monitor]
                box = {"left": mon["left"], "top": mon["top"],
                       "width": mon["width"], "height": mon["height"]}
            else:
                box = {"left": region["x"], "top": region["y"],
                       "width": region["w"], "height": region["h"]}
            raw = np.array(self._sct.grab(box))  # BGRA
            return raw[:, :, :3].copy()          # 去 alpha -> BGR

        # pyautogui 后端
        if region is None:
            raw = self._pg.screenshot()
        else:
            raw = self._pg.screenshot(region=(region["x"], region["y"],
                                              region["w"], region["h"]))
        return np.array(raw)[:, :, ::-1].copy()  # RGB -> BGR
