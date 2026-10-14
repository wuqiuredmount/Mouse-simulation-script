"""高层动作：把“答题”封装成一个动作。"""

import random
import time

from src.action.human_mouse import HumanMouse
from src.utils.logger import get_logger

log = get_logger("quiz.action")


class Actions:
    def __init__(self, mouse: HumanMouse, think_delay=(0.3, 0.9)):
        self.mouse = mouse
        self.think_delay = think_delay

    def answer(self, option_region: dict) -> None:
        """点击某个选项区域的中心（带人类思考延迟）。"""
        cx = option_region["x"] + option_region["w"] / 2
        cy = option_region["y"] + option_region["h"] / 2
        time.sleep(random.uniform(*self.think_delay))  # 思考
        self.mouse.click(cx, cy)
