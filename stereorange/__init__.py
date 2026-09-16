"""StereoRange 的双目视差与深度计算基础模块。"""

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
]
