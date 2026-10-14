"""选择事件处理器：识别题干 -> 查知识库 -> 点正确选项。

用于游戏中弹出的 A/B/C 决策事件（如“当机立断”）。
未知事件会返回 None，交由上层保存并暂停。
"""

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import yaml

from src.capture.screen_capture import ScreenCapture
from src.utils.logger import get_logger
from src.vision.ocr_engine import create_ocr

log = get_logger("quiz.tasks.choice")

ROOT = Path(__file__).resolve().parent.parent.parent


class ChoiceEvent:
    def __init__(self, eid: str, keywords: List[str], answer: str, note: str = ""):
        self.id = eid
        self.keywords = keywords
        self.answer = answer
        self.note = note


class ChoiceHandler:
    def __init__(self, capture: ScreenCapture, ocr_backend: str = "paddle",
                 choices_path: Optional[Path] = None):
        self.capture = capture
        self.ocr = create_ocr(ocr_backend, "ch")
        self.path = Path(choices_path) if choices_path else (ROOT / "config" / "choices.yaml")
        self.settings: Dict = {}
        self.option_buttons: Dict = {}
        self.events: List[ChoiceEvent] = []
        self._mtime = 0.0
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            log.warning("选择事件库不存在: %s", self.path)
            return
        with self.path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        self.settings = raw.get("settings", {}) or {}
        self.option_buttons = raw.get("option_buttons", {}) or {}
        self.events = []
        for item in raw.get("events", []) or []:
            self.events.append(ChoiceEvent(
                eid=item.get("id", ""),
                keywords=list(item.get("question_keywords", []) or []),
                answer=str(item.get("answer", "")).strip().upper(),
                note=item.get("note", ""),
            ))
        self._mtime = self.path.stat().st_mtime
        log.info("已加载 %d 个选择事件", len(self.events))

    def reload_if_changed(self) -> None:
        try:
            if self.path.stat().st_mtime != self._mtime:
                log.info("选择事件库有更新，重新加载。")
                self.reload()
        except OSError:
            pass

    def read_question(self, region: dict) -> str:
        """读取题干区域的文字。"""
        img = self.capture.grab(region)
        return self.ocr.read_text(img)

    def match(self, question_text: str) -> Optional[ChoiceEvent]:
        """根据题干文字匹配事件。返回命中的事件或 None。"""
        if not question_text:
            return None
        threshold = float(self.settings.get("match_threshold", 0.6))
        best, best_ratio = None, 0.0
        for ev in self.events:
            if not ev.keywords:
                continue
            hit = sum(1 for kw in ev.keywords if kw in question_text)
            ratio = hit / len(ev.keywords)
            if ratio > best_ratio:
                best_ratio, best = ratio, ev
        if best is not None and best_ratio >= threshold:
            log.info("匹配到事件 %s (命中率 %.2f) -> 答案 %s", best.id, best_ratio, best.answer)
            return best
        return None

    def option_center(self, letter: str):
        btn = self.option_buttons.get(letter.upper())
        if not btn or btn.get("w", 0) == 0:
            return None
        return (btn["x"] + btn["w"] // 2, btn["y"] + btn["h"] // 2)
