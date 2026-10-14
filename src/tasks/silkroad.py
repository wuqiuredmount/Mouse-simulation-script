"""丝绸之路任务：根据配置构建按钮点击器。"""

from pathlib import Path

import yaml

from src.action.human_mouse import HumanMouse
from src.capture.screen_capture import ScreenCapture
from src.tasks.template_clicker import Button, TemplateClicker
from src.utils.logger import get_logger

log = get_logger("quiz.tasks.silkroad")

ROOT = Path(__file__).resolve().parent.parent.parent


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_buttons(cfg: dict) -> list:
    settings = cfg.get("settings", {})
    default_threshold = settings.get("global_threshold", 0.85)
    default_cooldown = settings.get("click_cooldown", 2.0)
    buttons = []
    for item in cfg.get("buttons", []):
        tpl = item["template"]
        tpl_path = str(ROOT / tpl) if not Path(tpl).is_absolute() else tpl
        buttons.append(Button(
            name=item["name"],
            template_path=tpl_path,
            threshold=item.get("threshold", default_threshold),
            cooldown=item.get("cooldown", default_cooldown),
            enabled=item.get("enabled", True),
        ))
    return buttons


def build_task(settings: dict, mouse: HumanMouse, capture: ScreenCapture) -> TemplateClicker:
    cfg = load_yaml(ROOT / "config" / "silkroad.yaml")
    buttons = build_buttons(cfg)
    interval = cfg.get("settings", {}).get("scan_interval", 0.6)
    return TemplateClicker(
        buttons=buttons,
        capture=capture,
        mouse=mouse,
        scan_interval=interval,
        dry_run=settings["safety"]["dry_run"],
    )
