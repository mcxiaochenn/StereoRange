"""StereoRange 双目相机标定工具。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from stereorange.calibration import (
    StereoCalibration,
    create_object_points,
    detect_chessboard_pair,
    save_calibration,
    solve_stereo_calibration,
    split_side_by_side,
)
from stereorange.config import DEFAULT_STEREO_CAMERA_INDEX
from stereorange.pattern import generate_checkerboard_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成棋盘格、采集图像并完成双目标定。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pattern = subparsers.add_parser("pattern", help="生成 A4 横向可打印棋盘格")
    _add_board_arguments(pattern, millimetres=True)
    pattern.add_argument("--output-dir", type=Path, default=Path("assets"))

    capture = subparsers.add_parser("capture", help="从横向拼接双目摄像头采集标定图")
    _add_board_arguments(capture, millimetres=False)
    capture.add_argument(
        "--camera", type=int, default=DEFAULT_STEREO_CAMERA_INDEX
    )
    capture.add_argument("--output-dir", type=Path, default=Path("private-data/images"))
    capture.add_argument("--target", type=int, default=25, help="建议采集数量")

    solve = subparsers.add_parser("solve", help="根据已采集图像求解标定参数")
    _add_board_arguments(solve, millimetres=True)
    solve.add_argument("--images", type=Path, default=Path("private-data/images"))
    solve.add_argument(
        "--output", type=Path, default=Path("private-data/calibration.npz")
    )
    return parser


def _add_board_arguments(parser: argparse.ArgumentParser, millimetres: bool) -> None:
    parser.add_argument("--cols", type=int, default=9, help="横向内角点数")
    parser.add_argument("--rows", type=int, default=6, help="纵向内角点数")
    if millimetres:
        parser.add_argument("--square-mm", type=float, default=25.0)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        board_size = (args.cols, args.rows)
        if args.command == "pattern":
            pdf_path, svg_path = generate_checkerboard_files(
                args.output_dir, board_size, args.square_mm
            )
            print(f"PDF 已生成：{pdf_path.resolve()}")
            print(f"SVG 已生成：{svg_path.resolve()}")
            return 0
        if args.command == "capture":
            _validate_capture_args(args)
            capture_pairs(args.camera, args.output_dir, board_size, args.target)
            return 0
        if args.command == "solve":
            calibration = solve_from_images(
                args.images, board_size, args.square_mm / 1000.0
            )
            save_calibration(args.output, calibration)
            print(f"有效图像对：{calibration.valid_pairs}")
            print(
                "重投影 RMS："
                f"左 {calibration.rms_left:.4f} px，"
                f"右 {calibration.rms_right:.4f} px，"
                f"双目 {calibration.rms_stereo:.4f} px"
            )
            print(f"校正后焦距：{calibration.focal_px:.3f} px")
            print(f"基线：{calibration.baseline_m:.6f} m")
            print(f"标定文件已保存：{args.output.resolve()}")
            return 0
        raise ValueError("未知标定命令。")
    except (OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


def capture_pairs(
    camera_index: int,
    output_dir: Path,
    board_size: tuple[int, int],
    target: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = _open_camera(camera_index)
    saved = _next_pair_index(output_dir) - 1
    print("空格：保存当前有效图像对；Q 或 Esc：退出。")
    try:
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(f"无法从双目摄像头 {camera_index} 读取画面。")
            left, right = split_side_by_side(frame)
            detected = detect_chessboard_pair(left, right, board_size)
            left_preview, right_preview = left.copy(), right.copy()
            if detected is not None:
                left_points, right_points = detected
                cv2.drawChessboardCorners(
                    left_preview, board_size, left_points, True
                )
                cv2.drawChessboardCorners(
                    right_preview, board_size, right_points, True
                )
            status = (
                f"READY  {saved}/{target}"
                if detected is not None
                else f"NOT FOUND  {saved}/{target}"
            )
            color = (0, 220, 0) if detected is not None else (0, 0, 255)
            for preview in (left_preview, right_preview):
                cv2.putText(
                    preview,
                    status,
                    (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                    cv2.LINE_AA,
                )
            cv2.imshow("StereoRange Calibration - Left", left_preview)
            cv2.imshow("StereoRange Calibration - Right", right_preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" ") and detected is not None:
                saved += 1
                _write_image(output_dir / f"left_{saved:03d}.png", left)
                _write_image(output_dir / f"right_{saved:03d}.png", right)
                print(f"已保存第 {saved} 组。")
            if cv2.getWindowProperty(
                "StereoRange Calibration - Left", cv2.WND_PROP_VISIBLE
            ) < 1:
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()
    print(f"采集结束，共有 {saved} 组图像。")


def solve_from_images(
    images_dir: Path,
    board_size: tuple[int, int],
    square_size_m: float,
) -> StereoCalibration:
    if square_size_m <= 0:
        raise ValueError("方格边长必须为正数。")
    left_paths = sorted(images_dir.glob("left_*.png"))
    if not left_paths:
        raise ValueError(f"未找到标定图像：{images_dir}")
    object_template = create_object_points(board_size, square_size_m)
    object_points = []
    left_points = []
    right_points = []
    image_size = None
    skipped = 0
    for left_path in left_paths:
        suffix = left_path.name.removeprefix("left_")
        right_path = images_dir / f"right_{suffix}"
        if not right_path.is_file():
            skipped += 1
            continue
        left = _read_image(left_path)
        right = _read_image(right_path)
        if left.shape != right.shape:
            raise ValueError(f"左右标定图尺寸不一致：{left_path.name}")
        current_size = (left.shape[1], left.shape[0])
        if image_size is None:
            image_size = current_size
        elif current_size != image_size:
            raise ValueError("所有标定图像必须使用同一分辨率。")
        detected = detect_chessboard_pair(left, right, board_size)
        if detected is None:
            skipped += 1
            print(f"跳过未同时识别角点的图像对：{suffix}")
            continue
        left_corners, right_corners = detected
        object_points.append(object_template.copy())
        left_points.append(left_corners)
        right_points.append(right_corners)
    if image_size is None:
        raise ValueError("没有可读取的成对标定图像。")
    if skipped:
        print(f"共跳过 {skipped} 组无效或不完整图像。")
    return solve_stereo_calibration(
        object_points,
        left_points,
        right_points,
        image_size,
        board_size,
        square_size_m,
    )


def _validate_capture_args(args: argparse.Namespace) -> None:
    if args.camera < 0:
        raise ValueError("摄像头索引不能为负数。")
    if args.target <= 0:
        raise ValueError("目标采集数量必须为正数。")
    create_object_points((args.cols, args.rows), 1.0)


def _open_camera(index: int):
    capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(index)
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"无法打开摄像头索引 {index}。")
    return capture


def _read_image(path: Path):
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取标定图像：{path}")
    return image


def _write_image(path: Path, image) -> None:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise OSError(f"无法编码标定图像：{path}")
    encoded.tofile(path)


def _next_pair_index(output_dir: Path) -> int:
    numbers = []
    for path in output_dir.glob("left_*.png"):
        try:
            numbers.append(int(path.stem.removeprefix("left_")))
        except ValueError:
            continue
    return max(numbers, default=0) + 1


if __name__ == "__main__":
    raise SystemExit(main())
