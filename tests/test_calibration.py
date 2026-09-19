from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from stereorange.calibration import (
    StereoCalibration,
    StereoRectifier,
    create_object_points,
    load_calibration,
    save_calibration,
    solve_stereo_calibration,
    split_side_by_side,
)
from stereorange.pattern import generate_checkerboard_files


def make_calibration() -> StereoCalibration:
    camera_matrix = np.array(
        [[300.0, 0.0, 160.0], [0.0, 300.0, 120.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    projection_left = np.hstack(
        (camera_matrix, np.zeros((3, 1), dtype=np.float64))
    )
    projection_right = projection_left.copy()
    projection_right[0, 3] = -18.0
    return StereoCalibration(
        image_size=(320, 240),
        board_size=(9, 6),
        square_size_m=0.025,
        left_camera_matrix=camera_matrix,
        left_distortion=np.zeros((1, 5), dtype=np.float64),
        right_camera_matrix=camera_matrix.copy(),
        right_distortion=np.zeros((1, 5), dtype=np.float64),
        rotation=np.eye(3, dtype=np.float64),
        translation=np.array([[-0.06], [0.0], [0.0]], dtype=np.float64),
        essential=np.eye(3, dtype=np.float64),
        fundamental=np.eye(3, dtype=np.float64),
        rectification_left=np.eye(3, dtype=np.float64),
        rectification_right=np.eye(3, dtype=np.float64),
        projection_left=projection_left,
        projection_right=projection_right,
        disparity_to_depth=np.eye(4, dtype=np.float64),
        rms_left=0.2,
        rms_right=0.2,
        rms_stereo=0.3,
        valid_pairs=25,
    )


def test_mobile_export_preserves_matrices_and_units(tmp_path: Path) -> None:
    import json
    from stereorange.mobile_export import export_mobile_calibration

    source, target = tmp_path / "calibration.npz", tmp_path / "mobile.json"
    original = make_calibration()
    save_calibration(source, original)
    export_mobile_calibration(source, target)
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["schema_version"] == 1
    assert result["length_unit"] == "m"
    assert result["image_size"] == [320, 240]
    assert np.allclose(result["projection_right"], original.projection_right)
    assert np.allclose(result["translation"], original.translation)
    assert result["rms_stereo"] == original.rms_stereo


def test_mobile_export_rejects_nonfinite_without_replacing_file(tmp_path: Path) -> None:
    from stereorange.mobile_export import export_mobile_calibration

    original = make_calibration()
    original.left_camera_matrix[0, 0] = np.nan
    source, target = tmp_path / "bad.npz", tmp_path / "previous.json"
    save_calibration(source, original)
    target.write_text("previous", encoding="utf-8")
    with pytest.raises(ValueError):
        export_mobile_calibration(source, target)
    assert target.read_text(encoding="utf-8") == "previous"


def test_mobile_export_cli(tmp_path: Path) -> None:
    import calibrate

    source, target = tmp_path / "input.npz", tmp_path / "output.json"
    save_calibration(source, make_calibration())
    assert calibrate.main(["export-mobile", "--input", str(source), "--output", str(target)]) == 0
    assert target.is_file()


def test_create_object_points_uses_measured_square_size() -> None:
    points = create_object_points((9, 6), square_size_m=0.025)

    assert points.shape == (54, 3)
    assert points.dtype == np.float32
    assert np.allclose(points[0], [0.0, 0.0, 0.0])
    assert np.allclose(points[-1], [0.2, 0.125, 0.0])


def test_split_side_by_side_returns_contiguous_views() -> None:
    frame = np.zeros((240, 640, 3), dtype=np.uint8)
    frame[:, :320] = 20
    frame[:, 320:] = 200

    left, right = split_side_by_side(frame)

    assert left.shape == right.shape == (240, 320, 3)
    assert left.flags.c_contiguous and right.flags.c_contiguous
    assert int(left.mean()) == 20
    assert int(right.mean()) == 200


def test_split_side_by_side_rejects_invalid_width() -> None:
    frame = np.zeros((240, 639, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="横向等分"):
        split_side_by_side(frame)


def test_calibration_round_trip_and_rectification(tmp_path: Path) -> None:
    path = tmp_path / "calibration.npz"
    original = make_calibration()
    save_calibration(path, original)

    loaded = load_calibration(path)
    rectifier = StereoRectifier(loaded)
    left = np.full((240, 320, 3), 50, dtype=np.uint8)
    right = np.full((240, 320, 3), 100, dtype=np.uint8)
    rectified_left, rectified_right = rectifier.rectify(left, right)

    assert loaded.image_size == (320, 240)
    assert loaded.focal_px == pytest.approx(300.0)
    assert loaded.baseline_m == pytest.approx(0.06)
    assert loaded.valid_pairs == 25
    assert np.array_equal(rectified_left, left)
    assert np.array_equal(rectified_right, right)


def test_rectifier_rejects_wrong_image_size() -> None:
    rectifier = StereoRectifier(make_calibration())
    wrong = np.zeros((120, 160, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="标定分辨率"):
        rectifier.rectify(wrong, wrong)


def test_generate_checkerboard_files_has_exact_physical_dimensions(
    tmp_path: Path,
) -> None:
    pdf_path, svg_path = generate_checkerboard_files(
        tmp_path,
        board_size=(9, 6),
        square_size_mm=25.0,
    )

    assert pdf_path.read_bytes().startswith(b"%PDF")
    svg = svg_path.read_text(encoding="utf-8")
    assert 'width="297mm"' in svg
    assert 'height="210mm"' in svg
    assert 'width="25mm"' in svg
    assert svg.count("<rect") == 36


def test_solve_stereo_calibration_recovers_synthetic_baseline() -> None:
    board_size = (9, 6)
    object_template = create_object_points(board_size, 0.025)
    camera_matrix = np.array(
        [[300.0, 0.0, 160.0], [0.0, 300.0, 120.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    distortion = np.zeros(5, dtype=np.float64)
    baseline = 0.08
    object_points = []
    left_points = []
    right_points = []
    for index in range(15):
        row, column = divmod(index, 5)
        rotation = np.array(
            [
                0.03 * (row - 1),
                0.04 * (column - 2),
                0.015 * ((index % 3) - 1),
            ],
            dtype=np.float64,
        )
        translation_left = np.array(
            [
                -0.10 + 0.04 * column,
                -0.06 + 0.05 * row,
                0.75 + 0.08 * (index % 4),
            ],
            dtype=np.float64,
        )
        translation_right = translation_left + np.array(
            [-baseline, 0.0, 0.0], dtype=np.float64
        )
        projected_left, _ = cv2.projectPoints(
            object_template,
            rotation,
            translation_left,
            camera_matrix,
            distortion,
        )
        projected_right, _ = cv2.projectPoints(
            object_template,
            rotation,
            translation_right,
            camera_matrix,
            distortion,
        )
        object_points.append(object_template.copy())
        left_points.append(projected_left.astype(np.float32))
        right_points.append(projected_right.astype(np.float32))

    calibration = solve_stereo_calibration(
        object_points,
        left_points,
        right_points,
        image_size=(320, 240),
        board_size=board_size,
        square_size_m=0.025,
    )

    assert calibration.valid_pairs == 15
    assert calibration.baseline_m == pytest.approx(baseline, rel=0.02)
    assert calibration.focal_px == pytest.approx(300.0, rel=0.02)
    assert calibration.rms_stereo < 0.01
