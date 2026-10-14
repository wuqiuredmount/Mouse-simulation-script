"""程序入口。

用法:
    python main.py                       # 默认运行丝绸之路点击器
    python main.py --task silkroad       # 丝绸之路：出现按钮就点
    python main.py --task quiz           # 答题模式
    python main.py --dry-run             # 只识别不点击
    python main.py --once                # 只跑一轮（调试）
"""

import sys

# 必须在其它导入/GUI 之前设置 DPI 感知
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from src.utils.winenv import ensure_dpi_aware, is_admin

ensure_dpi_aware()

import argparse
from pathlib import Path

import yaml

from src.action.human_mouse import HumanMouse
from src.action.mouse_driver import create_driver
from src.capture.screen_capture import ScreenCapture
from src.utils.logger import setup_logger

ROOT = Path(__file__).parent


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_mouse(settings: dict) -> HumanMouse:
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
    )


def build_capture(settings: dict) -> ScreenCapture:
    c = settings["capture"]
    return ScreenCapture(c["backend"], c["monitor"])


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 游戏鼠标助手")
    parser.add_argument("--task", default="learn",
                        choices=["learn", "silkroad", "quiz"])
    parser.add_argument("--settings", default="config/settings.yaml")
    parser.add_argument("--regions", default="config/regions.yaml")
    parser.add_argument("--bank", default="data/question_bank.json")
    parser.add_argument("--dry-run", action="store_true", help="只识别不点击")
    parser.add_argument("--once", action="store_true", help="只跑一轮后退出")
    args = parser.parse_args()

    settings = load_yaml(ROOT / args.settings)
    if args.dry_run:
        settings["safety"]["dry_run"] = True
    setup_logger(settings["app"]["log_level"])

    if not is_admin():
        print("[提示] 当前不是管理员权限。若游戏以管理员运行，点击可能无效。"
              "建议用桌面快捷方式（已设为管理员）启动。")

    capture = build_capture(settings)
    mouse = build_mouse(settings)

    if args.task == "learn":
        from src.ui.control_panel import launch
        launch(settings)
    elif args.task == "silkroad":
        from src.tasks.silkroad import build_task
        task = build_task(settings, mouse, capture)
        task.run(max_loops=1 if args.once else None)
    else:
        from src.core.engine import Engine
        regions = load_yaml(ROOT / args.regions)["regions"]
        engine = Engine(settings, regions, str(ROOT / args.bank))
        engine.run(max_loops=1 if args.once else None)


if __name__ == "__main__":
    main()
