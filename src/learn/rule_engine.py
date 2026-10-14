"""学习型规则引擎。

循环逻辑：
  截图 -> 检测可见模板集合 -> 匹配规则
    - 命中规则  -> 执行动作序列
    - 有可见但无规则 -> 【未知情况】保存截图并暂停，等待用户写新规则
    - 无任何可见模板 -> 空闲等待（不算未知）

规则文件被修改后会自动重新加载。
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

from src.action.human_mouse import HumanMouse
from src.action.mouse_driver import create_driver
from src.capture.screen_capture import ScreenCapture
from src.core.status import EngineStatus
from src.learn.rules import Rule, RuleSet, load_ruleset
from src.utils import agent_bridge
from src.utils.hotkey import HotkeyWatcher
from src.utils.imaging import imread_unicode, imwrite_unicode
from src.utils.logger import get_logger

log = get_logger("quiz.learn.engine")

ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS = ROOT / "data" / "assets"
UNKNOWN_DIR = ROOT / "data" / "unknown"


class TemplateLibrary:
    """按名字缓存模板图，并提供匹配。"""

    def __init__(self, folder: Path, names: List[str], threshold: float, thresholds: dict = None):
        self.folder = folder
        self.threshold = threshold
        self.thresholds = thresholds or {}
        self.templates: Dict[str, np.ndarray] = {}
        self.reload(names)

    def reload(self, names: List[str]) -> None:
        for n in names:
            if n in self.templates:
                continue
            img = imread_unicode(str(self.folder / (n + ".png")))
            if img is None:
                log.warning("模板缺失: %s", self.folder / (n + ".png"))
            else:
                self.templates[n] = img

    def match(self, screen: np.ndarray, name: str) -> Tuple[Optional[Tuple[int, int]], float]:
        tpl = self.templates.get(name)
        if tpl is None:
            return None, 0.0
        res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        thr = self.thresholds.get(name, self.threshold)
        if max_val < thr:
            return None, float(max_val)
        th, tw = tpl.shape[:2]
        return (max_loc[0] + tw // 2, max_loc[1] + th // 2), float(max_val)


class RuleEngine:
    def __init__(self, settings: dict, status: EngineStatus,
                 rules_path: Optional[Path] = None):
        self.settings = settings
        self.status = status
        self.rules_path = Path(rules_path) if rules_path else (ROOT / "config" / "rules.yaml")
        self.ruleset: RuleSet = load_ruleset(self.rules_path)

        cap = settings["capture"]
        self.capture = ScreenCapture(cap["backend"], cap["monitor"])
        self.mouse = self._build_mouse(settings)

        self.interval = float(self.ruleset.settings.get("scan_interval", 0.8))
        self.threshold = float(self.ruleset.settings.get("match_threshold", 0.85))
        self.lib = TemplateLibrary(ASSETS, self.ruleset.needed_templates(), self.threshold, self.ruleset.thresholds)

        self._stop = False
        self._paused = False
        self.hotkey = HotkeyWatcher(settings.get("safety", {}).get("hotkey_exit", "f1"))

        # 是否通过管理员代理执行点击（解决游戏以管理员运行时的 UIPI 拦截）
        self.use_agent = bool(settings.get("mouse", {}).get("use_admin_agent", False))
        self.agent_window = settings.get("mouse", {}).get("game_window", "三国")
        self._agent_ok = agent_bridge.agent_alive()

    def _agent_available(self) -> bool:
        if not self.use_agent:
            return False
        if self._agent_ok and agent_bridge.agent_alive():
            return True
        # 重试检测（代理可能稍后启动）
        self._agent_ok = agent_bridge.agent_alive()
        return self._agent_ok

    def _grab(self):
        """截取全屏。代理在线时走代理（管理员），确保画面与点击一致。"""
        if self._agent_available():
            try:
                out = ROOT / "data" / "monitor" / "_engine.png"
                agent_bridge.send("capture", {"path": str(out)})
                img = imread_unicode(str(out))
                if img is not None:
                    return img
            except Exception as e:  # noqa
                log.warning("代理截图失败(%s)，回退本地截图。", e)
                self._agent_ok = False
        return self.capture.grab(None)

    def _click_at(self, x: float, y: float) -> None:
        """点击绝对坐标：优先走管理员代理，否则退回本地鼠标。"""
        if self._agent_available():
            try:
                agent_bridge.send("click", {"x": int(x), "y": int(y),
                                            "window": self.agent_window})
                log.info("通过代理点击 (%d, %d)", int(x), int(y))
                return
            except Exception as e:  # noqa
                log.warning("代理点击失败(%s)，回退本地鼠标。", e)
                self._agent_ok = False
        self.mouse.click(x, y)

    @staticmethod
    def _build_mouse(settings: dict) -> HumanMouse:
        m = settings["mouse"]
        driver = create_driver(m["driver"], settings["safety"]["failsafe"])
        return HumanMouse(
            driver,
            min_duration=m["min_duration"],
            max_duration=m["max_duration"],
            overshoot_prob=m["overshoot_prob"],
            tremor=m["tremor"],
            click_hold=tuple(m["click_hold"]),
            pre_click_delay=tuple(m["pre_click_delay"]),
            speed=m["speed"],
            dry_run=settings["safety"]["dry_run"],
            click_count=m.get("click_count", 1),
            double_interval=tuple(m.get("double_interval", (0.08, 0.18))),
        )

    # ---------- 外部控制 ----------

    def pause(self) -> None:
        self._paused = True
        self.status.set(state="paused", message="已暂停")

    def resume(self) -> None:
        self._paused = False
        self.status.set(state="running", message="运行中")

    def stop(self) -> None:
        self._stop = True

    @property
    def paused(self) -> bool:
        return self._paused

    # ---------- 主循环 ----------

    def run(self) -> None:
        self.status.set(state="running", message="引擎启动")
        log.info("规则引擎启动，间隔=%.2fs，阈值=%.2f，代理=%s",
                 self.interval, self.threshold,
                 "在线" if self._agent_available() else "离线(用本地鼠标)")
        while not self._stop:
            if self.hotkey.pressed():
                log.info("检测到退出热键，正在停止…")
                self.status.set(state="stopped", message="已通过热键退出")
                break
            if self._paused:
                time.sleep(0.2)
                continue
            self._reload_if_changed()
            t0 = time.time()
            try:
                self.tick()
            except Exception as e:  # noqa
                log.error("tick 异常: %s", e)
            dt = time.time() - t0
            if dt < self.interval:
                time.sleep(self.interval - dt)
        self.status.set(state="stopped", message="已停止")
        log.info("规则引擎已停止。")

    def run_once(self) -> None:
        """执行一次：检测 + 匹配 + 动作，不进入循环。"""
        self._paused = False
        self._reload_if_changed()
        self.tick()

    def _reload_if_changed(self) -> None:
        try:
            mtime = self.rules_path.stat().st_mtime
        except OSError:
            return
        if mtime != self.ruleset.mtime:
            log.info("检测到规则文件变化，重新加载。")
            self.ruleset = load_ruleset(self.rules_path)
            self.lib.reload(self.ruleset.needed_templates())
            self.status.set(message="规则已更新")

    def tick(self) -> None:
        screen = self._grab()
        visible = self._detect(screen)
        now = time.time()
        rule = self.ruleset.find(visible, now)
        if rule is not None:
            self.status.set(state="running", current_rule=rule.id,
                            message="执行规则: " + rule.desc, visible=sorted(visible))
            log.info("命中规则 [%s] %s", rule.id, rule.desc)
            self._execute(rule)
            rule.last_run = time.time()
            self.status.bump("count_exec")
            return
        if visible:
            if self.ruleset.matches_condition(visible):
                # 认识这些元素，只是对应规则还在冷却 —— 等待即可
                self.status.set(state="running", current_rule="",
                                message="等待冷却…", visible=sorted(visible))
                return
            if self.ruleset.is_partial_match(visible):
                # 是某规则条件的子集：动作进行中（如派遣后按钮暂时消失）—— 等待
                self.status.set(state="running", current_rule="",
                                message="动作进行中…", visible=sorted(visible))
                return
            self._handle_unknown(screen, visible)
        else:
            self.status.set(state="running", current_rule="",
                            message="等待中（未发现已知元素）", visible=[])

    def _detect(self, screen: np.ndarray) -> Set[str]:
        visible: Set[str] = set()
        for name in list(self.lib.templates.keys()):
            pos, score = self.lib.match(screen, name)
            if pos is not None:
                visible.add(name)
        return visible

    def _execute(self, rule: Rule) -> None:
        for step in rule.action:
            if self._stop or self._paused:
                return
            if step.type == "click":
                pos, score = self.lib.match(self._grab(), str(step.target))
                if pos is None:
                    log.warning("动作目标当前不可见，跳过: %s", step.target)
                    continue
                self.status.set(message="点击 " + str(step.target))
                self._click_at(pos[0], pos[1])
            elif step.type == "click_at":
                x, y = step.target
                self._click_at(int(x), int(y))
            elif step.type == "repeat_click":
                self._repeat_click(step.target)
            elif step.type == "pause":
                msg = str(step.target) if step.target else "需要人工确认"
                log.warning("规则触发暂停: %s", msg)
                self._handle_unknown(self._grab(), self._detect(self._grab()))
                return
            elif step.type == "wait":
                time.sleep(float(step.target))

    def _repeat_click(self, cfg: dict) -> None:
        """按固定间隔连续点击，持续 duration 秒。
        cfg: {x, y, interval, duration}  或 {template, interval, duration}
        """
        interval = float(cfg.get("interval", 0.2))
        duration = float(cfg.get("duration", 3.0))
        x = cfg.get("x")
        y = cfg.get("y")
        if x is None and cfg.get("template"):
            pos, _ = self.lib.match(self._grab(), str(cfg["template"]))
            if pos is None:
                log.warning("repeat_click 目标不可见: %s", cfg.get("template"))
                return
            x, y = pos
        if x is None or y is None:
            log.warning("repeat_click 缺少坐标")
            return
        log.info("连续点击 (%d,%d)，间隔 %.3fs，持续 %.1fs", int(x), int(y), interval, duration)
        t0 = time.time()
        while time.time() - t0 < duration:
            if self._stop or self._paused:
                return
            self._click_at(int(x), int(y))
            time.sleep(interval)

    def _handle_unknown(self, screen: np.ndarray, visible: Set[str]) -> None:
        self._paused = True
        UNKNOWN_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        fp = UNKNOWN_DIR / ("unknown_" + ts + ".png")
        imwrite_unicode(str(fp), screen)
        msg = "遇到未知情况，已暂停。可见: " + ", ".join(sorted(visible))
        log.warning(msg)
        log.warning("截图已保存: %s", fp)
        self.status.set(state="unknown", message=msg, current_rule="",
                        visible=sorted(visible), last_unknown=str(fp))
        self.status.bump("count_unknown")
