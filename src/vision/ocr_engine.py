"""OCR 引擎抽象：把图像转成文字。后端可插拔。"""

import os
from typing import List

# 必须在导入 paddle 之前设置：禁用 oneDNN，规避 paddle 3.x 的
# "ConvertPirAttribute2RuntimeAttribute not support" 报错。
os.environ.setdefault("FLAGS_use_mkldnn", "0")

import numpy as np

from src.utils.logger import get_logger

log = get_logger("quiz.vision.ocr")


class BaseOCR:
    def read_text(self, image: np.ndarray) -> str:
        raise NotImplementedError

    def read_lines(self, image: np.ndarray) -> List[str]:
        """返回按行切分的文字，默认基于 read_text 实现。"""
        return [ln.strip() for ln in self.read_text(image).splitlines() if ln.strip()]


class StubOCR(BaseOCR):
    """占位后端：直接返回空串。用于跑通架构 / 单元测试。"""

    def read_text(self, image: np.ndarray) -> str:
        return ""


class TesseractOCR(BaseOCR):
    """基于 pytesseract 的本地 OCR。需安装 tesseract 引擎。"""

    def __init__(self, lang: str = "chi_sim+eng"):
        import pytesseract  # noqa
        import cv2           # noqa
        self._tess = pytesseract
        self._cv2 = cv2
        self.lang = lang

    def read_text(self, image: np.ndarray) -> str:
        gray = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2GRAY)
        # 二值化，提升对比度
        _, th = self._cv2.threshold(gray, 0, 255,
                                    self._cv2.THRESH_BINARY + self._cv2.THRESH_OTSU)
        return self._tess.image_to_string(th, lang=self.lang).strip()


class PaddleOCRBackend(BaseOCR):
    """基于 PaddleOCR 的中文 OCR，兼容 2.x 与 3.x API。"""

    def __init__(self, lang: str = "ch"):
        from paddleocr import PaddleOCR  # noqa
        self._major = self._detect_major()
        kwargs = dict(lang=lang)
        if self._major >= 3:
            # 3.x：关闭文档方向/矫正等附加模块，减少模型下载与耗时
            # 并显式关闭 mkldnn（配合 FLAGS_use_mkldnn=0）
            kwargs.update(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
            )
        else:
            kwargs.update(use_angle_cls=True, show_log=False)
        try:
            self._ocr = PaddleOCR(**kwargs)
        except TypeError:
            # 参数不被接受时退回最简构造
            self._ocr = PaddleOCR(lang=lang)

    @staticmethod
    def _detect_major() -> int:
        try:
            import paddleocr
            ver = getattr(paddleocr, "__version__", "2.0")
            return int(str(ver).split(".")[0])
        except Exception:
            return 2

    def read_text(self, image: np.ndarray) -> str:
        if self._major >= 3:
            return self._read_v3(image)
        return self._read_v2(image)

    def _read_v3(self, image: np.ndarray) -> str:
        results = self._ocr.predict(image)
        lines = []
        for res in results or []:
            texts = None
            if isinstance(res, dict):
                texts = res.get("rec_texts")
            else:
                data = getattr(res, "json", None) or getattr(res, "res", None)
                if isinstance(data, dict):
                    texts = data.get("rec_texts")
            if texts:
                lines.extend(texts)
        return "\n".join(lines)

    def _read_v2(self, image: np.ndarray) -> str:
        result = self._ocr.ocr(image, cls=True)
        lines = []
        for block in result or []:
            for item in block or []:
                lines.append(item[1][0])
        return "\n".join(lines)


def create_ocr(backend: str, lang: str) -> BaseOCR:
    backend = backend.lower()
    if backend == "stub":
        log.warning("使用 StubOCR：不会识别任何文字。")
        return StubOCR()
    if backend == "tesseract":
        try:
            return TesseractOCR(lang=lang)
        except Exception as e:  # noqa
            log.error("Tesseract 初始化失败(%s)，回退到 StubOCR。", e)
            return StubOCR()
    if backend == "paddle":
        try:
            return PaddleOCRBackend(lang="ch")
        except Exception as e:  # noqa
            log.error("PaddleOCR 初始化失败(%s)，回退到 StubOCR。", e)
            return StubOCR()
    raise ValueError(f"未知 OCR 后端: {backend}")
