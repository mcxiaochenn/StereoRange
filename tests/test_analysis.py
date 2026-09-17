from __future__ import annotations

import numpy as np
import pytest

from stereorange.analysis import (
    DetectionResult,
    DistancePointTracker,
    TrackedDistancePoint,
    add_detection_distances,
    find_center_point,
    find_object_extremes,
    find_scene_extremes,
)


def test_detection_distance_uses_inner_region_median_and_range() -> None:
    depth = np.full((100, 100), np.nan, dtype=np.float32)
    depth[30:70, 30:70] = 1.25
    depth[20:30, 20:80] = 0.1
    detection = DetectionResult(0, "人", 0.9, (20, 20, 80, 80))

    result = add_detection_distances((detection,), depth, 0.2, 3.0)[0]

    assert result.distance_m == pytest.approx(1.25)
    assert result.depth_point == (49, 49)
    assert result.valid_depth_ratio > 0.9


def test_detection_distance_requires_enough_valid_pixels() -> None:
    depth = np.full((40, 40), np.nan, dtype=np.float32)
    depth[20, 20] = 1.0
    detection = DetectionResult(0, "人", 0.9, (0, 0, 40, 40))

    result = add_detection_distances((detection,), depth, 0.2, 3.0)[0]

    assert result.distance_m is None


def test_scene_extremes_use_reliable_grid_medians() -> None:
    depth = np.full((16, 24), np.nan, dtype=np.float32)
    depth[0:8, 0:8] = 0.5
    depth[0:8, 8:16] = 1.5
    depth[8:16, 16:24] = 2.5
    depth[15, 0] = 0.2

    points = find_scene_extremes(depth, 0.2, 3.0)

    assert points["nearest"].distance_m == pytest.approx(0.5)
    assert points["farthest"].distance_m == pytest.approx(2.5)


def test_object_extremes_and_center_point() -> None:
    detections = (
        DetectionResult(0, "人", 0.9, (0, 0, 10, 10), 1.0, 0.8, (5, 5)),
        DetectionResult(2, "汽车", 0.8, (10, 0, 20, 10), 1.0, 2.2, (15, 5)),
    )
    depth = np.full((31, 31), np.nan, dtype=np.float32)
    depth[12:19, 12:19] = 1.4

    extremes = find_object_extremes(detections)
    center = find_center_point(depth, 0.2, 3.0)

    assert extremes["nearest"].source == "人"
    assert extremes["farthest"].source == "汽车"
    assert center is not None and center.distance_m == pytest.approx(1.4)


def test_tracker_smooths_and_clears_after_timeout() -> None:
    tracker = DistancePointTracker(alpha=0.25, timeout_s=0.5)
    first = TrackedDistancePoint("nearest", 0, 0, 1.0, "全场景")
    second = TrackedDistancePoint("nearest", 8, 4, 2.0, "全场景")

    assert tracker.update({"nearest": first}, now=0.0)["nearest"].distance_m == 1.0
    smoothed = tracker.update({"nearest": second}, now=0.1)["nearest"]
    assert smoothed.x == 2
    assert smoothed.y == 1
    assert smoothed.distance_m == pytest.approx(1.25)
    assert "nearest" in tracker.update({}, now=0.5)
    assert "nearest" not in tracker.update({}, now=0.61)


def test_no_valid_depth_produces_no_measurement() -> None:
    depth = np.full((32, 32), np.nan, dtype=np.float32)

    assert find_scene_extremes(depth, 0.2, 3.0) == {}
    assert find_center_point(depth, 0.2, 3.0) is None
