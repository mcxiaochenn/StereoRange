import cv2

from stereorange.camera import configure_stereo_capture
from stereorange.config import (
    DEFAULT_STEREO_FRAME_FPS,
    DEFAULT_STEREO_FRAME_HEIGHT,
    DEFAULT_STEREO_FRAME_WIDTH,
)


def test_configure_stereo_capture_requests_default_mode() -> None:
    values = {}

    class FakeCapture:
        def set(self, property_id, value):
            values[property_id] = value
            return True

    configure_stereo_capture(FakeCapture())

    assert values[cv2.CAP_PROP_FRAME_WIDTH] == DEFAULT_STEREO_FRAME_WIDTH
    assert values[cv2.CAP_PROP_FRAME_HEIGHT] == DEFAULT_STEREO_FRAME_HEIGHT
    assert values[cv2.CAP_PROP_FPS] == DEFAULT_STEREO_FRAME_FPS
    assert int(values[cv2.CAP_PROP_FOURCC]) == cv2.VideoWriter_fourcc(*"MJPG")
