"""StereoRange 命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from stereorange import PROJECT_CREDIT
from stereorange.calibration import (
    StereoCalibration,
    StereoRectifier,
    load_calibration,
)
from stereorange.core import (
    FloatImage,
    Image,
    compute_disparity,
    disparity_to_depth,
    generate_demo_pair,
)
from stereorange.config import (
    DEFAULT_BASELINE_M,
    DEFAULT_CALIBRATION_PATH,
    DEFAULT_FOCAL_PX,
    DEFAULT_LEFT_CAMERA_INDEX,
    DEFAULT_MODEL_PATH,
    DEFAULT_RIGHT_CAMERA_INDEX,
    DEFAULT_STEREO_CAMERA_INDEX,
)
from stereorange.live import run_live_cameras, run_live_stereo_camera
from stereorange.presentation import colorize_values, save_results, show_results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="基于双目视差的基础测距演示。",
        epilog=PROJECT_CREDIT,
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用内置模拟双目图，不连接摄像头",
    )
    parser.add_argument("--left", type=Path, help="已校正的左图路径")
    parser.add_argument("--right", type=Path, help="已校正的右图路径")
    parser.add_argument(
        "--stereo-camera",
        type=int,
        default=DEFAULT_STEREO_CAMERA_INDEX,
        help="横向拼接双目摄像头索引，默认 0",
    )
    parser.add_argument(
        "--dual-camera",
        action="store_true",
        help="改用两个独立摄像头，而不是单设备横向双目画面",
    )
    parser.add_argument(
        "--left-camera",
        type=int,
        default=DEFAULT_LEFT_CAMERA_INDEX,
        help="左摄像头索引，默认 0",
    )
    parser.add_argument(
        "--right-camera",
        type=int,
        default=DEFAULT_RIGHT_CAMERA_INDEX,
        help="右摄像头索引，默认 1",
    )
    parser.add_argument("--focal-px", type=float, help="以像素为单位的焦距")
    parser.add_argument("--baseline-m", type=float, help="以米为单位的双目基线")
    parser.add_argument(
        "--calibration",
        type=Path,
        help="标定参数文件；未指定时自动尝试 private-data/calibration.npz",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="YOLOX-Nano ONNX 模型路径",
    )
    parser.add_argument(
        "--classic-ui",
        action="store_true",
        help="实时模式使用原 OpenCV 多窗口界面",
    )
    parser.add_argument("--output-dir", type=Path, help="可选的结果输出目录")
    parser.add_argument("--no-gui", action="store_true", help="不打开交互窗口")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _validate_args(args)
        if _is_live_mode(args) and not args.classic_ui and not args.dual_camera:
            calibration_path = args.calibration or DEFAULT_CALIBRATION_PATH
            return run_competition_gui(
                args.stereo_camera,
                calibration_path,
                args.model,
            )
        calibration, calibration_path = _select_calibration(args)
        rectifier = StereoRectifier(calibration) if calibration is not None else None
        if _is_live_mode(args):
            focal_px = (
                calibration.focal_px
                if calibration is not None
                else args.focal_px
                if args.focal_px is not None
                else DEFAULT_FOCAL_PX
            )
            baseline_m = (
                calibration.baseline_m
                if calibration is not None
                else args.baseline_m
                if args.baseline_m is not None
                else DEFAULT_BASELINE_M
            )
            if calibration_path is not None:
                print(f"已加载标定文件：{calibration_path.resolve()}")
            if args.dual_camera:
                run_live_cameras(
                    left_index=args.left_camera,
                    right_index=args.right_camera,
                    focal_px=focal_px,
                    baseline_m=baseline_m,
                    output_dir=args.output_dir,
                    rectifier=rectifier,
                    calibration_path=calibration_path,
                )
            else:
                run_live_stereo_camera(
                    camera_index=args.stereo_camera,
                    focal_px=focal_px,
                    baseline_m=baseline_m,
                    output_dir=args.output_dir,
                    rectifier=rectifier,
                    calibration_path=calibration_path,
                )
            return 0

        left, right, input_mode, focal_px, baseline_m = _load_inputs(args)
        if rectifier is not None:
            left, right = rectifier.rectify(left, right)
            focal_px = calibration.focal_px
            baseline_m = calibration.baseline_m
        disparity = compute_disparity(left, right)
        depth = _make_depth(disparity, focal_px, baseline_m)
        disparity_preview = colorize_values(disparity, cv2.COLORMAP_TURBO)
        depth_preview = (
            colorize_values(depth, cv2.COLORMAP_MAGMA) if depth is not None else None
        )
        metadata = _build_metadata(
            input_mode,
            left,
            disparity,
            depth,
            focal_px,
            baseline_m,
            calibration_path,
        )

        _print_summary(metadata)
        if args.output_dir is not None:
            save_results(
                args.output_dir,
                disparity,
                disparity_preview,
                depth,
                depth_preview,
                metadata,
            )
            print(f"结果已保存到：{args.output_dir.resolve()}")
        if not args.no_gui:
            show_results(
                left,
                right,
                disparity,
                disparity_preview,
                depth,
                depth_preview,
            )
        return 0
    except (OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


def run_competition_gui(
    camera_index: int,
    calibration_path: Path,
    model_path: Path,
) -> int:
    """延迟导入 Qt，使演示、测试和经典界面不强制初始化 Qt。"""
    from stereorange.gui import run_gui

    return run_gui(camera_index, calibration_path, model_path)


def _validate_args(args: argparse.Namespace) -> None:
    if args.demo and (args.left is not None or args.right is not None):
        raise ValueError("--demo 不能与本地图像参数同时使用。")
    if args.demo and args.calibration is not None:
        raise ValueError("--demo 不能与 --calibration 同时使用。")
    if args.dual_camera and not _is_live_mode(args):
        raise ValueError("--dual-camera 只能用于实时摄像头模式。")
    if (args.left is None) != (args.right is None):
        raise ValueError("--left 与 --right 必须同时提供。")
    if (args.focal_px is None) != (args.baseline_m is None):
        raise ValueError("--focal-px 与 --baseline-m 必须同时提供。")
    if args.focal_px is not None and args.focal_px <= 0:
        raise ValueError("--focal-px 必须为正数。")
    if args.baseline_m is not None and args.baseline_m <= 0:
        raise ValueError("--baseline-m 必须为正数。")
    if args.calibration is not None and args.focal_px is not None:
        raise ValueError("--calibration 不能与手动焦距和基线参数同时使用。")
    if args.stereo_camera < 0 or args.left_camera < 0 or args.right_camera < 0:
        raise ValueError("摄像头索引不能为负数。")
    if (
        _is_live_mode(args)
        and args.dual_camera
        and args.left_camera == args.right_camera
    ):
        raise ValueError("左右摄像头索引必须不同。")
    if _is_live_mode(args) and args.no_gui:
        raise ValueError("实时摄像头模式不能使用 --no-gui。")


def _is_live_mode(args: argparse.Namespace) -> bool:
    return not args.demo and args.left is None and args.right is None


def _load_inputs(
    args: argparse.Namespace,
) -> tuple[Image, Image, str, float | None, float | None]:
    if args.demo:
        demo = generate_demo_pair()
        focal_px = args.focal_px if args.focal_px is not None else demo.focal_px
        baseline_m = (
            args.baseline_m if args.baseline_m is not None else demo.baseline_m
        )
        return demo.left, demo.right, "demo", focal_px, baseline_m

    left = _read_image(args.left)
    right = _read_image(args.right)
    if left.shape != right.shape:
        raise ValueError("左右图像尺寸必须一致。")
    return left, right, "files", args.focal_px, args.baseline_m


def _select_calibration(
    args: argparse.Namespace,
) -> tuple[StereoCalibration | None, Path | None]:
    if args.demo or args.focal_px is not None:
        return None, None
    if args.calibration is not None:
        return load_calibration(args.calibration), args.calibration
    if _is_live_mode(args) and DEFAULT_CALIBRATION_PATH.is_file():
        return load_calibration(DEFAULT_CALIBRATION_PATH), DEFAULT_CALIBRATION_PATH
    return None, None


def _read_image(path: Path) -> Image:
    if not path.is_file():
        raise ValueError(f"图像文件不存在：{path}")
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError as exc:
        raise OSError(f"无法读取图像文件：{path}") from exc
    if data.size == 0:
        raise ValueError(f"无法解码图像文件：{path}")
    try:
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    except cv2.error as exc:
        raise ValueError(f"无法解码图像文件：{path}") from exc
    if image is None:
        raise ValueError(f"无法解码图像文件：{path}")
    return image


def _make_depth(
    disparity: FloatImage,
    focal_px: float | None,
    baseline_m: float | None,
) -> FloatImage | None:
    if focal_px is None or baseline_m is None:
        return None
    return disparity_to_depth(disparity, focal_px, baseline_m)


def _build_metadata(
    input_mode: str,
    image: Image,
    disparity: FloatImage,
    depth: FloatImage | None,
    focal_px: float | None,
    baseline_m: float | None,
    calibration_path: Path | None,
) -> dict[str, object]:
    valid_disparity = np.isfinite(disparity) & (disparity > 0)
    return {
        "input_mode": input_mode,
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "focal_px": focal_px,
        "baseline_m": baseline_m,
        "calibration_file": (
            str(calibration_path.resolve()) if calibration_path is not None else None
        ),
        "calibration_placeholder": (
            input_mode != "demo" and calibration_path is None and depth is not None
        ),
        "depth_available": depth is not None,
        "valid_disparity_pixels": int(np.count_nonzero(valid_disparity)),
        "valid_disparity_ratio": float(np.mean(valid_disparity)),
    }


def _print_summary(metadata: dict[str, object]) -> None:
    mode = "内置演示" if metadata["input_mode"] == "demo" else "本地图像"
    print(f"输入模式：{mode}")
    print(f"图像尺寸：{metadata['width']} × {metadata['height']}")
    print(f"有效视差像素：{metadata['valid_disparity_pixels']}")
    if metadata["depth_available"]:
        print("深度可用：可点击深度图查询距离。")
    else:
        print("深度不可用：请同时提供焦距和基线参数。")


if __name__ == "__main__":
    raise SystemExit(main())
