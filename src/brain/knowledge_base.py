"""题库管理：加载固定题目与答案。"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from src.utils.logger import get_logger

log = get_logger("quiz.brain.kb")


@dataclass
class Question:
    id: str
    question: str
    answer: str
    options: List[str]
    answer_index: Optional[int] = None
    match: str = "fuzzy"


class KnowledgeBase:
    def __init__(self, path: str):
        self.path = Path(path)
        self.questions: List[Question] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            log.warning("题库文件不存在: %s", self.path)
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for item in raw.get("questions", []):
            self.questions.append(
                Question(
                    id=item.get("id", ""),
                    question=item.get("question", ""),
                    answer=item.get("answer", ""),
                    options=item.get("options", []),
                    answer_index=item.get("answer_index"),
                    match=item.get("match", "fuzzy"),
                )
            )
        log.info("已加载 %d 道题目", len(self.questions))

    def all(self) -> List[Question]:
        return self.questions
