"""可被桌面界面和后续移动端复用的单帧处理流水线。"""

from __future__ import annotations

from threading import Lock
from time import perf_counter
from typing import Protocol

from stereorange.analysis import (
    DetectionResult,
    DistancePointTracker,
    ProcessedFrame,
    TrackingMode,
    add_detection_distances,
    find_center_point,
    find_object_extremes,
    find_scene_extremes,
)
from stereorange.calibration import StereoRectifier
from stereorange.core import Image, compute_disparity, disparity_to_depth
from stereorange.presentation import colorize_values

import cv2


class Detector(Protocol):
    confidence: float

    def detect(self, image: Image) -> tuple[DetectionResult, ...]: ...


class FrameProcessor:
    def __init__(
        self,
        focal_px: float,
        baseline_m: float,
        rectifier: StereoRectifier | None = None,
        detector: Detector | None = None,
        detection_interval: int = 2,
    ) -> None:
        self.focal_px = focal_px
        self.baseline_m = baseline_m
        self.rectifier = rectifier
        self.detector = detector
        self.detection_interval = max(1, detection_interval)
        self.minimum_m = 0.20
        self.maximum_m = 3.00
        self.mode: TrackingMode = "scene"
        self._frame_number = 0
        self._detections: tuple[DetectionResult, ...] = ()
        self._tracker = DistancePointTracker()
        self._lock = Lock()
        self._fps = 0.0

    def update_settings(
        self,
        minimum_m: float,
        maximum_m: float,
        confidence: float,
        mode: TrackingMode,
    ) -> None:
        if minimum_m <= 0 or maximum_m <= minimum_m:
            raise ValueError("距离范围必须为正数，且最大值必须大于最小值。")
        with self._lock:
            mode_changed = mode != self.mode
            self.minimum_m = minimum_m
            self.maximum_m = maximum_m
            self.mode = mode
            if self.detector is not None:
                self.detector.confidence = confidence
            if mode_changed:
                self._tracker.reset()

    def process(self, left: Image, right: Image) -> ProcessedFrame:
        started = perf_counter()
        if self.rectifier is not None:
            left, right = self.rectifier.rectify(left, right)
        disparity = compute_disparity(left, right)
        depth = disparity_to_depth(disparity, self.focal_px, self.baseline_m)
        with self._lock:
            minimum_m = self.minimum_m
            maximum_m = self.maximum_m
            mode = self.mode
        if (
            self.detector is not None
            and self._frame_number % self.detection_interval == 0
        ):
            self._detections = self.detector.detect(left)
        detections = add_detection_distances(
            self._detections,
            depth,
            minimum_m,
            maximum_m,
        )
        extremes = (
            find_scene_extremes(depth, minimum_m, maximum_m)
            if mode == "scene"
            else find_object_extremes(detections)
        )
        center = find_center_point(depth, minimum_m, maximum_m)
        candidates = dict(extremes)
        if center is not None:
            candidates["center"] = center
        points = self._tracker.update(candidates)
        disparity_preview = colorize_values(disparity, cv2.COLORMAP_TURBO)
        depth_preview = colorize_values(depth, cv2.COLORMAP_MAGMA)
        elapsed = max(perf_counter() - started, 1e-6)
        instant_fps = 1.0 / elapsed
        self._fps = instant_fps if self._fps == 0 else self._fps * 0.8 + instant_fps * 0.2
        self._frame_number += 1
        warnings = ()
        if self.detector is None:
            warnings = ("识别模型不可用，当前仅显示场景测距。",)
        return ProcessedFrame(
            left=left,
            right=right,
            disparity=disparity,
            depth=depth,
            disparity_preview=disparity_preview,
            depth_preview=depth_preview,
            detections=detections,
            points=points,
            fps=self._fps,
            warnings=warnings,
        )
