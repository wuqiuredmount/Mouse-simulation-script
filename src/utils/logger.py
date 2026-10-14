"""统一日志工具。"""

import logging
import sys


_CONFIGURED = False


def setup_logger(level: str = "INFO") -> logging.Logger:
    """配置并返回根 logger（只配置一次）。"""
    global _CONFIGURED
    logger = logging.getLogger("quiz")
    if _CONFIGURED:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger(name: str = "quiz") -> logging.Logger:
    return logging.getLogger(name)
