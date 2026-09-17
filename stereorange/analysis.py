"""物体距离统计和稳定测距点跟踪。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import monotonic
from typing import Literal

import numpy as np

from stereorange.core import FloatImage, Image

TrackingMode = Literal["scene", "objects"]
PointKind = Literal["nearest", "center", "farthest"]


@dataclass(frozen=True)
class DetectionResult:
    class_id: int
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]
    valid_depth_ratio: float = 0.0
    distance_m: float | None = None
    depth_point: tuple[int, int] | None = None


@dataclass(frozen=True)
class TrackedDistancePoint:
    kind: PointKind
    x: int | None
    y: int | None
    distance_m: float | None
    source: str

    @property
    def valid(self) -> bool:
        return (
            self.x is not None
            and self.y is not None
            and self.distance_m is not None
        )


@dataclass(frozen=True)
class ProcessedFrame:
    left: Image
    right: Image
    disparity: FloatImage
    depth: FloatImage
    disparity_preview: Image
    depth_preview: Image
    detections: tuple[DetectionResult, ...]
    points: dict[PointKind, TrackedDistancePoint]
    fps: float
    warnings: tuple[str, ...] = ()


def add_detection_distances(
    detections: list[DetectionResult] | tuple[DetectionResult, ...],
    depth: FloatImage,
    minimum_m: float,
    maximum_m: float,
) -> tuple[DetectionResult, ...]:
    """使用框内中央 60% 区域计算物体的有效深度中位数。"""

    height, width = depth.shape
    measured: list[DetectionResult] = []
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        x1, x2 = sorted((max(0, x1), min(width, x2)))
        y1, y2 = sorted((max(0, y1), min(height, y2)))
        if x2 <= x1 or y2 <= y1:
            measured.append(detection)
            continue
        margin_x = int((x2 - x1) * 0.2)
        margin_y = int((y2 - y1) * 0.2)
        inner_x1, inner_x2 = x1 + margin_x, x2 - margin_x
        inner_y1, inner_y2 = y1 + margin_y, y2 - margin_y
        region = depth[inner_y1:inner_y2, inner_x1:inner_x2]
        valid = (
            np.isfinite(region)
            & (region >= minimum_m)
            & (region <= maximum_m)
        )
        valid_count = int(np.count_nonzero(valid))
        ratio = valid_count / region.size if region.size else 0.0
        required = max(10, int(region.size * 0.1))
        if valid_count < required:
            measured.append(replace(detection, valid_depth_ratio=ratio))
            continue
        ys, xs = np.nonzero(valid)
        measured.append(
            replace(
                detection,
                valid_depth_ratio=ratio,
                distance_m=float(np.median(region[valid])),
                depth_point=(
                    int(inner_x1 + np.median(xs)),
                    int(inner_y1 + np.median(ys)),
                ),
            )
        )
    return tuple(measured)


def find_scene_extremes(
    depth: FloatImage,
    minimum_m: float,
    maximum_m: float,
    grid_size: int = 8,
    minimum_valid_ratio: float = 0.5,
) -> dict[PointKind, TrackedDistancePoint]:
    """按网格中位数寻找可靠的全场景最近和最远点。"""

    candidates: list[tuple[float, int, int]] = []
    height, width = depth.shape
    for y in range(0, height, grid_size):
        for x in range(0, width, grid_size):
            region = depth[y : y + grid_size, x : x + grid_size]
            valid = (
                np.isfinite(region)
                & (region >= minimum_m)
                & (region <= maximum_m)
            )
            if region.size and np.count_nonzero(valid) / region.size >= minimum_valid_ratio:
                candidates.append(
                    (
                        float(np.median(region[valid])),
                        min(width - 1, x + region.shape[1] // 2),
                        min(height - 1, y + region.shape[0] // 2),
                    )
                )
    if not candidates:
        return {}
    nearest = min(candidates, key=lambda item: item[0])
    farthest = max(candidates, key=lambda item: item[0])
    return {
        "nearest": TrackedDistancePoint(
            "nearest", nearest[1], nearest[2], nearest[0], "全场景"
        ),
        "farthest": TrackedDistancePoint(
            "farthest", farthest[1], farthest[2], farthest[0], "全场景"
        ),
    }


def find_object_extremes(
    detections: tuple[DetectionResult, ...],
) -> dict[PointKind, TrackedDistancePoint]:
    valid = [
        detection
        for detection in detections
        if detection.distance_m is not None and detection.depth_point is not None
    ]
    if not valid:
        return {}
    nearest = min(valid, key=lambda item: item.distance_m or np.inf)
    farthest = max(valid, key=lambda item: item.distance_m or -np.inf)
    return {
        "nearest": _point_from_detection("nearest", nearest),
        "farthest": _point_from_detection("farthest", farthest),
    }


def find_center_point(
    depth: FloatImage,
    minimum_m: float,
    maximum_m: float,
    window_size: int = 15,
) -> TrackedDistancePoint | None:
    height, width = depth.shape
    x, y = width // 2, height // 2
    radius = window_size // 2
    region = depth[
        max(0, y - radius) : min(height, y + radius + 1),
        max(0, x - radius) : min(width, x + radius + 1),
    ]
    valid = (
        np.isfinite(region)
        & (region >= minimum_m)
        & (region <= maximum_m)
    )
    if not np.any(valid):
        return None
    return TrackedDistancePoint(
        "center", x, y, float(np.median(region[valid])), "画面中心"
    )


class DistancePointTracker:
    """对三个测距点进行 EMA 平滑，并在超时后清除旧值。"""

    def __init__(self, alpha: float = 0.25, timeout_s: float = 0.5) -> None:
        self.alpha = alpha
        self.timeout_s = timeout_s
        self._points: dict[PointKind, TrackedDistancePoint] = {}
        self._last_seen: dict[PointKind, float] = {}

    def reset(self) -> None:
        self._points.clear()
        self._last_seen.clear()

    def update(
        self,
        candidates: dict[PointKind, TrackedDistancePoint],
        now: float | None = None,
    ) -> dict[PointKind, TrackedDistancePoint]:
        timestamp = monotonic() if now is None else now
        for kind in ("nearest", "center", "farthest"):
            candidate = candidates.get(kind)
            if candidate is not None and candidate.valid:
                previous = self._points.get(kind)
                self._points[kind] = (
                    candidate if previous is None else self._smooth(previous, candidate)
                )
                self._last_seen[kind] = timestamp
            elif (
                kind in self._last_seen
                and timestamp - self._last_seen[kind] > self.timeout_s
            ):
                self._points.pop(kind, None)
                self._last_seen.pop(kind, None)
        return dict(self._points)

    def _smooth(
        self,
        previous: TrackedDistancePoint,
        current: TrackedDistancePoint,
    ) -> TrackedDistancePoint:
        assert previous.x is not None and previous.y is not None
        assert previous.distance_m is not None
        assert current.x is not None and current.y is not None
        assert current.distance_m is not None
        alpha = self.alpha
        return TrackedDistancePoint(
            kind=current.kind,
            x=round(previous.x * (1 - alpha) + current.x * alpha),
            y=round(previous.y * (1 - alpha) + current.y * alpha),
            distance_m=previous.distance_m * (1 - alpha)
            + current.distance_m * alpha,
            source=current.source,
        )


def _point_from_detection(
    kind: PointKind, detection: DetectionResult
) -> TrackedDistancePoint:
    assert detection.depth_point is not None
    assert detection.distance_m is not None
    return TrackedDistancePoint(
        kind,
        detection.depth_point[0],
        detection.depth_point[1],
        detection.distance_m,
        detection.label,
    )
