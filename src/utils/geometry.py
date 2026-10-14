"""几何与曲线工具：用于生成拟人鼠标轨迹。"""

import math
import random
from typing import List, Tuple

Point = Tuple[float, float]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def cubic_bezier(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
    """三次贝塞尔曲线上参数 t (0..1) 处的点。"""
    mt = 1 - t
    x = (mt ** 3) * p0[0] + 3 * (mt ** 2) * t * p1[0] + 3 * mt * (t ** 2) * p2[0] + (t ** 3) * p3[0]
    y = (mt ** 3) * p0[1] + 3 * (mt ** 2) * t * p1[1] + 3 * mt * (t ** 2) * p2[1] + (t ** 3) * p3[1]
    return x, y


def random_control_points(start: Point, end: Point, spread: float = 0.3) -> Tuple[Point, Point]:
    """围绕起终点连线生成两个随机控制点，使轨迹带自然弧度。"""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = max(math.hypot(dx, dy), 1e-6)
    # 单位法向量
    nx, ny = -dy / length, dx / length

    def offset(base: Point, along_frac: float, perp_frac: float) -> Point:
        return (
            base[0] + dx * along_frac + nx * length * perp_frac,
            base[1] + dy * along_frac + ny * length * perp_frac,
        )

    p1 = offset(start, random.uniform(0.1, 0.35), random.uniform(-spread, spread))
    p2 = offset(end, -random.uniform(0.1, 0.35), random.uniform(-spread, spread))
    return p1, p2


def build_path(start: Point, end: Point, steps: int, spread: float = 0.3) -> List[Point]:
    """生成从 start 到 end 的贝塞尔轨迹点列表。"""
    p1, p2 = random_control_points(start, end, spread)
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        pts.append(cubic_bezier(start, p1, p2, end, t))
    return pts
