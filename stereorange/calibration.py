"""双目相机标定、存储和立体校正。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from stereorange.core import Image

Points = NDArray[np.float32]


@dataclass(frozen=True)
class StereoCalibration:
    image_size: tuple[int, int]
    board_size: tuple[int, int]
    square_size_m: float
    left_camera_matrix: NDArray[np.float64]
    left_distortion: NDArray[np.float64]
    right_camera_matrix: NDArray[np.float64]
    right_distortion: NDArray[np.float64]
    rotation: NDArray[np.float64]
    translation: NDArray[np.float64]
    essential: NDArray[np.float64]
    fundamental: NDArray[np.float64]
    rectification_left: NDArray[np.float64]
    rectification_right: NDArray[np.float64]
    projection_left: NDArray[np.float64]
    projection_right: NDArray[np.float64]
    disparity_to_depth: NDArray[np.float64]
    rms_left: float
    rms_right: float
    rms_stereo: float
    valid_pairs: int

    @property
    def focal_px(self) -> float:
        return float((self.projection_left[0, 0] + self.projection_right[0, 0]) / 2)

    @property
    def baseline_m(self) -> float:
        return float(np.linalg.norm(self.translation))


class StereoRectifier:
    """复用已计算的映射表，对每帧左右图进行校正。"""

    def __init__(self, calibration: StereoCalibration) -> None:
        self.calibration = calibration
        size = calibration.image_size
        self._left_maps = cv2.initUndistortRectifyMap(
            calibration.left_camera_matrix,
            calibration.left_distortion,
            calibration.rectification_left,
            calibration.projection_left,
            size,
            cv2.CV_32FC1,
        )
        self._right_maps = cv2.initUndistortRectifyMap(
            calibration.right_camera_matrix,
            calibration.right_distortion,
            calibration.rectification_right,
            calibration.projection_right,
            size,
            cv2.CV_32FC1,
        )

    def rectify(self, left: Image, right: Image) -> tuple[Image, Image]:
        expected = self.calibration.image_size
        actual_left = (left.shape[1], left.shape[0])
        actual_right = (right.shape[1], right.shape[0])
        if actual_left != expected or actual_right != expected:
            raise ValueError(
                f"输入图像尺寸必须与标定分辨率 {expected[0]}×{expected[1]} 一致。"
            )
        return (
            cv2.remap(left, *self._left_maps, cv2.INTER_LINEAR),
            cv2.remap(right, *self._right_maps, cv2.INTER_LINEAR),
        )


def split_side_by_side(frame: Image) -> tuple[Image, Image]:
    """将单设备输出的横向双目帧等分为左右图。"""

    if frame.ndim not in (2, 3):
        raise ValueError("双目摄像头画面格式无效。")
    height, width = frame.shape[:2]
    if height < 32 or width < 128 or width % 2 != 0:
        raise ValueError("双目摄像头画面必须可横向等分，且每侧至少为 64×32 像素。")
    middle = width // 2
    return (
        np.ascontiguousarray(frame[:, :middle]),
        np.ascontiguousarray(frame[:, middle:]),
    )


def create_object_points(
    board_size: tuple[int, int], square_size_m: float
) -> Points:
    if square_size_m <= 0:
        raise ValueError("方格边长必须为正数。")
    columns, rows = board_size
    if columns < 2 or rows < 2:
        raise ValueError("棋盘格内角点的行列数必须至少为 2。")
    points = np.zeros((columns * rows, 3), dtype=np.float32)
    points[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2)
    points *= square_size_m
    return points


def detect_chessboard_pair(
    left: Image, right: Image, board_size: tuple[int, int]
) -> tuple[Points, Points] | None:
    if left.shape[:2] != right.shape[:2]:
        raise ValueError("左右标定图像尺寸必须一致。")
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
    left_gray = _to_gray(left)
    right_gray = _to_gray(right)
    found_left, left_corners = cv2.findChessboardCorners(left_gray, board_size, flags)
    found_right, right_corners = cv2.findChessboardCorners(right_gray, board_size, flags)
    if not found_left or not found_right:
        return None
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    left_corners = cv2.cornerSubPix(
        left_gray, left_corners, (11, 11), (-1, -1), criteria
    )
    right_corners = cv2.cornerSubPix(
        right_gray, right_corners, (11, 11), (-1, -1), criteria
    )
    return left_corners.astype(np.float32), right_corners.astype(np.float32)


def solve_stereo_calibration(
    object_points: list[Points],
    left_points: list[Points],
    right_points: list[Points],
    image_size: tuple[int, int],
    board_size: tuple[int, int],
    square_size_m: float,
) -> StereoCalibration:
    if len(object_points) < 10:
        raise ValueError("有效标定图像对至少需要 10 组，建议采集 25～30 组。")
    if not (len(object_points) == len(left_points) == len(right_points)):
        raise ValueError("左右角点与三维点组数不一致。")
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)
    rms_left, left_matrix, left_distortion, _, _ = cv2.calibrateCamera(
        object_points, left_points, image_size, None, None
    )
    rms_right, right_matrix, right_distortion, _, _ = cv2.calibrateCamera(
        object_points, right_points, image_size, None, None
    )
    (
        rms_stereo,
        left_matrix,
        left_distortion,
        right_matrix,
        right_distortion,
        rotation,
        translation,
        essential,
        fundamental,
    ) = cv2.stereoCalibrate(
        object_points,
        left_points,
        right_points,
        left_matrix,
        left_distortion,
        right_matrix,
        right_distortion,
        image_size,
        criteria=criteria,
        flags=cv2.CALIB_FIX_INTRINSIC,
    )
    rect_left, rect_right, proj_left, proj_right, q, _, _ = cv2.stereoRectify(
        left_matrix,
        left_distortion,
        right_matrix,
        right_distortion,
        image_size,
        rotation,
        translation,
        flags=cv2.CALIB_ZERO_DISPARITY,
        alpha=0,
    )
    return StereoCalibration(
        image_size=image_size,
        board_size=board_size,
        square_size_m=square_size_m,
        left_camera_matrix=left_matrix,
        left_distortion=left_distortion,
        right_camera_matrix=right_matrix,
        right_distortion=right_distortion,
        rotation=rotation,
        translation=translation,
        essential=essential,
        fundamental=fundamental,
        rectification_left=rect_left,
        rectification_right=rect_right,
        projection_left=proj_left,
        projection_right=proj_right,
        disparity_to_depth=q,
        rms_left=float(rms_left),
        rms_right=float(rms_right),
        rms_stereo=float(rms_stereo),
        valid_pairs=len(object_points),
    )


def save_calibration(path: Path, calibration: StereoCalibration) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        image_size=np.asarray(calibration.image_size, dtype=np.int32),
        board_size=np.asarray(calibration.board_size, dtype=np.int32),
        square_size_m=calibration.square_size_m,
        left_camera_matrix=calibration.left_camera_matrix,
        left_distortion=calibration.left_distortion,
        right_camera_matrix=calibration.right_camera_matrix,
        right_distortion=calibration.right_distortion,
        rotation=calibration.rotation,
        translation=calibration.translation,
        essential=calibration.essential,
        fundamental=calibration.fundamental,
        rectification_left=calibration.rectification_left,
        rectification_right=calibration.rectification_right,
        projection_left=calibration.projection_left,
        projection_right=calibration.projection_right,
        disparity_to_depth=calibration.disparity_to_depth,
        rms_left=calibration.rms_left,
        rms_right=calibration.rms_right,
        rms_stereo=calibration.rms_stereo,
        valid_pairs=calibration.valid_pairs,
    )


def load_calibration(path: Path) -> StereoCalibration:
    if not path.is_file():
        raise ValueError(f"标定文件不存在：{path}")
    try:
        with np.load(path, allow_pickle=False) as data:
            return StereoCalibration(
                image_size=tuple(int(v) for v in data["image_size"]),
                board_size=tuple(int(v) for v in data["board_size"]),
                square_size_m=float(data["square_size_m"]),
                left_camera_matrix=data["left_camera_matrix"],
                left_distortion=data["left_distortion"],
                right_camera_matrix=data["right_camera_matrix"],
                right_distortion=data["right_distortion"],
                rotation=data["rotation"],
                translation=data["translation"],
                essential=data["essential"],
                fundamental=data["fundamental"],
                rectification_left=data["rectification_left"],
                rectification_right=data["rectification_right"],
                projection_left=data["projection_left"],
                projection_right=data["projection_right"],
                disparity_to_depth=data["disparity_to_depth"],
                rms_left=float(data["rms_left"]),
                rms_right=float(data["rms_right"]),
                rms_stereo=float(data["rms_stereo"]),
                valid_pairs=int(data["valid_pairs"]),
            )
    except (OSError, KeyError, ValueError) as exc:
        raise ValueError(f"无法读取有效标定文件：{path}") from exc


def _to_gray(image: Image) -> NDArray[np.uint8]:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
