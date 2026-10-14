"""焦点诊断 + 点击：确认点击瞬间游戏是否在前台。

用法: python tools/focus_click.py 1230 895 --window 三国
"""

import argparse
import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.winenv import ensure_dpi_aware, is_admin

ensure_dpi_aware()

from src.action.mouse_driver import create_driver

user32 = ctypes.windll.user32


def foreground_title() -> str:
    hwnd = user32.GetForegroundWindow()
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def find_hwnd(keyword: str):
    result = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if keyword in buf.value:
            result.append((hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("x", type=int)
    ap.add_argument("y", type=int)
    ap.add_argument("--window", default="三国")
    ap.add_argument("--count", type=int, default=2)
    args = ap.parse_args()

    print("管理员权限:", is_admin())
    print("点击前前台窗口:", foreground_title())

    wins = find_hwnd(args.window)
    if wins:
        hwnd, title = wins[0]
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        r = user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        time.sleep(0.6)
        print("置前窗口:", title, "SetForegroundWindow 返回:", r)
    print("点击前(置前后)前台窗口:", foreground_title())

    d = create_driver("pydirectinput", False)
    d.move_to(args.x, args.y)
    time.sleep(0.4)
    for i in range(args.count):
        d.mouse_down(); time.sleep(0.10); d.mouse_up()
        if i < args.count - 1:
            time.sleep(0.12)
    print("已点击 (%d,%d) x%d" % (args.x, args.y, args.count))
    print("点击后前台窗口:", foreground_title())


if __name__ == "__main__":
    main()
