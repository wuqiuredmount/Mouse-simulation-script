"""拟人化鼠标：贝塞尔轨迹 + 缓动 + 过冲 + 微抖 + 自然时序。"""

import math
import random
import time
from typing import Tuple

from src.action.mouse_driver import BaseDriver
from src.utils import geometry as geo
from src.utils.logger import get_logger

log = get_logger("quiz.action.mouse")

Point = Tuple[float, float]


class HumanMouse:
    def __init__(
        self,
        driver: BaseDriver,
        min_duration: float = 0.35,
        max_duration: float = 0.95,
        overshoot_prob: float = 0.6,
        tremor: float = 0.4,
        click_hold: Tuple[float, float] = (0.05, 0.14),
        pre_click_delay: Tuple[float, float] = (0.08, 0.25),
        speed: str = "human",
        dry_run: bool = False,
        click_count: int = 1,
        double_interval: Tuple[float, float] = (0.08, 0.18),
    ):
        self.driver = driver
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.overshoot_prob = overshoot_prob
        self.tremor = tremor
        self.click_hold = click_hold
        self.pre_click_delay = pre_click_delay
        self.speed = speed
        self.dry_run = dry_run
        self.click_count = max(1, int(click_count))
        self.double_interval = double_interval

    # ---------- 时序模型 ----------

    def _duration_for(self, dist: float) -> float:
        """根据距离决定移动时长（Fitts 定律近似 + 随机化）。"""
        if self.speed == "instant":
            return 0.0
        base = self.min_duration + (self.max_duration - self.min_duration) * min(dist / 1200.0, 1.0)
        return geo.clamp(base * random.uniform(0.85, 1.2), 0.08, self.max_duration * 1.4)

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """平滑缓动（类似 minimum-jerk 的手感）。"""
        return t * t * (3 - 2 * t)

    # ---------- 移动 ----------

    def move(self, x: float, y: float) -> None:
        """人类式移动到 (x, y)。"""
        start = self.driver.position()
        target: Point = (x, y)
        dist = geo.distance(start, target)

        if self.speed == "instant" or dist < 2:
            self._safe_move(x, y)
            return

        duration = self._duration_for(dist)
        steps = max(12, int(duration * 60))  # 约 60 步/秒

        # 过冲：先冲过目标一点点，再回来
        end = target
        if random.random() < self.overshoot_prob and dist > 120:
            over = random.uniform(0.02, 0.08) * dist
            ang = math.atan2(target[1] - start[1], target[0] - start[0])
            end = (target[0] + math.cos(ang) * over,
                   target[1] + math.sin(ang) * over)

        path = geo.build_path(start, end, steps, spread=0.25)

        t0 = time.perf_counter()
        for i, (px, py) in enumerate(path):
            # 缓动：把线性进度映射到非线性时间
            progress = self._ease_in_out((i + 1) / steps)
            # 微抖动：模拟手部震颤
            if self.tremor > 0:
                px += random.uniform(-self.tremor, self.tremor)
                py += random.uniform(-self.tremor, self.tremor)
            self._safe_move(int(px), int(py))
            # 按缓动节奏 sleep
            target_elapsed = duration * progress
            now = time.perf_counter() - t0
            if target_elapsed > now:
                time.sleep(target_elapsed - now)

        # 过冲后的小幅回修正
        if end != target:
            self._correct(target)

    def _correct(self, target: Point) -> None:
        """从当前位置微调到目标（模拟修正动作）。"""
        cur = self.driver.position()
        path = geo.build_path(cur, target, random.randint(3, 6), spread=0.1)
        for px, py in path:
            self._safe_move(int(px), int(py))
            time.sleep(random.uniform(0.005, 0.02))

    def _safe_move(self, x: int, y: int) -> None:
        if self.dry_run:
            return
        try:
            self.driver.move_to(x, y)
        except Exception:  # pyautogui FAILSAFE 触发时抛异常
            log.warning("移动被中断（可能触发了 failsafe）")
            raise

    # ---------- 点击 ----------

    def click(self, x: float, y: float) -> None:
        """拟人点击：移动 -> 停顿 -> 按下(带时长) -> 松开。
        可点 click_count 次（默认 2 下，模拟双击）。
        """
        self.move(x, y)
        time.sleep(random.uniform(*self.pre_click_delay))
        if self.dry_run:
            log.info("[dry-run] 点击 (%d, %d) x%d", int(x), int(y), self.click_count)
            return
        for i in range(self.click_count):
            self.driver.mouse_down()
            time.sleep(random.uniform(*self.click_hold))
            self.driver.mouse_up()
            if i < self.click_count - 1:
                time.sleep(random.uniform(*self.double_interval))
        log.info("已点击 (%d, %d) x%d", int(x), int(y), self.click_count)

    # ---------- 人类式等待 ----------

    @staticmethod
    def human_delay(mean: float, jitter: float = 0.3) -> None:
        """正态分布的随机停顿，比固定 sleep 更自然。"""
        time.sleep(max(0.0, random.gauss(mean, mean * jitter)))
