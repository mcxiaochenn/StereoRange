from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel

from stereorange.gui import StereoRangeWindow, _open_camera


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_ui_warns_when_calibration_rms_is_too_high(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    _app()
    window = StereoRangeWindow(
        0,
        tmp_path / "calibration.npz",
        tmp_path / "model.onnx",
        start_worker=False,
    )
    window._on_system_state(
        {"camera": True, "calibration": True, "model": True, "rms": 4.087}
    )
    assert "4.09" in window.calibration_badge.text()
    assert "仅供演示参考" in window.warning_banner.text()
    window.close()


def test_thumbnail_can_become_main_view(tmp_path: Path) -> None:
    _app()
    window = StereoRangeWindow(
        0,
        tmp_path / "calibration.npz",
        tmp_path / "model.onnx",
        start_worker=False,
    )
    window._select_view("depth")
    assert window._main_key == "depth"
    assert window.main_panel.title == "深度图"
    window.close()


def test_pause_mode_and_missing_resources_are_visible(tmp_path: Path) -> None:
    _app()
    window = StereoRangeWindow(
        0,
        tmp_path / "missing-calibration.npz",
        tmp_path / "missing-model.onnx",
        start_worker=False,
    )

    window._toggle_pause()
    assert window.pause_button.text() == "继续"
    window.mode_combo.setCurrentIndex(1)
    assert window._worker._settings[3] == "objects"
    window.detections_checkbox.setChecked(False)
    assert window.settings.value("show_detections", type=bool) is False

    window._on_system_state(
        {"camera": False, "calibration": False, "model": False, "rms": None}
    )
    assert "未连接" in window.camera_badge.text()
    assert "不可用" in window.model_badge.text()
    assert "占位参数" in window.calibration_badge.text()
    assert window.retry_button.text() == "重试连接"
    label_texts = [label.text() for label in window.findChildren(QLabel)]
    assert any(
        "陆逸尘" in text and "ChenDusk" in text and "周璟雯" in text and "胡乐毅" in text
        for text in label_texts
    )
    window.close()


def test_camera_open_failure_returns_cleanly(monkeypatch) -> None:
    captures = []

    class ClosedCapture:
        def __init__(self) -> None:
            self.released = False

        def isOpened(self) -> bool:
            return False

        def release(self) -> None:
            self.released = True

    def fake_video_capture(*_args):
        capture = ClosedCapture()
        captures.append(capture)
        return capture

    monkeypatch.setattr("stereorange.gui.cv2.VideoCapture", fake_video_capture)

    assert _open_camera(0) is None
    assert len(captures) == 3
    assert all(capture.released for capture in captures)
