from pathlib import Path

import pytest

from stereorange.detection import YoloXDetector


def test_detector_reports_missing_model(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="识别模型不存在"):
        YoloXDetector(tmp_path / "missing.onnx")
