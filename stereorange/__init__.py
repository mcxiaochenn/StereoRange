"""StereoRange 的双目视差与深度计算基础模块。"""

__author__ = "陆逸尘、周璟雯、胡乐毅"
__credits__ = "平湖技师学院 · 指导教师 张梁"
PROJECT_CREDIT = (
    "平湖技师学院 · 陆逸尘（辰渊尘 ChenDusk · @mcxiaochenn）· 周璟雯 · 胡乐毅 · 指导教师 张梁"
)

from stereorange.core import (
    DemoPair,
    compute_disparity,
    disparity_to_depth,
    generate_demo_pair,
    sample_median,
)

__all__ = [
    "DemoPair",
    "compute_disparity",
    "disparity_to_depth",
    "generate_demo_pair",
    "sample_median",
    "PROJECT_CREDIT",
]
