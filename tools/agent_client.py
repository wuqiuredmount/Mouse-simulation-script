"""代理客户端：非管理员进程通过它给管理员代理下指令。

用法（命令行）：
    python tools/agent_client.py ping
    python tools/agent_client.py click 1230 895 --window 三国
    python tools/agent_client.py click_template sr_help --window 三国
    python tools/agent_client.py capture data/monitor/foo.png

用法（作为库）：
    from tools.agent_client import send
    r = send("click", {"x": 1230, "y": 895, "window": "三国"})
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AGENT_DIR = ROOT / "data" / "agent"
AGENT_DIR.mkdir(parents=True, exist_ok=True)
CMD_FILE = AGENT_DIR / "command.json"
RESULT_FILE = AGENT_DIR / "result.json"
STATUS_FILE = AGENT_DIR / "status.txt"


class AgentUnavailable(Exception):
    pass


def agent_alive() -> bool:
    if not STATUS_FILE.exists():
        return False
    return STATUS_FILE.read_text(encoding="utf-8").startswith("running")


def send(action: str, args: dict | None = None, timeout: float = 15.0) -> dict:
    """发送指令并等待结果。代理未运行时抛 AgentUnavailable。"""
    if not agent_alive():
        raise AgentUnavailable("管理员代理未运行，请先双击 agent_start.bat")

    cid = uuid.uuid4().hex
    payload = {"id": cid, "action": action, "args": args or {}}

    # 等待上一个结果被消费
    RESULT_FILE.unlink(missing_ok=True)
    tmp = CMD_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CMD_FILE)

    t0 = time.time()
    while time.time() - t0 < timeout:
        if RESULT_FILE.exists():
            try:
                res = json.loads(RESULT_FILE.read_text(encoding="utf-8"))
            except Exception:
                time.sleep(0.05)
                continue
            if res.get("id") == cid:
                RESULT_FILE.unlink(missing_ok=True)
                if not res.get("ok"):
                    raise RuntimeError(res.get("error", "unknown error"))
                return res.get("data", {})
        time.sleep(0.05)
    raise TimeoutError("代理响应超时")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--window", default=None)
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.85)
    a = ap.parse_args()

    if not agent_alive():
        print("[ERROR] 管理员代理未运行。请先双击桌面/目录下的 agent_start.bat")
        return

    if a.action == "ping":
        print(send("ping"))
    elif a.action == "click":
        x, y = int(a.rest[0]), int(a.rest[1])
        print(send("click", {"x": x, "y": y, "count": a.count, "window": a.window}))
    elif a.action == "click_template":
        print(send("click_template", {"name": a.rest[0], "window": a.window,
                                       "count": a.count, "threshold": a.threshold}))
    elif a.action == "capture":
        print(send("capture", {"path": a.rest[0]}))
    elif a.action == "foreground":
        print(send("foreground", {"window": a.rest[0] if a.rest else a.window}))
    elif a.action == "quit":
        print(send("quit"))
    else:
        print("未知命令:", a.action)


if __name__ == "__main__":
    main()
