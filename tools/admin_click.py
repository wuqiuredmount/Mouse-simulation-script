"""管理员点击：执行点击并把结果写入文件（供非管理员父进程读取）。"""

import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.winenv import ensure_dpi_aware, is_admin

ensure_dpi_aware()

from src.action.mouse_driver import create_driver

user32 = ctypes.windll.user32
RESULT = ROOT / "data" / "monitor" / "click_result.txt"


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
    x = int(sys.argv[1])
    y = int(sys.argv[2])
    keyword = sys.argv[3] if len(sys.argv) > 3 else "三国"

    lines = ["admin: %s" % is_admin(), "fg_before: %s" % foreground_title()]

    wins = find_hwnd(keyword)
    if wins:
        hwnd, title = wins[0]
        user32.ShowWindow(hwnd, 9)
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        time.sleep(0.6)
        lines.append("focused: %s" % title)

    lines.append("fg_after_focus: %s" % foreground_title())
    d = create_driver("pydirectinput", False)
    d.move_to(x, y)
    time.sleep(0.4)
    for i in range(2):
        d.mouse_down(); time.sleep(0.10); d.mouse_up()
        if i == 0:
            time.sleep(0.12)
    lines.append("clicked: (%d,%d)" % (x, y))
    lines.append("fg_after: %s" % foreground_title())

    RESULT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
