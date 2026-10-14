"""模板匹配：在屏幕中定位图标/按钮，返回中心坐标。"""

from typing import Optional, Tuple

import cv2
import numpy as np

from src.utils.logger import get_logger

log = get_logger("quiz.vision.template")


class TemplateMatcher:
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def find(
        self,
        screen: np.ndarray,
        template: np.ndarray,
        region_offset: Tuple[int, int] = (0, 0),
    ) -> Optional[Tuple[int, int]]:
        """在 screen 中寻找 template，返回屏幕绝对坐标中心点 (x, y)。
        region_offset 是 screen 相对屏幕原点的偏移，用于换算绝对坐标。
        """
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val < self.threshold:
            return None
        th, tw = template.shape[:2]
        cx = region_offset[0] + max_loc[0] + tw // 2
        cy = region_offset[1] + max_loc[1] + th // 2
        log.debug("模板命中 val=%.3f at (%d,%d)", max_val, cx, cy)
        return cx, cy
