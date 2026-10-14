"""点击测试工具：判断鼠标点击为什么没生效。

用法：
    python tools/test_click.py --backend pydirectinput --now
    python tools/test_click.py --backend pyautogui --now
    python tools/test_click.py --backend pydirectinput --activate "三国"

建议【以管理员身份】运行本工具（游戏若是管理员，非管理员的点击会被系统拦截）。
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.winenv import ensure_dpi_aware, is_admin

ensure_dpi_aware()

from src.action.mouse_driver import create_driver


def try_activate(keyword: str) -> None:
    try:
        import pygetwindow as gw
    except Exception:
        print("[warn] 未安装 pygetwindow，跳过窗口激活。")
        return
    wins = [w for w in gw.getAllWindows() if keyword in (w.title or "")]
    if not wins:
        print("[warn] 没找到标题含 %r 的窗口。" % keyword)
        return
    w = wins[0]
    print("激活窗口: %s" % w.title)
    try:
        if w.isMinimized:
            w.restore()
        w.activate()
        time.sleep(0.4)
    except Exception as e:  # noqa
        print("[warn] 激活失败: %s" % e)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="pydirectinput",
                        choices=["pyautogui", "pydirectinput"])
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--now", action="store_true",
                        help="不移动鼠标，直接点击当前光标位置")
    parser.add_argument("--activate", default=None,
                        help="点击前先激活标题含该关键字的窗口，如 三国")
    parser.add_argument("--count", type=int, default=2, help="点击次数")
    args = parser.parse_args()

    print("管理员权限: %s" % ("是" if is_admin() else "否（可能导致点击无效）"))
    print("DPI 感知: 已设置")

    driver = create_driver(args.backend, failsafe=False)

    if args.activate:
        try_activate(args.activate)

    if args.now:
        x, y = driver.position()
        print("[%s] 立即点击当前位置 (%d, %d) x%d…" % (args.backend, x, y, args.count))
    else:
        print("[%s] %.0f 秒后点击，请把鼠标移到目标按钮上…" % (args.backend, args.delay))
        time.sleep(args.delay)
        x, y = driver.position()
        print("点击 (%d, %d) x%d…" % (x, y, args.count))

    for i in range(args.count):
        driver.mouse_down()
        time.sleep(0.10)
        driver.mouse_up()
        if i < args.count - 1:
            time.sleep(0.12)
    print("已发送点击。若游戏仍无反应，请以管理员身份再试一次。")


if __name__ == "__main__":
    main()
