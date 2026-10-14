"""线程安全的引擎状态容器：引擎线程写，GUI 主线程读。"""

import threading
from typing import Any, Dict, List


class EngineStatus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.state = "idle"          # idle | running | paused | unknown | stopped
        self.message = "未启动"
        self.current_rule = ""
        self.visible: List[str] = []
        self.count_exec = 0
        self.count_unknown = 0
        self.last_unknown = ""

    def set(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def bump(self, field: str, delta: int = 1) -> None:
        with self._lock:
            setattr(self, field, getattr(self, field) + delta)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self.state,
                "message": self.message,
                "current_rule": self.current_rule,
                "visible": list(self.visible),
                "count_exec": self.count_exec,
                "count_unknown": self.count_unknown,
                "last_unknown": self.last_unknown,
            }
