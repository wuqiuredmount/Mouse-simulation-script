"""鼠标驱动抽象：把具体后端（pyautogui / pydirectinput）封装统一接口。"""

from src.utils.logger import get_logger

log = get_logger("quiz.action.driver")


class BaseDriver:
    def position(self): raise NotImplementedError
    def move_to(self, x: int, y: int): raise NotImplementedError
    def mouse_down(self): raise NotImplementedError
    def mouse_up(self): raise NotImplementedError
    def set_failsafe(self, enabled: bool): pass


class PyAutoGUIDriver(BaseDriver):
    def __init__(self, failsafe: bool = True):
        import pyautogui
        self._pg = pyautogui
        self._pg.FAILSAFE = failsafe
        self._pg.PAUSE = 0

    def position(self):
        return self._pg.position()

    def move_to(self, x: int, y: int):
        self._pg.moveTo(x, y, duration=0)

    def mouse_down(self):
        self._pg.mouseDown()

    def mouse_up(self):
        self._pg.mouseUp()

    def set_failsafe(self, enabled: bool):
        self._pg.FAILSAFE = enabled


class PyDirectInputDriver(BaseDriver):
    """Windows 下对游戏更友好的输入后端。"""

    def __init__(self, failsafe: bool = True):
        import pydirectinput
        self._pdi = pydirectinput
        self._pdi.PAUSE = 0.02
        self._pdi.FAILSAFE = failsafe

    def position(self):
        return self._pdi.position()

    def move_to(self, x: int, y: int):
        self._pdi.moveTo(x, y)

    def mouse_down(self):
        self._pdi.mouseDown()

    def mouse_up(self):
        self._pdi.mouseUp()


def create_driver(name: str, failsafe: bool = True) -> BaseDriver:
    name = name.lower()
    if name == "pydirectinput":
        try:
            return PyDirectInputDriver(failsafe=failsafe)
        except Exception as e:  # noqa
            log.error("pydirectinput 初始化失败(%s)，回退 pyautogui。", e)
    return PyAutoGUIDriver(failsafe=failsafe)
