"""核心引擎：驱动 感知->识别->决策->执行 主循环。"""

import time
from typing import List, Optional

from src.action.actions import Actions
from src.action.human_mouse import HumanMouse
from src.brain.knowledge_base import KnowledgeBase
from src.brain.matcher import Matcher
from src.capture.screen_capture import ScreenCapture
from src.core.state import State
from src.utils.logger import get_logger
from src.vision.ocr_engine import create_ocr

log = get_logger("quiz.engine")


class Engine:
    def __init__(self, settings: dict, regions: dict, kb_path: str):
        self.settings = settings
        self.regions = regions
        self.state = State.IDLE
        self._last_answer = ""          # 去重：同一题不重复点
        self._cooldown_until = 0.0

        # --- 组装各模块 ---
        cap_cfg = settings["capture"]
        self.capture = ScreenCapture(cap_cfg["backend"], cap_cfg["monitor"])
        self.fps = cap_cfg.get("fps", 5)

        vis_cfg = settings["vision"]
        self.ocr = create_ocr(vis_cfg["ocr_backend"], vis_cfg.get("ocr_lang", "chi_sim+eng"))

        brain_cfg = settings["brain"]
        self.kb = KnowledgeBase(kb_path)
        self.matcher = Matcher(self.kb, brain_cfg["match_mode"], brain_cfg["fuzzy_threshold"])

        mouse_cfg = settings["mouse"]
        from src.action.mouse_driver import create_driver
        self.driver = create_driver(mouse_cfg["driver"], settings["safety"]["failsafe"])
        self.mouse = HumanMouse(
            self.driver,
            min_duration=mouse_cfg["min_duration"],
            max_duration=mouse_cfg["max_duration"],
            overshoot_prob=mouse_cfg["overshoot_prob"],
            tremor=mouse_cfg["tremor"],
            click_hold=tuple(mouse_cfg["click_hold"]),
            pre_click_delay=tuple(mouse_cfg["pre_click_delay"]),
            speed=mouse_cfg["speed"],
            dry_run=settings["safety"]["dry_run"],
        )
        self.actions = Actions(self.mouse, tuple(settings["brain"]["think_delay"]))

        self.cooldown = 1.5  # 点击后冷却秒数

    # ---------- 单步 ----------

    def _read_question(self) -> str:
        img = self.capture.grab(self.regions["question"])
        return self.ocr.read_text(img)

    def _read_options(self) -> List[str]:
        texts = []
        for opt in self.regions["options"]:
            img = self.capture.grab(opt)
            texts.append(self.ocr.read_text(img))
        return texts

    def tick(self) -> None:
        """执行一轮检测。由 run() 循环调用。"""
        # 冷却期
        if time.time() < self._cooldown_until:
            self.state = State.COOLDOWN
            return

        self.state = State.DETECTING
        question_text = self._read_question()
        if not question_text or question_text == self._last_answer:
            self.state = State.IDLE
            return

        self.state = State.DECIDING
        matched = self.matcher.match(question_text)
        if matched is None:
            log.debug("题干未匹配: %r", question_text[:40])
            self.state = State.IDLE
            return

        options = self._read_options()
        idx = self.matcher.locate_answer_option(matched, options)
        if idx is None or idx >= len(self.regions["options"]):
            log.warning("未能定位正确选项，跳过。")
            self.state = State.IDLE
            return

        self.state = State.ACTING
        log.info("题目 %s -> 选项 %d: %s", matched.id, idx, matched.answer)
        self.actions.answer(self.regions["options"][idx])

        self._last_answer = question_text
        self._cooldown_until = time.time() + self.cooldown
        self.state = State.COOLDOWN

    # ---------- 主循环 ----------

    def run(self, max_loops: Optional[int] = None) -> None:
        log.info("引擎启动 (fps=%s, dry_run=%s)", self.fps, self.settings["safety"]["dry_run"])
        interval = 1.0 / max(1, self.fps)
        loops = 0
        try:
            while self.state != State.STOPPED:
                start = time.time()
                try:
                    self.tick()
                except Exception as e:  # noqa
                    log.error("tick 异常: %s", e)
                loops += 1
                if max_loops and loops >= max_loops:
                    break
                elapsed = time.time() - start
                if elapsed < interval:
                    time.sleep(interval - elapsed)
        except KeyboardInterrupt:
            log.info("用户中断，停止。")
        finally:
            self.state = State.STOPPED
            log.info("引擎已停止。")

    def stop(self) -> None:
        self.state = State.STOPPED
