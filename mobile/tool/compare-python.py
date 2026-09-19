"""在同一组合成深度数据上对照 Python 与 Rust 的距离统计规则。"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from stereorange.analysis import (  # noqa: E402
    DetectionResult, add_detection_distances, find_center_point,
    find_object_extremes, find_scene_extremes,
)


def main() -> None:
    rng = np.random.default_rng(20260919)
    detections = [DetectionResult(0, "人", .9, (5, 3, 27, 30)),
                  DetectionResult(39, "瓶子", .8, (34, 10, 57, 40))]
    cases = [rng.uniform(.1, 3.5, (48, 64)).astype(np.float32),
             np.ones((48, 64), np.float32), np.full((48, 64), np.nan, np.float32)]
    cases[0][::3, ::2] = np.nan
    for depth in cases:
        payload = {
            "width": 64, "height": 48,
            "depth": [float(v) if np.isfinite(v) else None for v in depth.flat],
            "detections": [asdict(d) for d in detections],
        }
        output = subprocess.run(
            ["cargo", "run", "--quiet", "--locked", "--manifest-path",
             str(ROOT / "mobile/rust/Cargo.toml"), "--example", "compare_analysis"],
            input=json.dumps(payload), text=True, encoding="utf-8", capture_output=True, check=True,
        )
        rust = json.loads(output.stdout)
        measured = add_detection_distances(detections, depth, .2, 3.)
        for actual, expected in zip(rust["detections"], measured):
            for key in ("distance_m", "valid_depth_ratio", "depth_point"):
                value = getattr(expected, key)
                if value is None:
                    assert actual[key] is None
                else:
                    np.testing.assert_allclose(actual[key], value, rtol=1e-5, atol=1e-6)
        for mode, expected in (
            ("scene", find_scene_extremes(depth, .2, 3.)),
            ("objects", find_object_extremes(measured)),
        ):
            center = find_center_point(depth, .2, 3.)
            if center is not None:
                expected["center"] = center
            actual = {p["kind"]: p for p in rust[mode]}
            assert actual.keys() == expected.keys()
            for kind, point in expected.items():
                np.testing.assert_allclose(
                    [actual[kind][k] for k in ("x", "y", "distance_m")],
                    [point.x, point.y, point.distance_m], rtol=1e-5, atol=1e-6,
                )
    print("Python/Rust 对照通过：随机深度、同值极值、全无效深度，共 3 组。")


if __name__ == "__main__":
    main()
