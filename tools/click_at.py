"""可靠点击工具：强制把游戏窗口置前，再点击指定坐标。

用法：
    python tools/click_at.py 1230 895
    python tools/click_at.py 1230 895 --window 三国

关键：Flash 游戏需要窗口处于前台才接收点击，这里用 ctypes 强制置前。
"""

import argparse
import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.winenv import ensure_dpi_aware

ensure_dpi_aware()

from src.action.mouse_driver import create_driver

user32 = ctypes.windll.user32


def find_hwnd(keyword: str):
    """枚举顶层窗口，返回标题含关键字的 hwnd。"""
    result = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if keyword in title:
            result.append((hwnd, title))
        return True

    user32.EnumWindows(cb, 0)
    return result


def force_foreground(hwnd) -> None:
    """强制把窗口置前（含常见绕过限制的技巧）。"""
    SW_RESTORE = 9
    user32.ShowWindow(hwnd, SW_RESTORE)
    # 先发送一个 ALT 击键，绕过前台锁定限制
    VK_MENU = 0x12
    KEYEVENTF_KEYUP = 0x0002
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("x", type=int)
    parser.add_argument("y", type=int)
    parser.add_argument("--window", default="三国")
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--backend", default="pydirectinput")
    args = parser.parse_args()

    wins = find_hwnd(args.window)
    if not wins:
        print("[warn] 没找到窗口，直接点击。")
    else:
        hwnd, title = wins[0]
        print("置前窗口: %s (hwnd=%s)" % (title, hwnd))
        force_foreground(hwnd)

    driver = create_driver(args.backend, failsafe=False)
    driver.move_to(args.x, args.y)
    time.sleep(0.4)
    for i in range(args.count):
        driver.mouse_down()
        time.sleep(0.10)
        driver.mouse_up()
        if i < args.count - 1:
            time.sleep(0.12)
    print("已点击 (%d, %d) x%d" % (args.x, args.y, args.count))


if __name__ == "__main__":
    main()
