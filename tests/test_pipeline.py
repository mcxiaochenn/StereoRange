from __future__ import annotations

from stereorange.analysis import DetectionResult
from stereorange.core import generate_demo_pair
from stereorange.pipeline import FrameProcessor


class FakeDetector:
    def __init__(self) -> None:
        self.confidence = 0.4
        self.calls = 0

    def detect(self, image):
        self.calls += 1
        return (
            DetectionResult(
                class_id=0,
                label="人",
                confidence=0.9,
                bbox=(40, 40, image.shape[1] - 40, image.shape[0] - 40),
            ),
        )


def test_frame_processor_reuses_detection_between_inference_frames() -> None:
    demo = generate_demo_pair()
    detector = FakeDetector()
    processor = FrameProcessor(
        demo.focal_px,
        demo.baseline_m,
        detector=detector,
        detection_interval=3,
    )

    first = processor.process(demo.left, demo.right)
    second = processor.process(demo.left, demo.right)

    assert detector.calls == 1
    assert first.left.shape == second.left.shape == demo.left.shape
    assert first.depth.shape == first.disparity.shape == demo.left.shape[:2]
    assert first.detections[0].label == "人"


def test_frame_processor_switches_tracking_mode_and_range() -> None:
    demo = generate_demo_pair()
    detector = FakeDetector()
    processor = FrameProcessor(
        demo.focal_px,
        demo.baseline_m,
        detector=detector,
    )
    processor.update_settings(0.2, 100.0, 0.55, "objects")

    result = processor.process(demo.left, demo.right)

    assert detector.confidence == 0.55
    assert "center" in result.points
