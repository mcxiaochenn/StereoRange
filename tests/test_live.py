from __future__ import annotations

import json

import cv2
import numpy as np

from stereorange.core import generate_demo_pair
from stereorange.live import run_live_cameras, run_live_stereo_camera


class FakeCapture:
    def __init__(self, index: int, frames: dict[int, object]) -> None:
        self.index = index
        self.frames = frames
        self.released = False

    def isOpened(self) -> bool:
        return True

    def set(self, _property: int, _value: float) -> bool:
        return True

    def read(self):
        return True, self.frames[self.index].copy()

    def release(self) -> None:
        self.released = True


def test_live_cameras_refresh_frames_and_release_devices(monkeypatch) -> None:
    demo = generate_demo_pair()
    frames = {0: demo.left, 1: demo.right}
    captures: list[FakeCapture] = []
    shown_windows: list[str] = []

    def fake_video_capture(index: int, _backend: int | None = None) -> FakeCapture:
        capture = FakeCapture(index, frames)
        captures.append(capture)
        return capture

    monkeypatch.setattr(cv2, "VideoCapture", fake_video_capture)
    monkeypatch.setattr(cv2, "namedWindow", lambda _name: None)
    monkeypatch.setattr(cv2, "setMouseCallback", lambda _name, _callback: None)
    monkeypatch.setattr(
        cv2,
        "imshow",
        lambda name, _image: shown_windows.append(name),
    )
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: ord("q"))
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)

    run_live_cameras(
        left_index=0,
        right_index=1,
        focal_px=demo.focal_px,
        baseline_m=demo.baseline_m,
        output_dir=None,
    )

    assert {capture.index for capture in captures} == {0, 1}
    assert all(capture.released for capture in captures)
    assert {
        "StereoRange - Left",
        "StereoRange - Right",
        "StereoRange - Disparity",
        "StereoRange - Depth",
    }.issubset(shown_windows)


def test_side_by_side_camera_splits_saves_and_releases_device(
    monkeypatch,
    tmp_path,
) -> None:
    demo = generate_demo_pair()
    combined = np.hstack((demo.left, demo.right))
    frames = {0: combined}
    captures: list[FakeCapture] = []
    shown_shapes: dict[str, tuple[int, ...]] = {}

    def fake_video_capture(index: int, _backend: int | None = None) -> FakeCapture:
        capture = FakeCapture(index, frames)
        captures.append(capture)
        return capture

    monkeypatch.setattr(cv2, "VideoCapture", fake_video_capture)
    monkeypatch.setattr(cv2, "namedWindow", lambda _name: None)
    monkeypatch.setattr(cv2, "setMouseCallback", lambda _name, _callback: None)
    monkeypatch.setattr(
        cv2,
        "imshow",
        lambda name, image: shown_shapes.update({name: image.shape}),
    )
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: ord("q"))
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)

    run_live_stereo_camera(
        camera_index=0,
        focal_px=demo.focal_px,
        baseline_m=demo.baseline_m,
        output_dir=tmp_path,
    )

    assert all(capture.released for capture in captures)
    assert shown_shapes["StereoRange - Left"] == demo.left.shape
    assert shown_shapes["StereoRange - Right"] == demo.right.shape
    metadata = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert metadata["input_mode"] == "stereo_camera"
    assert metadata["camera_index"] == 0
    assert metadata["calibration_placeholder"] is True
