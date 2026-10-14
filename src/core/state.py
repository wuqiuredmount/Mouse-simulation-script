"""答题状态机状态定义。"""

from enum import Enum, auto


class State(Enum):
    IDLE = auto()          # 等待答题界面出现
    DETECTING = auto()     # 正在识别题干/选项
    DECIDING = auto()      # 正在匹配题库
    ACTING = auto()        # 正在点击
    COOLDOWN = auto()      # 点击后冷却，等待下一题
    STOPPED = auto()       # 已停止
