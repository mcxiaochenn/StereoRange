"""结果着色、保存与 OpenCV 交互窗口。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from stereorange.core import FloatImage, Image, sample_median


def colorize_values(values: FloatImage, colormap: int) -> Image:
    """将有效浮点值按百分位缩放为彩色预览图。"""

    valid = np.isfinite(values) & (values > 0)
    normalized = np.zeros(values.shape, dtype=np.uint8)
    if np.any(valid):
        lower, upper = np.percentile(values[valid], (2, 98))
        if upper <= lower:
            upper = lower + 1.0
        scaled = np.clip((values - lower) / (upper - lower), 0.0, 1.0)
        normalized[valid] = (scaled[valid] * 255).astype(np.uint8)
    preview = cv2.applyColorMap(normalized, colormap)
    preview[~valid] = 0
    return preview


def save_results(
    output_dir: Path,
    disparity: FloatImage,
    disparity_preview: Image,
    depth: FloatImage | None,
    depth_preview: Image | None,
    metadata: dict[str, Any],
) -> None:
    """保存原始数组、预览图和 JSON 摘要。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "disparity.npy", disparity)
    _write_png(output_dir / "disparity.png", disparity_preview)
    if depth is not None and depth_preview is not None:
        np.save(output_dir / "depth.npy", depth)
        _write_png(output_dir / "depth.png", depth_preview)
    (output_dir / "result.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def show_results(
    left: Image,
    right: Image,
    disparity: FloatImage,
    disparity_preview: Image,
    depth: FloatImage | None,
    depth_preview: Image | None,
) -> None:
    """显示左右图和结果，并允许点击查询视差或深度。"""

    cv2.imshow("StereoRange - Left", left)
    cv2.imshow("StereoRange - Right", right)
    cv2.imshow("StereoRange - Disparity", disparity_preview)

    if depth is not None and depth_preview is not None:
        target_values = depth
        target_preview = depth_preview
        target_window = "StereoRange - Depth"
        unit = "m"
        label = "距离"
        cv2.imshow(target_window, target_preview)
    else:
        target_values = disparity
        target_preview = disparity_preview
        target_window = "StereoRange - Disparity"
        unit = "px"
        label = "视差"

    def on_mouse(event: int, x: int, y: int, _flags: int, _data: object) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        value = sample_median(target_values, x=x, y=y)
        marked = target_preview.copy()
        cv2.circle(marked, (x, y), 5, (255, 255, 255), 1, cv2.LINE_AA)
        if value is None:
            text = "N/A"
            print(f"坐标 ({x}, {y})：无法获得有效{label}")
        else:
            text = f"{value:.3f} {unit}"
            print(f"坐标 ({x}, {y})：{label} {value:.3f} {unit}")
        cv2.putText(
            marked,
            text,
            (min(x + 8, max(0, marked.shape[1] - 150)), max(20, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.imshow(target_window, marked)

    cv2.setMouseCallback(target_window, on_mouse)
    print(f"请点击{target_window}窗口查询{label}，按 Q 或 Esc 退出。")
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):
            break
        if cv2.getWindowProperty(target_window, cv2.WND_PROP_VISIBLE) < 1:
            break
    cv2.destroyAllWindows()


def _write_png(path: Path, image: Image) -> None:
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise OSError(f"无法编码结果图像：{path}")
    encoded.tofile(str(path))
