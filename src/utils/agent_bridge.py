"""管理员代理桥接：让普通权限的引擎通过代理执行点击等操作。

代理（管理员）由 tools/agent_daemon.py 提供，通过文件通信：
  data/agent/command.json   引擎写指令
  data/agent/result.json    代理写结果
  data/agent/status.txt     代理状态（running/stopped）
"""

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_DIR = ROOT / "data" / "agent"
CMD_FILE = AGENT_DIR / "command.json"
RESULT_FILE = AGENT_DIR / "result.json"
STATUS_FILE = AGENT_DIR / "status.txt"


class AgentUnavailable(Exception):
    pass


def agent_alive() -> bool:
    """代理是否在线。"""
    if not STATUS_FILE.exists():
        return False
    try:
        return STATUS_FILE.read_text(encoding="utf-8").startswith("running")
    except OSError:
        return False


def send(action: str, args: dict | None = None, timeout: float = 15.0) -> dict:
    """发送指令给代理并等待结果。代理不在线时抛 AgentUnavailable。"""
    if not agent_alive():
        raise AgentUnavailable("管理员代理未运行")

    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    cid = uuid.uuid4().hex
    payload = {"id": cid, "action": action, "args": args or {}}

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
