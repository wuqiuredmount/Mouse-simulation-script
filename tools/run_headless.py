"""无界面托管运行器：连续运行规则引擎，自动完成丝绸之路。

用法：
    python tools/run_headless.py

依赖：管理员代理必须在线（启动代理.bat）。
遇到未知情况会暂停并在终端提示，同时存图到 data/unknown/。
按 Ctrl+C 或 F1 停止。
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml

from src.core.status import EngineStatus
from src.learn.rule_engine import RuleEngine
from src.utils.logger import setup_logger, get_logger
from src.utils import agent_bridge


class ConsoleStatus(EngineStatus):
    """把状态变化打印到终端的极简实现。"""

    def set(self, **kwargs):
        super().set(**kwargs)
        if "state" in kwargs or "message" in kwargs:
            s = self.snapshot()
            print("[%s] %s | 规则=%s 可见=%s 执行=%d 未知=%d" % (
                s["state"], s["message"], s["current_rule"] or "-",
                ",".join(s["visible"]) or "-", s["count_exec"], s["count_unknown"]))


def main():
    settings = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    setup_logger(settings["app"]["log_level"])
    log = get_logger("quiz.headless")

    log.info("===== 丝绸之路自动托管启动 =====")
    log.info("管理员代理: %s", "在线" if agent_bridge.agent_alive() else "离线!! 请先启动代理")
    if not agent_bridge.agent_alive():
        log.error("代理未运行，无法点击。请先双击 启动代理.bat")
        return

    status = ConsoleStatus()
    engine = RuleEngine(settings, status, ROOT / "config" / "rules.yaml")
    try:
        engine.run()
    except KeyboardInterrupt:
        log.info("手动中断。")


if __name__ == "__main__":
    main()
