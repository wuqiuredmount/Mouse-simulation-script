"""管理员常驻代理：一次提权启动，之后通过命令文件接收并执行指令。

只需启动一次（提权）。之后客户端写 data/agent/command.json，
本进程（管理员）读取执行，结果写入 data/agent/result.json。

支持的命令 action：
  click          {x, y, count?}            点击坐标
  click_template {name, window?}           截图匹配模板后点击其中心
  capture        {path}                    截图保存
  foreground     {window}                  把窗口置前
  ping                                     心跳测试
  quit                                     退出代理
"""

import ctypes
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.winenv import ensure_dpi_aware, is_admin

ensure_dpi_aware()

import cv2
import mss
import numpy as np

from src.action.mouse_driver import create_driver
from src.utils.imaging import imread_unicode, imwrite_unicode

AGENT_DIR = ROOT / "data" / "agent"
AGENT_DIR.mkdir(parents=True, exist_ok=True)
CMD_FILE = AGENT_DIR / "command.json"
RESULT_FILE = AGENT_DIR / "result.json"
STATUS_FILE = AGENT_DIR / "status.txt"
ASSETS = ROOT / "data" / "assets"

user32 = ctypes.windll.user32

kernel32 = ctypes.windll.kernel32

def find_hwnd(keyword: str):
    """查找标题含关键字的可见顶层窗口。"""
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


def _force_fg(hwnd):
    """AttachThreadInput + ALT 击键 + SetForegroundWindow（需管理员）。"""
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    if user32.GetForegroundWindow() == hwnd:
        return True
    VK_MENU, KEYUP = 0x12, 0x0002
    fg = user32.GetForegroundWindow()
    cur = kernel32.GetCurrentThreadId()
    ft = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    tt = user32.GetWindowThreadProcessId(hwnd, None)
    attached = []
    for t in set([ft, tt]):
        if t and t != cur:
            if user32.AttachThreadInput(cur, t, True):
                attached.append(t)
    try:
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYUP, 0)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        for t in attached:
            user32.AttachThreadInput(cur, t, False)
    return user32.GetForegroundWindow() == hwnd


def force_foreground(keyword: str) -> str:
    wins = find_hwnd(keyword)
    if not wins:
        return 
    hwnd, title = wins[0]
    _force_fg(hwnd)
    time.sleep(0.3)
    return title


# ---------- 截图 / 匹配 ----------

def grab_full() -> np.ndarray:
    sct = mss.mss()
    raw = np.array(sct.grab(sct.monitors[1]))
    return raw[:, :, :3].copy()


def match_template(screen: np.ndarray, name: str, threshold: float = 0.85):
    tpl = imread_unicode(str(ASSETS / (name + ".png")))
    if tpl is None:
        return None, 0.0
    res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < threshold:
        return None, float(max_val)
    th, tw = tpl.shape[:2]
    return (max_loc[0] + tw // 2, max_loc[1] + th // 2), float(max_val)


# ---------- 命令执行 ----------

# ---------- 现场保存/恢复 ----------

class _CPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _get_foreground():
    return user32.GetForegroundWindow()


def _get_cursor():
    p = _CPoint()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def _set_cursor(x, y):
    user32.SetCursorPos(int(x), int(y))


def _restore_foreground(hwnd):
    try:
        _force_fg(hwnd)
    except Exception:
        pass


def _do_clicks(x, y, count, restore, prev_fg, prev_cursor):
    """执行点击，然后恢复现场。"""
    d = create_driver("pydirectinput", False)
    d.move_to(int(x), int(y))
    time.sleep(0.15)
    for i in range(count):
        d.mouse_down(); time.sleep(0.06); d.mouse_up()
        if i < count - 1:
            time.sleep(0.10)
    if restore:
        cur_fg = _get_foreground()
        if prev_fg and cur_fg != prev_fg:
            _restore_foreground(prev_fg)
        # 光标恢复：多次尝试，防止被后续事件覆盖
        for _ in range(3):
            _set_cursor(prev_cursor[0], prev_cursor[1])
            time.sleep(0.02)


def do_click(args: dict) -> dict:
    x, y = int(args["x"]), int(args["y"])
    count = int(args.get("count", 2))
    restore = bool(args.get("restore", True))
    prev_fg = _get_foreground()
    prev_cursor = _get_cursor()
    if args.get("window"):
        force_foreground(args["window"])
    _do_clicks(x, y, count, restore, prev_fg, prev_cursor)
    return {"clicked": [x, y, count], "restored": restore}


def do_click_template(args: dict) -> dict:
    name = args["name"]
    restore = bool(args.get("restore", True))
    prev_fg = _get_foreground()
    prev_cursor = _get_cursor()
    if args.get("window"):
        force_foreground(args["window"])
    screen = grab_full()
    pos, score = match_template(screen, name, float(args.get("threshold", 0.85)))
    if pos is None:
        if restore:
            _restore_foreground(prev_fg)
            _set_cursor(*prev_cursor)
        return {"matched": False, "score": score}
    x, y = pos
    count = int(args.get("count", 2))
    _do_clicks(x, y, count, restore, prev_fg, prev_cursor)
    return {"matched": True, "score": score, "clicked": [x, y]}



def do_repeat_click(args: dict) -> dict:
    """在目标位置高速连续点击 count 次，用于限时小游戏（如探寻宝物）。"""
    x, y = int(args["x"]), int(args["y"])
    count = int(args.get("count", 10))
    interval = float(args.get("interval", 0.3))
    restore = bool(args.get("restore", True))
    prev_fg = _get_foreground()
    prev_cursor = _get_cursor()
    if args.get("window"):
        force_foreground(args["window"])
    d = create_driver("pydirectinput", False)
    d.move_to(x, y)
    time.sleep(0.08)
    for i in range(count):
        d.mouse_down(); time.sleep(0.03); d.mouse_up()
        if i < count - 1:
            time.sleep(interval)
    if restore:
        cur_fg = _get_foreground()
        if prev_fg and cur_fg != prev_fg:
            _restore_foreground(prev_fg)
        _set_cursor(prev_cursor[0], prev_cursor[1])
    return {"repeat_clicked": [x, y, count]}


def do_capture(args: dict) -> dict:
    img = grab_full()
    out = args.get("path", "data/monitor/agent_capture.png")
    p = ROOT / out if not Path(out).is_absolute() else Path(out)
    imwrite_unicode(str(p), img)
    return {"saved": str(p), "size": [img.shape[1], img.shape[0]]}


def do_foreground(args: dict) -> dict:
    title = force_foreground(args["window"])
    return {"focused": title}


HANDLERS = {
    "click": do_click,
    "click_template": do_click_template,
    "capture": do_capture,
    "repeat_click": do_repeat_click,
    "foreground": do_foreground,
    "ping": lambda a: {"pong": True},
}


def write_result(payload: dict) -> None:
    tmp = RESULT_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(RESULT_FILE)


def main() -> None:
    if not is_admin():
        print("[ERROR] 代理必须以管理员身份运行。请用 agent_start.bat 启动。")
        return
    STATUS_FILE.write_text("running pid=%d time=%s" % (__import__("os").getpid(), time.strftime("%H:%M:%S")), encoding="utf-8")
    print("管理员代理已启动，等待指令…  (处理 %s)" % CMD_FILE)

    while True:
        if not CMD_FILE.exists():
            time.sleep(0.2)
            continue
        try:
            cmd = json.loads(CMD_FILE.read_text(encoding="utf-8"))
        except Exception:
            time.sleep(0.2)
            continue
        CMD_FILE.unlink(missing_ok=True)

        cid = cmd.get("id", "")
        action = cmd.get("action", "")

        if action == "quit":
            write_result({"id": cid, "ok": True, "data": {"bye": True}})
            print("收到退出指令，代理结束。")
            break

        handler = HANDLERS.get(action)
        if handler is None:
            write_result({"id": cid, "ok": False, "error": "unknown action: " + action})
            continue

        try:
            data = handler(cmd.get("args", {}) or {})
            write_result({"id": cid, "ok": True, "data": data})
        except Exception as e:  # noqa
            write_result({"id": cid, "ok": False, "error": str(e)})

    STATUS_FILE.write_text("stopped time=%s" % time.strftime("%H:%M:%S"), encoding="utf-8")


if __name__ == "__main__":
    main()
