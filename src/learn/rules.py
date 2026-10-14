"""学习型规则的数据模型与加载。

规则结构（config/rules.yaml）：
  rules:
    - id: start_round
      desc: 开始一轮
      when_visible: [sr_shang, sr_dispatch]   # 这些模板都可见才触发
      when_any: [sr_help]                      # 或：任一可见即触发（可选）
      action:
        - click: sr_shang
        - wait: 1.0
        - click: sr_dispatch
      cooldown: 3.0
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from src.utils.logger import get_logger

log = get_logger("quiz.learn.rules")


@dataclass
class ActionStep:
    type: str                 # click | click_at | wait
    target: Any = None        # 模板名 / [x, y] / 秒数


@dataclass
class Rule:
    id: str
    desc: str
    when_visible: List[str] = field(default_factory=list)
    when_any: List[str] = field(default_factory=list)
    action: List[ActionStep] = field(default_factory=list)
    cooldown: float = 2.0
    last_run: float = 0.0

    def ready(self, now: float) -> bool:
        return (now - self.last_run) >= self.cooldown


@dataclass
class RuleSet:
    settings: Dict[str, Any]
    rules: List[Rule]
    mtime: float = 0.0
    thresholds: dict = field(default_factory=dict)

    def find(self, visible: Set[str], now: float) -> Optional[Rule]:
        """按顺序返回第一条满足条件且冷却结束的规则。"""
        for r in self.rules:
            if not r.ready(now):
                continue
            if r.when_visible and not set(r.when_visible).issubset(visible):
                continue
            if r.when_any and not (set(r.when_any) & visible):
                continue
            if not r.when_visible and not r.when_any:
                continue
            return r
        return None

    def is_partial_match(self, visible: Set[str]) -> bool:
        """当前可见集合是否为某条规则条件的【非空子集】。
        是的话说明该规则的动作正在进行（部分元素暂时消失），应等待而非报警。
        """
        if not visible:
            return False
        for r in self.rules:
            cond = set(r.when_visible) | set(r.when_any)
            if cond and visible.issubset(cond):
                return True
        return False

    def matches_condition(self, visible: Set[str]) -> bool:
        """是否有任意规则的条件与当前可见集合匹配（忽略冷却）。
        用于区分“认识、只是冷却中”与“真正未知”。
        """
        for r in self.rules:
            if r.when_visible and set(r.when_visible).issubset(visible):
                return True
            if r.when_any and (set(r.when_any) & visible):
                return True
        return False

    def needed_templates(self) -> List[str]:
        names: Set[str] = set()
        for r in self.rules:
            names.update(r.when_visible)
            names.update(r.when_any)
            for a in r.action:
                if a.type == "click" and isinstance(a.target, str):
                    names.add(a.target)
        return sorted(names)


def _parse_action(items: List[Any]) -> List[ActionStep]:
    steps: List[ActionStep] = []
    for item in items or []:
        if not isinstance(item, dict) or len(item) != 1:
            continue
        key, val = next(iter(item.items()))
        key = str(key).strip().lower()
        if key == "click":
            steps.append(ActionStep("click", val))
        elif key in ("click_at", "clickat"):
            steps.append(ActionStep("click_at", val))
        elif key == "wait":
            steps.append(ActionStep("wait", float(val)))
        elif key in ("repeat_click", "repeatclick"):
            # val = {x, y, interval, duration} 或 {template, interval, duration}
            steps.append(ActionStep("repeat_click", val))
        elif key == "pause":
            steps.append(ActionStep("pause", val))
    return steps


def load_ruleset(path: Path) -> RuleSet:
    if not path.exists():
        log.warning("规则文件不存在: %s", path)
        return RuleSet(settings={}, rules=[], mtime=0.0)
    mtime = path.stat().st_mtime
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    settings = raw.get("settings", {}) or {}
    thresholds = raw.get("thresholds", {}) or {}
    rules: List[Rule] = []
    for item in raw.get("rules", []) or []:
        rules.append(Rule(
            id=item.get("id", ""),
            desc=item.get("desc", item.get("id", "")),
            when_visible=list(item.get("when_visible", []) or []),
            when_any=list(item.get("when_any", []) or []),
            action=_parse_action(item.get("action", [])),
            cooldown=float(item.get("cooldown", 2.0)),
        ))
    log.info("已加载 %d 条规则", len(rules))
    return RuleSet(settings=settings, rules=rules, mtime=mtime, thresholds=thresholds)
