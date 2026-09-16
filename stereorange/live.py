"""实时双目画面采集与视差显示。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from stereorange.config import DEFAULT_FRAME_HEIGHT, DEFAULT_FRAME_WIDTH
from stereorange.core import (
    FloatImage,
    Image,
    compute_disparity,
    disparity_to_depth,
    sample_median,
)
from stereorange.presentation import colorize_values, save_results

PairReader = Callable[[], tuple[Image, Image]]


def run_live_stereo_camera(
    camera_index: int,
    focal_px: float,
    baseline_m: float,
    output_dir: Path | None,
) -> None:
    """读取单个横向拼接输出的双目摄像头，并拆分左右画面。"""

    capture = _open_camera(camera_index)
    try:

        def read_pair() -> tuple[Image, Image]:
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(f"无法从双目摄像头 {camera_index} 读取画面。")
            height, width = frame.shape[:2]
            if height < 32 or width < 128 or width % 2 != 0:
                raise ValueError(
                    "双目摄像头画面必须可横向等分，且每侧至少为 64×32 像素。"
                )
            middle = width // 2
            left = np.ascontiguousarray(frame[:, :middle])
            right = np.ascontiguousarray(frame[:, middle:])
            return left, right

        _run_live_loop(
            read_pair=read_pair,
            focal_px=focal_px,
            baseline_m=baseline_m,
            output_dir=output_dir,
            metadata_base={
                "input_mode": "stereo_camera",
                "camera_index": camera_index,
            },
        )
    finally:
        capture.release()
        cv2.destroyAllWindows()


def run_live_cameras(
    left_index: int,
    right_index: int,
    focal_px: float,
    baseline_m: float,
    output_dir: Path | None,
) -> None:
    """依次读取两个独立摄像头，并实时显示双目处理结果。"""

    left_capture = _open_camera(left_index)
    right_capture = None
    try:
        right_capture = _open_camera(right_index)
        for capture in (left_capture, right_capture):
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_FRAME_WIDTH)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_FRAME_HEIGHT)

        def read_pair() -> tuple[Image, Image]:
            left_ok, left = left_capture.read()
            right_ok, right = right_capture.read()
            if not left_ok or left is None:
                raise ValueError(f"无法从左摄像头 {left_index} 读取画面。")
            if not right_ok or right is None:
                raise ValueError(f"无法从右摄像头 {right_index} 读取画面。")
            if right.shape[:2] != left.shape[:2]:
                right = cv2.resize(
                    right,
                    (left.shape[1], left.shape[0]),
                    interpolation=cv2.INTER_AREA,
                )
            return left, right

        _run_live_loop(
            read_pair=read_pair,
            focal_px=focal_px,
            baseline_m=baseline_m,
            output_dir=output_dir,
            metadata_base={
                "input_mode": "cameras",
                "left_camera_index": left_index,
                "right_camera_index": right_index,
            },
        )
    finally:
        left_capture.release()
        if right_capture is not None:
            right_capture.release()
        cv2.destroyAllWindows()


def _run_live_loop(
    read_pair: PairReader,
    focal_px: float,
    baseline_m: float,
    output_dir: Path | None,
    metadata_base: dict[str, object],
) -> None:
    last_result: tuple[Image, FloatImage, Image, FloatImage, Image] | None = None
    click_state: dict[str, Any] = {"depth": None, "point": None}
    depth_window = "StereoRange - Depth"
    cv2.namedWindow(depth_window)

    def on_mouse(
        event: int,
        x: int,
        y: int,
        _flags: int,
        _data: object,
    ) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        depth = click_state["depth"]
        if depth is None:
            return
        value = sample_median(depth, x=x, y=y)
        click_state["point"] = (x, y)
        if value is None:
            print(f"坐标 ({x}, {y})：无法获得有效距离")
        else:
            print(f"坐标 ({x}, {y})：距离 {value:.3f} m")

    cv2.setMouseCallback(depth_window, on_mouse)
    print(
        "警告：实时模式当前使用未标定的默认焦距和基线，"
        "显示距离仅供流程演示。"
    )
    print("按 Q 或 Esc 退出；点击深度图可查询当前位置的估算距离。")

    while True:
        left, right = read_pair()
        disparity = compute_disparity(left, right)
        depth = disparity_to_depth(disparity, focal_px, baseline_m)
        disparity_preview = colorize_values(disparity, cv2.COLORMAP_TURBO)
        depth_preview = colorize_values(depth, cv2.COLORMAP_MAGMA)
        click_state["depth"] = depth

        marked_depth = depth_preview.copy()
        point = click_state["point"]
        if point is not None:
            _draw_measurement(marked_depth, depth, point[0], point[1])

        cv2.imshow("StereoRange - Left", left)
        cv2.imshow("StereoRange - Right", right)
        cv2.imshow("StereoRange - Disparity", disparity_preview)
        cv2.imshow(depth_window, marked_depth)
        last_result = (left, disparity, disparity_preview, depth, depth_preview)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if cv2.getWindowProperty(depth_window, cv2.WND_PROP_VISIBLE) < 1:
            break

    if output_dir is not None and last_result is not None:
        left, disparity, disparity_preview, depth, depth_preview = last_result
        valid_pixels = int(
            np.count_nonzero(np.isfinite(disparity) & (disparity > 0))
        )
        metadata = {
            **metadata_base,
            "width": int(left.shape[1]),
            "height": int(left.shape[0]),
            "focal_px": focal_px,
            "baseline_m": baseline_m,
            "calibration_placeholder": True,
            "depth_available": True,
            "valid_disparity_pixels": valid_pixels,
            "valid_disparity_ratio": valid_pixels / disparity.size,
        }
        save_results(
            output_dir,
            disparity,
            disparity_preview,
            depth,
            depth_preview,
            metadata,
        )
        print(f"退出前最后一帧结果已保存到：{output_dir.resolve()}")


def _open_camera(index: int):
    capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(index)
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"无法打开摄像头索引 {index}。")
    return capture


def _draw_measurement(
    preview: Image,
    depth: FloatImage,
    x: int,
    y: int,
) -> None:
    value = sample_median(depth, x=x, y=y)
    text = "N/A" if value is None else f"{value:.3f} m"
    cv2.circle(preview, (x, y), 5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(
        preview,
        text,
        (min(x + 8, max(0, preview.shape[1] - 150)), max(20, y - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
