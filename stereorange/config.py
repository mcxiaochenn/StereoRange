"""StereoRange 当前阶段的运行参数。"""

from pathlib import Path

# TODO(标定): 以下数值只是让实时流程先跑起来的占位参数。
# 完成真实双目标定后，应使用标定得到的焦距（像素）和左右相机基线（米）替换。
# 在替换前，实时模式显示的距离只能用于流程演示，不能作为实际测量结果。
DEFAULT_FOCAL_PX = 700.0
DEFAULT_BASELINE_M = 0.12

DEFAULT_STEREO_CAMERA_INDEX = 0
DEFAULT_LEFT_CAMERA_INDEX = 0
DEFAULT_RIGHT_CAMERA_INDEX = 1
DEFAULT_FRAME_WIDTH = 640
DEFAULT_FRAME_HEIGHT = 480
DEFAULT_STEREO_FRAME_WIDTH = 640
DEFAULT_STEREO_FRAME_HEIGHT = 240
DEFAULT_STEREO_FRAME_FPS = 30
DEFAULT_STEREO_FRAME_CODEC = "MJPG"
DEFAULT_CALIBRATION_PATH = Path("private-data/calibration.npz")
DEFAULT_MODEL_PATH = Path("private-data/models/yolox_nano.onnx")
