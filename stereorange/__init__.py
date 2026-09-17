"""StereoRange 的双目视差与深度计算基础模块。"""

__author__ = "陆逸尘、辰渊尘"
__credits__ = "平湖技师学院 · GitHub @mcxiaochenn · ChenDusk"
PROJECT_CREDIT = (
    "平湖技师学院 · 陆逸尘 · 辰渊尘 · GitHub @mcxiaochenn · ChenDusk"
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
