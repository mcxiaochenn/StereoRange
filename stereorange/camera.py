"""双目相机采集模式配置。"""

from __future__ import annotations

import cv2

from stereorange.config import (
    DEFAULT_STEREO_FRAME_CODEC,
    DEFAULT_STEREO_FRAME_FPS,
    DEFAULT_STEREO_FRAME_HEIGHT,
    DEFAULT_STEREO_FRAME_WIDTH,
)


def configure_stereo_capture(capture) -> None:
    """请求低延迟的 640×240 横向双目模式。"""

    capture.set(
        cv2.CAP_PROP_FOURCC,
        cv2.VideoWriter_fourcc(*DEFAULT_STEREO_FRAME_CODEC),
    )
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_STEREO_FRAME_WIDTH)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_STEREO_FRAME_HEIGHT)
    capture.set(cv2.CAP_PROP_FPS, DEFAULT_STEREO_FRAME_FPS)
