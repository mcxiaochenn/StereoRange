from __future__ import annotations

import numpy as np
import pytest

from stereorange.core import (
    compute_disparity,
    disparity_to_depth,
    generate_demo_pair,
    sample_median,
)


def test_disparity_to_depth_marks_invalid_values() -> None:
    disparity = np.array([[10.0, 0.0, -1.0]], dtype=np.float32)

    depth = disparity_to_depth(disparity, focal_px=100.0, baseline_m=0.2)

    assert depth[0, 0] == 2.0
    assert np.isnan(depth[0, 1])
    assert np.isnan(depth[0, 2])


def test_sample_median_uses_valid_values_in_seven_pixel_window() -> None:
    values = np.full((11, 11), np.nan, dtype=np.float32)
    values[4:7, 4:7] = np.arange(1, 10, dtype=np.float32).reshape(3, 3)

    assert sample_median(values, x=5, y=5) == 5.0
    assert sample_median(values, x=0, y=0) is None


def test_demo_pair_is_deterministic() -> None:
    first = generate_demo_pair()
    second = generate_demo_pair()

    assert first.left.shape == first.right.shape == (360, 640, 3)
    assert first.left.dtype == first.right.dtype == np.uint8
    assert np.array_equal(first.left, second.left)
    assert np.array_equal(first.right, second.right)
    assert first.focal_px > 0
    assert first.baseline_m > 0


def test_demo_pair_produces_positive_disparity() -> None:
    demo = generate_demo_pair()

    disparity = compute_disparity(demo.left, demo.right)

    assert disparity.shape == demo.left.shape[:2]
    assert disparity.dtype == np.float32
    assert np.count_nonzero(disparity > 0) > disparity.size * 0.1


def test_invalid_depth_and_sampling_parameters_are_rejected() -> None:
    disparity = np.ones((4, 4), dtype=np.float32)

    with pytest.raises(ValueError, match="焦距和基线"):
        disparity_to_depth(disparity, focal_px=0, baseline_m=0.1)
    with pytest.raises(ValueError, match="正奇数"):
        sample_median(disparity, x=1, y=1, window_size=4)


def test_too_small_images_are_rejected() -> None:
    image = np.zeros((20, 20, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="图像尺寸过小"):
        compute_disparity(image, image)
