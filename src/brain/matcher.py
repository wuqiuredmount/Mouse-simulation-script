"""题目匹配：把识别到的题干映射到题库中的正确答案。"""

import difflib
import re
from typing import Optional

from src.brain.knowledge_base import KnowledgeBase, Question
from src.utils.logger import get_logger

log = get_logger("quiz.brain.matcher")


def _normalize(text: str) -> str:
    """去除空白与常见标点，便于比对。"""
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[，。！？、：；,.!?;:\"'（）()【】\[\]]", "", text)


class Matcher:
    def __init__(self, kb: KnowledgeBase, mode: str = "fuzzy", threshold: float = 0.8):
        self.kb = kb
        self.mode = mode
        self.threshold = threshold

    def match(self, recognized: str) -> Optional[Question]:
        """返回最匹配的题目，找不到返回 None。"""
        if not recognized:
            return None
        target = _normalize(recognized)
        best: Optional[Question] = None
        best_score = 0.0

        for q in self.kb.all():
            norm_q = _normalize(q.question)
            if self.mode == "exact":
                if norm_q == target:
                    return q
                continue
            if self.mode == "contains":
                if norm_q and (norm_q in target or target in norm_q):
                    return q
                continue
            # fuzzy
            score = difflib.SequenceMatcher(None, norm_q, target).ratio()
            if score > best_score:
                best_score, best = score, q

        if best is not None and best_score >= self.threshold:
            log.info("匹配到题目 %s (相似度 %.2f)", best.id, best_score)
            return best
        log.info("未匹配到题目 (最高相似度 %.2f)", best_score)
        return None

    def locate_answer_option(self, question: Question, option_texts) -> Optional[int]:
        """在识别到的各选项文字里，找出正确答案所在的选项序号。
        option_texts: List[str]，按界面顺序的选项文字。
        返回选项索引，找不到返回 None。
        """
        ans = _normalize(question.answer)
        # 先精确/包含匹配
        for idx, opt in enumerate(option_texts):
            norm_opt = _normalize(opt)
            if norm_opt and (norm_opt == ans or ans in norm_opt or norm_opt in ans):
                return idx
        # 再模糊匹配
        best_idx, best_score = None, 0.0
        for idx, opt in enumerate(option_texts):
            score = difflib.SequenceMatcher(None, _normalize(opt), ans).ratio()
            if score > best_score:
                best_score, best_idx = score, idx
        if best_idx is not None and best_score >= self.threshold:
            return best_idx
        # 兜底：题库里若直接给了 answer_index
        return question.answer_index
