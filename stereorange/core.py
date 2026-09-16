"""双目演示数据、视差计算与深度换算。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from stereorange.config import DEFAULT_BASELINE_M, DEFAULT_FOCAL_PX

Image = NDArray[np.uint8]
FloatImage = NDArray[np.float32]


@dataclass(frozen=True)
class DemoPair:
    """一组带虚拟相机参数的确定性双目演示图。"""

    left: Image
    right: Image
    focal_px: float
    baseline_m: float


def generate_demo_pair() -> DemoPair:
    """生成无需相机即可运行的已校正模拟双目图像。"""

    height, width = 360, 640
    rng = np.random.default_rng(20260916)
    gray = rng.integers(0, 256, (height, width), dtype=np.uint8)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    left = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    background_disparity = 8
    right = cv2.copyMakeBorder(
        left[:, background_disparity:],
        0,
        0,
        0,
        background_disparity,
        cv2.BORDER_REPLICATE,
    )

    layers = (
        (80, 70, 210, 220, 16, (30, 70, 20)),
        (365, 95, 190, 185, 28, (70, 20, 35)),
    )
    for x, y, layer_width, layer_height, disparity, tint in layers:
        texture = rng.integers(
            0,
            186,
            (layer_height, layer_width, 3),
            dtype=np.uint8,
        )
        texture = np.clip(
            texture.astype(np.int16) + np.asarray(tint, dtype=np.int16),
            0,
            255,
        ).astype(np.uint8)
        left[y : y + layer_height, x : x + layer_width] = texture
        right_x = x - disparity
        right[y : y + layer_height, right_x : right_x + layer_width] = texture

    return DemoPair(
        left=left,
        right=right,
        focal_px=DEFAULT_FOCAL_PX,
        baseline_m=DEFAULT_BASELINE_M,
    )


def compute_disparity(left: Image, right: Image) -> FloatImage:
    """使用 StereoSGBM 计算以像素为单位的浮点视差图。"""

    if left.shape != right.shape:
        raise ValueError("左右图像尺寸必须一致。")
    if left.ndim not in (2, 3):
        raise ValueError("图像必须是灰度图或 BGR 彩色图。")

    height, width = left.shape[:2]
    if height < 32 or width < 64:
        raise ValueError("图像尺寸过小，宽度至少 64 像素且高度至少 32 像素。")

    left_gray = _to_gray(left)
    right_gray = _to_gray(right)
    num_disparities = min(128, max(16, ((width // 4) // 16) * 16))
    block_size = 5
    matcher = cv2.StereoSGBM_create(
        minDisparity=0,
        numDisparities=num_disparities,
        blockSize=block_size,
        P1=8 * block_size**2,
        P2=32 * block_size**2,
        disp12MaxDiff=1,
        uniquenessRatio=10,
        speckleWindowSize=100,
        speckleRange=2,
        preFilterCap=31,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
    )
    return matcher.compute(left_gray, right_gray).astype(np.float32) / 16.0


def disparity_to_depth(
    disparity: FloatImage,
    focal_px: float,
    baseline_m: float,
) -> FloatImage:
    """按 Z=fB/d 将有效视差换算为以米为单位的深度。"""

    if focal_px <= 0 or baseline_m <= 0:
        raise ValueError("焦距和基线必须为正数。")

    depth = np.full(disparity.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(disparity) & (disparity > 0)
    depth[valid] = focal_px * baseline_m / disparity[valid]
    return depth


def sample_median(
    values: FloatImage,
    x: int,
    y: int,
    window_size: int = 7,
) -> float | None:
    """返回点击位置附近有效正数的中位数。"""

    if window_size <= 0 or window_size % 2 == 0:
        raise ValueError("采样窗口必须为正奇数。")
    if not (0 <= x < values.shape[1] and 0 <= y < values.shape[0]):
        return None

    radius = window_size // 2
    region = values[
        max(0, y - radius) : min(values.shape[0], y + radius + 1),
        max(0, x - radius) : min(values.shape[1], x + radius + 1),
    ]
    valid_values = region[np.isfinite(region) & (region > 0)]
    if valid_values.size == 0:
        return None
    return float(np.median(valid_values))


def _to_gray(image: Image) -> NDArray[np.uint8]:
    if image.ndim == 2:
        return image
    if image.shape[2] != 3:
        raise ValueError("彩色图像必须使用 BGR 三通道格式。")
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
