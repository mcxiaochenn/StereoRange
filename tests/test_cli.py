from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from main import main
from stereorange.core import generate_demo_pair


def test_default_headless_run_saves_complete_result(tmp_path: Path) -> None:
    exit_code = main(["--demo", "--no-gui", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "disparity.npy").is_file()
    assert (tmp_path / "disparity.png").is_file()
    assert (tmp_path / "depth.npy").is_file()
    assert (tmp_path / "depth.png").is_file()
    metadata = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert metadata["input_mode"] == "demo"
    assert metadata["depth_available"] is True
    assert metadata["valid_disparity_pixels"] > 0


def test_local_images_without_camera_parameters_only_save_disparity(
    tmp_path: Path,
    capsys,
) -> None:
    demo = generate_demo_pair()
    left_path = tmp_path / "left.png"
    right_path = tmp_path / "right.png"
    output_path = tmp_path / "output"
    assert cv2.imwrite(str(left_path), demo.left)
    assert cv2.imwrite(str(right_path), demo.right)

    exit_code = main(
        [
            "--left",
            str(left_path),
            "--right",
            str(right_path),
            "--no-gui",
            "--output-dir",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert (output_path / "disparity.npy").is_file()
    assert not (output_path / "depth.npy").exists()
    metadata = json.loads(
        (output_path / "result.json").read_text(encoding="utf-8")
    )
    assert metadata["input_mode"] == "files"
    assert metadata["depth_available"] is False
    assert "深度不可用" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--left", "left.png", "--no-gui"], "必须同时提供"),
        (["--focal-px", "700", "--no-gui"], "必须同时提供"),
        (
            ["--focal-px", "-1", "--baseline-m", "0.12", "--no-gui"],
            "--focal-px",
        ),
        (
            ["--focal-px", "700", "--baseline-m", "0", "--no-gui"],
            "--baseline-m",
        ),
    ],
)
def test_invalid_parameter_combinations_return_error(
    arguments: list[str],
    message: str,
    capsys,
) -> None:
    assert main(arguments) == 2
    assert message in capsys.readouterr().err


def test_missing_local_image_returns_error(capsys) -> None:
    exit_code = main(
        ["--left", "missing-left.png", "--right", "missing-right.png", "--no-gui"]
    )

    assert exit_code == 2
    assert "图像文件不存在" in capsys.readouterr().err


def test_undecodable_local_image_returns_error(tmp_path: Path, capsys) -> None:
    invalid_path = tmp_path / "invalid.png"
    invalid_path.write_bytes(b"")

    exit_code = main(
        [
            "--left",
            str(invalid_path),
            "--right",
            str(invalid_path),
            "--no-gui",
        ]
    )

    assert exit_code == 2
    assert "无法解码图像文件" in capsys.readouterr().err


def test_different_image_sizes_return_error(tmp_path: Path, capsys) -> None:
    left_path = tmp_path / "left.png"
    right_path = tmp_path / "right.png"
    assert cv2.imwrite(str(left_path), np.zeros((64, 96, 3), dtype=np.uint8))
    assert cv2.imwrite(str(right_path), np.zeros((64, 128, 3), dtype=np.uint8))

    exit_code = main(
        [
            "--left",
            str(left_path),
            "--right",
            str(right_path),
            "--no-gui",
        ]
    )

    assert exit_code == 2
    assert "左右图像尺寸必须一致" in capsys.readouterr().err


def test_default_mode_dispatches_to_competition_ui(
    monkeypatch,
    tmp_path: Path,
) -> None:
    received: dict[str, object] = {}

    def fake_run_competition_gui(camera_index, calibration_path, model_path) -> int:
        received.update(
            camera_index=camera_index,
            calibration_path=calibration_path,
            model_path=model_path,
        )
        return 0

    monkeypatch.setattr("main.run_competition_gui", fake_run_competition_gui)
    monkeypatch.setattr(
        "main.DEFAULT_CALIBRATION_PATH",
        tmp_path / "missing-calibration.npz",
    )

    assert main([]) == 0
    assert received["camera_index"] == 0
    assert received["calibration_path"] == tmp_path / "missing-calibration.npz"


def test_classic_ui_keeps_side_by_side_camera_dispatch(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_run_live_stereo_camera(**kwargs) -> None:
        received.update(kwargs)

    monkeypatch.setattr("main.run_live_stereo_camera", fake_run_live_stereo_camera)

    assert main(["--classic-ui"]) == 0
    assert received["camera_index"] == 0


def test_dual_camera_mode_dispatches_two_device_indices(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_run_live_cameras(**kwargs) -> None:
        received.update(kwargs)

    monkeypatch.setattr("main.run_live_cameras", fake_run_live_cameras)

    assert main(["--dual-camera", "--left-camera", "1", "--right-camera", "2"]) == 0
    assert received["left_index"] == 1
    assert received["right_index"] == 2


def test_live_camera_mode_rejects_no_gui(capsys) -> None:
    assert main(["--no-gui"]) == 2
    assert "实时摄像头模式不能使用 --no-gui" in capsys.readouterr().err


def test_demo_and_file_inputs_are_mutually_exclusive(capsys) -> None:
    assert main(["--demo", "--left", "left.png", "--right", "right.png"]) == 2
    assert "--demo 不能与本地图像" in capsys.readouterr().err
