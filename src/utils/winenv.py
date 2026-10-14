"""Windows 环境设置：DPI 感知 + 管理员权限检测。"""

import ctypes
import sys

_DPI_SET = False


def ensure_dpi_aware() -> None:
    """设置进程 DPI 感知，保证“截图坐标”与“鼠标坐标”一致。

    不设置的话，在缩放不是 100% 的显示器上，mss 抓到的是物理像素，
    而鼠标 API 用的是逻辑像素，点击会偏位。
    """
    global _DPI_SET
    if _DPI_SET or sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    _DPI_SET = True


def is_admin() -> bool:
    """当前进程是否以管理员身份运行。"""
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False
