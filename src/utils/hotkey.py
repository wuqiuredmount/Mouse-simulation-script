"""全局热键监听（Windows）：即使窗口没焦点也能检测按键。

用 GetAsyncKeyState 轮询，采用“边沿触发”，避免长按重复触发。
"""

import ctypes

VK_CODES = {
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "esc": 0x1B,
}


class HotkeyWatcher:
    """检测某个键是否“刚被按下”。"""

    def __init__(self, key: str = "f1"):
        self.key = key.lower()
        self.vk = VK_CODES.get(self.key)
        self._was_down = False
        self._user32 = ctypes.windll.user32 if self.vk else None

    def pressed(self) -> bool:
        """刚按下的那一瞬间返回 True（长按只触发一次）。"""
        if self._user32 is None:
            return False
        state = self._user32.GetAsyncKeyState(self.vk)
        down = bool(state & 0x8000)
        edge = down and not self._was_down
        self._was_down = down
        return edge
