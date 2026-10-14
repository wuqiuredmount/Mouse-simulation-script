"""通用按钮自动点击器。

工作原理：
  循环截图全屏 -> 对每个按钮模板做匹配 -> 命中则拟人点击其中心。
  每轮只点一个（匹配度最高的），然后重新截图，避免误连点。
"""

import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from src.action.human_mouse import HumanMouse
from src.capture.screen_capture import ScreenCapture
from src.utils.imaging import imread_unicode
from src.utils.logger import get_logger

log = get_logger("quiz.tasks.clicker")


class Button:
    """一个可点击的按钮模板。"""

    def __init__(self, name: str, template_path: str, threshold: float = 0.85,
                 cooldown: float = 2.0, enabled: bool = True):
        self.name = name
        self.template_path = template_path
        self.threshold = threshold
        self.cooldown = cooldown
        self.enabled = enabled
        self.template = None
        self.last_click = 0.0

    def load(self) -> bool:
        img = imread_unicode(self.template_path)
        if img is None:
            log.warning("模板读取失败: %s -> %s", self.name, self.template_path)
            return False
        self.template = img
        return True

    def ready(self, now: float) -> bool:
        if not self.enabled or self.template is None:
            return False
        return (now - self.last_click) >= self.cooldown

    def mark(self, now: float) -> None:
        self.last_click = now


class TemplateClicker:
    """检测屏幕上的按钮模板并拟人点击。"""

    def __init__(self, buttons: List[Button], capture: ScreenCapture,
                 mouse: HumanMouse, scan_interval: float = 0.6,
                 dry_run: bool = False):
        self.buttons = [b for b in buttons if b.load()]
        self.capture = capture
        self.mouse = mouse
        self.scan_interval = scan_interval
        self.dry_run = dry_run
        self._stop = False

    def _match(self, screen: np.ndarray, btn: Button) -> Tuple[Optional[Tuple[int, int]], float]:
        res = cv2.matchTemplate(screen, btn.template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val < btn.threshold:
            return None, float(max_val)
        th, tw = btn.template.shape[:2]
        center = (max_loc[0] + tw // 2, max_loc[1] + th // 2)
        return center, float(max_val)

    def tick(self) -> bool:
        """执行一轮检测+点击。返回是否点了东西。"""
        screen = self.capture.grab(None)
        now = time.time()
        best_btn: Optional[Button] = None
        best_pos = None
        best_score = 0.0

        for btn in self.buttons:
            if not btn.ready(now):
                continue
            pos, score = self._match(screen, btn)
            if pos is not None and score > best_score:
                best_btn, best_pos, best_score = btn, pos, score

        if best_btn is None:
            return False

        log.info("点击按钮 [%s] 匹配度=%.2f 位置=%s", best_btn.name, best_score, best_pos)
        if self.dry_run:
            log.info("[dry-run] 不实际点击")
        else:
            self.mouse.click(best_pos[0], best_pos[1])
        best_btn.mark(time.time())
        return True

    def run(self, max_loops: Optional[int] = None) -> None:
        log.info("按钮点击器启动：共 %d 个模板, 间隔=%.2fs, dry_run=%s",
                 len(self.buttons), self.scan_interval, self.dry_run)
        loops = 0
        try:
            while not self._stop:
                try:
                    self.tick()
                except Exception as e:  # noqa
                    log.error("tick 异常: %s", e)
                loops += 1
                if max_loops and loops >= max_loops:
                    break
                time.sleep(self.scan_interval)
        except KeyboardInterrupt:
            log.info("用户中断。")
        finally:
            log.info("按钮点击器已停止。")

    def stop(self) -> None:
        self._stop = True
