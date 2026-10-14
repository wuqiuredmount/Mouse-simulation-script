"""PostMessage 后台点击测试：不移动真实鼠标、不激活窗口，直接投递点击消息。

用法：
    python tools/postmessage_click.py --window 三国 --enum
        列出窗口树，看看游戏的实际子窗口
    python tools/postmessage_click.py --window 三国 --x 1500 --y 1120
        向该屏幕坐标对应的窗口投递点击
"""

import argparse
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.winenv import ensure_dpi_aware

ensure_dpi_aware()

user32 = ctypes.windll.user32

# 消息常量
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEMOVE = 0x0200
MK_LBUTTON = 0x0001


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def list_windows(keyword: str, depth: int = 0, parent=0):
    """递归枚举窗口树。"""
    results = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            title = buf.value

        # 取类名
        cbuf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cbuf, 256)
        cls = cbuf.value

        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top

        text = "  " * depth + "hwnd=%s cls=%s title=%r rect=(%d,%d,%dx%d)" % (
            hwnd, cls, title[:30], r.left, r.top, w, h)
        print(text)

        # 递归子窗口
        child = 0

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def ccb(ch, lp):
            list_windows(keyword, depth + 1, hwnd)
            return True

        user32.EnumChildWindows(hwnd, ccb, 0)
        return True

    user32.EnumWindows(cb, 0)
    return results


def find_game_window(keyword: str):
    """找标题含关键字的顶层窗口。"""
    found = []

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
            found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    return found


def send_click(hwnd, screen_x, screen_y, count=2):
    """向窗口投递点击消息。坐标为屏幕绝对坐标，内部转客户区坐标。"""
    pt = POINT(screen_x, screen_y)
    user32.ScreenToClient(hwnd, ctypes.byref(pt))
    cx, cy = pt.x, pt.y
    lparam = (cy << 16) | (cx & 0xFFFF)
    print("窗口 %s 客户区坐标 (%d, %d)" % (hwnd, cx, cy))

    for i in range(count):
        # 先移动，再按下、抬起（有些游戏要求 move 先行）
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.03)
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.06)
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
        if i < count - 1:
            time.sleep(0.1)
    print("已投递 %d 次后台点击" % count)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="三国")
    ap.add_argument("--enum", action="store_true", help="列出窗口树")
    ap.add_argument("--x", type=int)
    ap.add_argument("--y", type=int)
    ap.add_argument("--count", type=int, default=2)
    a = ap.parse_args()

    print("=== 查找窗口 ===")
    wins = find_game_window(a.window)
    for hwnd, title in wins:
        print("  顶层窗口: hwnd=%s title=%r" % (hwnd, title))
    if not wins:
        print("没找到窗口")
        return

    if a.enum:
        print("\n=== 窗口树 ===")
        list_windows(a.window)
        return

    if a.x is None or a.y is None:
        print("请用 --x --y 指定坐标，或用 --enum 查看窗口")
        return

    # 找离目标点最近的可见顶层窗口（游戏整个可能是一个大窗口）
    hwnd = wins[0][0]
    print("\n=== 投递点击 ===")
    send_click(hwnd, a.x, a.y, a.count)


if __name__ == "__main__":
    main()
