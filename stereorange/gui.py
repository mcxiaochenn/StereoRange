"""StereoRange 比赛演示用 PySide6 单窗口界面。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from stereorange import PROJECT_CREDIT
from stereorange.analysis import PointKind, ProcessedFrame, TrackingMode
from stereorange.calibration import StereoRectifier, load_calibration, split_side_by_side
from stereorange.camera import configure_stereo_capture
from stereorange.config import DEFAULT_BASELINE_M, DEFAULT_FOCAL_PX
from stereorange.detection import YoloXDetector
from stereorange.pipeline import FrameProcessor

VIEW_NAMES = {
    "left": "智能测距",
    "right": "右相机",
    "disparity": "视差图",
    "depth": "深度图",
}
POINT_COLORS = {
    "nearest": QColor("#ff694a"),
    "center": QColor("#36d4d9"),
    "farthest": QColor("#8f7cff"),
}


class ImagePanel(QLabel):
    clicked = Signal(str)

    def __init__(self, key: str, title: str) -> None:
        super().__init__()
        self.key = key
        self.title = title
        self._pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(180, 120)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.setText(title)
        self.setProperty("imagePanel", True)

    def set_image(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self._refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)

    def _refresh(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setText(self.title)
            return
        self.setText("")
        self.setPixmap(
            self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class StatusBadge(QLabel):
    def __init__(self, label: str) -> None:
        super().__init__(f"{label} · 等待")
        self.label = label
        self.set_state("等待", "neutral")

    def set_state(self, text: str, level: str) -> None:
        colors = {
            "ok": ("#14392f", "#64e0b1"),
            "warn": ("#463616", "#ffcc66"),
            "error": ("#481f25", "#ff7d8b"),
            "neutral": ("#28303b", "#aab6c5"),
        }
        background, foreground = colors[level]
        self.setText(f"{self.label} · {text}")
        self.setStyleSheet(
            f"background:{background}; color:{foreground}; border-radius:10px;"
            "padding:5px 10px; font-weight:600;"
        )


class MetricCard(QFrame):
    def __init__(self, title: str, color: str) -> None:
        super().__init__()
        self.setProperty("metricCard", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        self.title = QLabel(title)
        self.title.setStyleSheet(f"color:{color}; font-weight:700;")
        self.value = QLabel("--")
        self.value.setStyleSheet("font-size:26px; font-weight:800; color:#f4f7fb;")
        self.source = QLabel("暂无有效数据")
        self.source.setStyleSheet("color:#8492a6;")
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.source)

    def update_value(self, distance: float | None, source: str = "") -> None:
        self.value.setText("--" if distance is None else f"{distance:.3f} m")
        self.source.setText(source or "暂无有效数据")


class VideoWorker(QThread):
    frame_ready = Signal(object)
    system_state = Signal(object)
    message = Signal(str, str)

    def __init__(
        self,
        camera_index: int,
        calibration_path: Path,
        model_path: Path,
    ) -> None:
        super().__init__()
        self.camera_index = camera_index
        self.calibration_path = calibration_path
        self.model_path = model_path
        self._stop_event = Event()
        self._paused = Event()
        self._reconnect = Event()
        self._processor: FrameProcessor | None = None
        self._settings = (0.2, 3.0, 0.4, "scene")
        self._state: dict[str, Any] = {
            "camera": False,
            "calibration": False,
            "model": False,
            "rms": None,
        }

    def stop(self) -> None:
        self._stop_event.set()
        self._paused.clear()
        self._reconnect.set()

    def set_paused(self, paused: bool) -> None:
        self._paused.set() if paused else self._paused.clear()

    def reconnect(self) -> None:
        self._reconnect.set()

    def update_settings(
        self,
        minimum_m: float,
        maximum_m: float,
        confidence: float,
        mode: TrackingMode,
    ) -> None:
        self._settings = (minimum_m, maximum_m, confidence, mode)
        if self._processor is not None:
            self._processor.update_settings(*self._settings)

    def run(self) -> None:
        rectifier = None
        focal_px, baseline_m = DEFAULT_FOCAL_PX, DEFAULT_BASELINE_M
        try:
            calibration = load_calibration(self.calibration_path)
            rectifier = StereoRectifier(calibration)
            focal_px, baseline_m = calibration.focal_px, calibration.baseline_m
            self._state.update(
                calibration=True,
                rms=calibration.rms_stereo,
                calibration_path=str(self.calibration_path),
            )
        except (OSError, ValueError) as exc:
            self.message.emit("标定参数不可用", str(exc))
        detector = None
        try:
            detector = YoloXDetector(self.model_path)
            self._state.update(model=True, model_path=str(self.model_path))
        except ValueError as exc:
            self.message.emit("物体识别不可用", str(exc))
        self._processor = FrameProcessor(
            focal_px,
            baseline_m,
            rectifier=rectifier,
            detector=detector,
        )
        self._processor.update_settings(*self._settings)
        self.system_state.emit(dict(self._state))

        capture = None
        while not self._stop_event.is_set():
            if self._reconnect.is_set() and capture is not None:
                capture.release()
                capture = None
                self._reconnect.clear()
            if capture is None:
                capture = _open_camera(self.camera_index)
                if capture is None:
                    self._state["camera"] = False
                    self.system_state.emit(dict(self._state))
                    self.message.emit(
                        "摄像头连接失败",
                        f"无法打开索引 {self.camera_index}，程序将在 1 秒后重试。",
                    )
                    self.msleep(1000)
                    continue
                self._state["camera"] = True
                self.system_state.emit(dict(self._state))
            if self._paused.is_set():
                self.msleep(40)
                continue
            ok, frame = capture.read()
            if not ok or frame is None:
                capture.release()
                capture = None
                self._state["camera"] = False
                self.system_state.emit(dict(self._state))
                self.message.emit("摄像头已断开", "读取画面失败，正在自动重连。")
                continue
            size = f"{frame.shape[1]}×{frame.shape[0]}"
            if self._state.get("camera_size") != size:
                self._state["camera_size"] = size
                self.system_state.emit(dict(self._state))
            try:
                left, right = split_side_by_side(frame)
                result = self._processor.process(left, right)
                self.frame_ready.emit(result)
            except (cv2.error, ValueError) as exc:
                self.message.emit("处理失败", str(exc))
                self.msleep(100)
        if capture is not None:
            capture.release()


class StereoRangeWindow(QMainWindow):
    def __init__(
        self,
        camera_index: int,
        calibration_path: Path,
        model_path: Path,
        start_worker: bool = True,
    ) -> None:
        super().__init__()
        self.setWindowTitle("StereoRange · 智能双目测距")
        self.setMinimumSize(1024, 600)
        self.resize(1280, 760)
        self.settings = QSettings("StereoRange", "CompetitionUI")
        self._main_key = "left"
        self._pixmaps: dict[str, QPixmap] = {}
        self._last_result: ProcessedFrame | None = None
        self._paused = False
        self._camera_index = camera_index
        self._calibration_path = calibration_path
        self._model_path = model_path
        self._worker = VideoWorker(camera_index, calibration_path, model_path)
        self._build_ui()
        self._restore_settings()
        self._connect_worker()
        if start_worker:
            self._worker.start()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(16, 12, 16, 14)
        page.setSpacing(10)

        header = QHBoxLayout()
        brand = QLabel("STEREORANGE")
        brand.setStyleSheet(
            "font-size:20px; font-weight:900; letter-spacing:2px; color:#f5f7fa;"
        )
        subtitle = QLabel("平湖技师学院 · 智能双目测距控制台")
        subtitle.setStyleSheet("color:#758398; margin-left:8px;")
        header.addWidget(brand)
        header.addWidget(subtitle)
        header.addStretch()
        self.camera_badge = StatusBadge("相机")
        self.calibration_badge = StatusBadge("标定")
        self.model_badge = StatusBadge("识别")
        self.fps_badge = StatusBadge("性能")
        for badge in (
            self.camera_badge,
            self.calibration_badge,
            self.model_badge,
            self.fps_badge,
        ):
            header.addWidget(badge)
        page.addLayout(header)

        self.warning_banner = QLabel("系统初始化中…")
        self.warning_banner.setWordWrap(True)
        self.warning_banner.setStyleSheet(
            "background:#382126; color:#ff9ca7; border:1px solid #713641;"
            "border-radius:7px; padding:8px 12px; font-weight:600;"
        )
        page.addWidget(self.warning_banner)

        content = QHBoxLayout()
        content.setSpacing(12)
        visual = QVBoxLayout()
        self.main_panel = ImagePanel("left", VIEW_NAMES["left"])
        self.main_panel.setMinimumSize(640, 420)
        self.main_panel.clicked.connect(self._select_view)
        visual.addWidget(self.main_panel, 1)
        self.thumbnail_row = QHBoxLayout()
        self.thumbnail_panels = []
        for key in ("right", "disparity", "depth"):
            panel = ImagePanel(key, VIEW_NAMES[key])
            panel.setMaximumHeight(160)
            panel.clicked.connect(self._select_view)
            self.thumbnail_panels.append(panel)
            self.thumbnail_row.addWidget(panel)
        visual.addLayout(self.thumbnail_row)
        content.addLayout(visual, 1)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(318)
        controls = QVBoxLayout(sidebar)
        controls.setContentsMargins(14, 14, 14, 14)
        controls.setSpacing(10)

        action_grid = QGridLayout()
        self.pause_button = QPushButton("暂停")
        self.pause_button.clicked.connect(self._toggle_pause)
        self.retry_button = QPushButton("重试连接")
        self.retry_button.clicked.connect(self._restart_worker)
        screenshot = QPushButton("保存截图")
        screenshot.clicked.connect(self._save_screenshot)
        fullscreen = QPushButton("全屏")
        fullscreen.clicked.connect(self._toggle_fullscreen)
        help_button = QPushButton("使用说明")
        help_button.clicked.connect(self._show_help)
        exit_button = QPushButton("退出")
        exit_button.clicked.connect(self.close)
        for index, button in enumerate(
            (self.pause_button, self.retry_button, screenshot, fullscreen, help_button, exit_button)
        ):
            action_grid.addWidget(button, index // 2, index % 2)
        controls.addLayout(action_grid)

        controls.addWidget(_section_label("测距模式"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("全场景可靠深度", "scene")
        self.mode_combo.addItem("仅识别物体", "objects")
        self.mode_combo.currentIndexChanged.connect(self._apply_settings)
        controls.addWidget(self.mode_combo)

        self.metrics = {
            "nearest": MetricCard("最近点", "#ff8066"),
            "center": MetricCard("中心点", "#4ee2e6"),
            "farthest": MetricCard("最远点", "#a79aff"),
        }
        for metric in self.metrics.values():
            controls.addWidget(metric)

        controls.addWidget(_section_label("识别物体"))
        self.object_list = QListWidget()
        self.object_list.setMinimumHeight(95)
        controls.addWidget(self.object_list, 1)

        controls.addWidget(_section_label("可靠范围与阈值"))
        settings_grid = QGridLayout()
        self.minimum_spin = _spin_box(0.05, 20.0, 0.20, " m")
        self.maximum_spin = _spin_box(0.10, 50.0, 3.00, " m")
        self.confidence_spin = _spin_box(0.05, 0.95, 0.40, "")
        settings_grid.addWidget(QLabel("最近"), 0, 0)
        settings_grid.addWidget(self.minimum_spin, 0, 1)
        settings_grid.addWidget(QLabel("最远"), 1, 0)
        settings_grid.addWidget(self.maximum_spin, 1, 1)
        settings_grid.addWidget(QLabel("置信度"), 2, 0)
        settings_grid.addWidget(self.confidence_spin, 2, 1)
        controls.addLayout(settings_grid)
        for spin in (self.minimum_spin, self.maximum_spin, self.confidence_spin):
            spin.valueChanged.connect(self._apply_settings)
        controls.addWidget(_section_label("显示图层"))
        layer_row = QHBoxLayout()
        self.detections_checkbox = QCheckBox("物体框")
        self.points_checkbox = QCheckBox("测距点")
        self.detections_checkbox.setChecked(True)
        self.points_checkbox.setChecked(True)
        self.detections_checkbox.toggled.connect(self._apply_layers)
        self.points_checkbox.toggled.connect(self._apply_layers)
        layer_row.addWidget(self.detections_checkbox)
        layer_row.addWidget(self.points_checkbox)
        controls.addLayout(layer_row)
        reset = QPushButton("恢复默认设置")
        reset.clicked.connect(self._reset_settings)
        controls.addWidget(reset)
        content.addWidget(sidebar)
        page.addLayout(content, 1)

        credit = QLabel(PROJECT_CREDIT)
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit.setStyleSheet("color:#607086; font-size:10px; letter-spacing:1px;")
        page.addWidget(credit)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("正在加载标定参数、识别模型和摄像头…")
        self.setStyleSheet(_stylesheet())

    def _connect_worker(self) -> None:
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.system_state.connect(self._on_system_state)
        self._worker.message.connect(self._on_message)

    def _on_frame(self, result: ProcessedFrame) -> None:
        self._last_result = result
        self._pixmaps = {
            "left": _frame_pixmap(
                result.left,
                result,
                self.detections_checkbox.isChecked(),
                self.points_checkbox.isChecked(),
            ),
            "right": _frame_pixmap(result.right),
            "disparity": _frame_pixmap(result.disparity_preview),
            "depth": _frame_pixmap(result.depth_preview),
        }
        self._refresh_panels()
        self.fps_badge.set_state(f"{result.fps:.1f} FPS", "ok" if result.fps >= 15 else "warn")
        for kind, card in self.metrics.items():
            point = result.points.get(kind)
            card.update_value(
                point.distance_m if point else None,
                point.source if point else "",
            )
        self.object_list.clear()
        for detection in result.detections:
            distance = (
                f"{detection.distance_m:.3f} m"
                if detection.distance_m is not None
                else "距离不可用"
            )
            self.object_list.addItem(
                f"{detection.label}  {detection.confidence:.0%}  ·  {distance}"
            )
        if not result.detections:
            self.object_list.addItem("未识别到常见物体")

    def _on_system_state(self, state: dict[str, Any]) -> None:
        self.camera_badge.set_state(
            (
                f"已连接 {state.get('camera_size', '')}".strip()
                if state["camera"]
                else "未连接"
            ),
            "ok" if state["camera"] else "error",
        )
        self.model_badge.set_state(
            "离线模型" if state["model"] else "不可用",
            "ok" if state["model"] else "error",
        )
        rms = state.get("rms")
        if state["calibration"] and rms is not None:
            if rms <= 1:
                level, text = "ok", f"优秀 {rms:.2f}px"
                banner = "标定质量良好，可进行实物精度验证。"
                banner_style = (
                    "background:#17352d; color:#72e2b8; border:1px solid #28604f;"
                )
            elif rms <= 2:
                level, text = "warn", f"一般 {rms:.2f}px"
                banner = "标定误差偏高，距离结果需要复核。"
                banner_style = (
                    "background:#3a301b; color:#ffd175; border:1px solid #705c2c;"
                )
            else:
                level, text = "error", f"较差 {rms:.2f}px"
                banner = (
                    f"标定 RMS 为 {rms:.2f} px，当前距离仅供演示参考；"
                    "正式比赛前请重新标定。"
                )
                banner_style = (
                    "background:#382126; color:#ff9ca7; border:1px solid #713641;"
                )
            self.calibration_badge.set_state(text, level)
            self.warning_banner.setText(banner)
            self.warning_banner.setStyleSheet(
                banner_style + "border-radius:7px; padding:8px 12px; font-weight:600;"
            )
        else:
            self.calibration_badge.set_state("占位参数", "error")
            self.warning_banner.setText("未加载实机标定参数，距离仅供流程演示。")

    def _on_message(self, title: str, message: str) -> None:
        self.statusBar().showMessage(f"{title}：{message}", 6000)

    def _select_view(self, key: str) -> None:
        if key != self._main_key:
            self._main_key = key
            self._refresh_panels()

    def _refresh_panels(self) -> None:
        self.main_panel.key = self._main_key
        self.main_panel.title = VIEW_NAMES[self._main_key]
        self.main_panel.set_image(self._pixmaps.get(self._main_key))
        other_keys = [key for key in VIEW_NAMES if key != self._main_key]
        for panel, key in zip(self.thumbnail_panels, other_keys):
            panel.key = key
            panel.title = VIEW_NAMES[key]
            panel.setToolTip(f"点击放大：{VIEW_NAMES[key]}")
            panel.set_image(self._pixmaps.get(key))

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self._worker.set_paused(self._paused)
        self.pause_button.setText("继续" if self._paused else "暂停")
        self.statusBar().showMessage("画面已暂停" if self._paused else "测距已继续")

    def _restart_worker(self) -> None:
        self.statusBar().showMessage("正在重新加载标定、模型并连接摄像头…")
        self._worker.stop()
        if self._worker.isRunning():
            self._worker.wait(3000)
        self._worker = VideoWorker(
            self._camera_index,
            self._calibration_path,
            self._model_path,
        )
        self._connect_worker()
        self._paused = False
        self.pause_button.setText("暂停")
        self._apply_settings()
        self._worker.start()

    def _apply_settings(self, *_args: object) -> None:
        minimum = self.minimum_spin.value()
        maximum = self.maximum_spin.value()
        if maximum <= minimum:
            maximum = min(50.0, minimum + 0.1)
            self.maximum_spin.blockSignals(True)
            self.maximum_spin.setValue(maximum)
            self.maximum_spin.blockSignals(False)
        mode = self.mode_combo.currentData()
        confidence = self.confidence_spin.value()
        self._worker.update_settings(minimum, maximum, confidence, mode)
        self.settings.setValue("minimum_m", minimum)
        self.settings.setValue("maximum_m", maximum)
        self.settings.setValue("confidence", confidence)
        self.settings.setValue("tracking_mode", mode)

    def _restore_settings(self) -> None:
        self.minimum_spin.setValue(float(self.settings.value("minimum_m", 0.2)))
        self.maximum_spin.setValue(float(self.settings.value("maximum_m", 3.0)))
        self.confidence_spin.setValue(float(self.settings.value("confidence", 0.4)))
        self.detections_checkbox.setChecked(
            self.settings.value("show_detections", True, type=bool)
        )
        self.points_checkbox.setChecked(
            self.settings.value("show_points", True, type=bool)
        )
        mode = self.settings.value("tracking_mode", "scene")
        self.mode_combo.setCurrentIndex(1 if mode == "objects" else 0)
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self._apply_settings()

    def _reset_settings(self) -> None:
        self.minimum_spin.setValue(0.2)
        self.maximum_spin.setValue(3.0)
        self.confidence_spin.setValue(0.4)
        self.mode_combo.setCurrentIndex(0)
        self.detections_checkbox.setChecked(True)
        self.points_checkbox.setChecked(True)
        self._apply_settings()

    def _apply_layers(self, *_args: object) -> None:
        self.settings.setValue(
            "show_detections", self.detections_checkbox.isChecked()
        )
        self.settings.setValue("show_points", self.points_checkbox.isChecked())
        if self._last_result is not None:
            self._on_frame(self._last_result)

    def _save_screenshot(self) -> None:
        pixmap = self._pixmaps.get(self._main_key)
        if pixmap is None:
            self.statusBar().showMessage("当前没有可保存的画面。", 3000)
            return
        output_dir = Path("screenshots")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"StereoRange_{datetime.now():%Y%m%d_%H%M%S}.png"
        if pixmap.save(str(path), "PNG"):
            self.statusBar().showMessage(f"截图已保存：{path.resolve()}", 6000)
        else:
            self.statusBar().showMessage("截图保存失败。", 4000)

    def _toggle_fullscreen(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "StereoRange 使用说明",
            "1. 将物体放入左右镜头共同可见的区域。\n"
            "2. 主画面会显示类别、置信度和物体距离。\n"
            "3. 可切换全场景或仅识别物体的最近/最远点。\n"
            "4. 点击下方缩略图可切换主视图，F11 可全屏。\n\n"
            "当前标定 RMS 偏高时，距离只能作为演示参考。\n\n"
            f"作者署名：{PROJECT_CREDIT}",
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F11:
            self._toggle_fullscreen()
            return
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self._worker.stop()
        if self._worker.isRunning():
            self._worker.wait(3000)
        event.accept()


def run_gui(
    camera_index: int,
    calibration_path: Path,
    model_path: Path,
) -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("StereoRange")
    app.setOrganizationName("StereoRange")
    window = StereoRangeWindow(camera_index, calibration_path, model_path)
    window.show()
    return app.exec()


def _open_camera(index: int):
    capture = cv2.VideoCapture(index, cv2.CAP_MSMF)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(index)
    if not capture.isOpened():
        capture.release()
        return None
    configure_stereo_capture(capture)
    return capture


def _frame_pixmap(
    image: np.ndarray,
    result: ProcessedFrame | None = None,
    show_detections: bool = True,
    show_points: bool = True,
) -> QPixmap:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    qimage = QImage(
        rgb.data,
        width,
        height,
        int(rgb.strides[0]),
        QImage.Format.Format_RGB888,
    ).copy()
    if result is not None:
        _paint_overlays(qimage, result, show_detections, show_points)
    return QPixmap.fromImage(qimage)


def _paint_overlays(
    image: QImage,
    result: ProcessedFrame,
    show_detections: bool,
    show_points: bool,
) -> None:
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Microsoft YaHei UI", 8)
    font.setBold(True)
    painter.setFont(font)
    for detection in result.detections if show_detections else ():
        x1, y1, x2, y2 = detection.bbox
        color = QColor.fromHsv((detection.class_id * 47) % 360, 170, 245)
        painter.setPen(QPen(color, 2))
        painter.drawRect(x1, y1, max(1, x2 - x1), max(1, y2 - y1))
        distance = (
            f"{detection.distance_m:.2f}m"
            if detection.distance_m is not None
            else "--"
        )
        text = f"{detection.label} {detection.confidence:.0%} | {distance}"
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text) + 8
        text_y = max(12, y1)
        painter.fillRect(x1, text_y - 12, text_width, 14, QColor(9, 14, 20, 210))
        painter.setPen(color)
        painter.drawText(x1 + 4, text_y - 1, text)
    labels = {"nearest": "最近", "center": "中心", "farthest": "最远"}
    for kind, point in result.points.items() if show_points else ():
        if not point.valid:
            continue
        assert point.x is not None and point.y is not None and point.distance_m is not None
        color = POINT_COLORS[kind]
        painter.setPen(QPen(color, 2))
        painter.drawEllipse(point.x - 5, point.y - 5, 10, 10)
        painter.drawLine(point.x - 9, point.y, point.x + 9, point.y)
        painter.drawLine(point.x, point.y - 9, point.x, point.y + 9)
        text = f"{labels[kind]} {point.distance_m:.2f}m"
        painter.fillRect(point.x + 7, point.y - 12, 72, 15, QColor(9, 14, 20, 215))
        painter.setPen(color)
        painter.drawText(point.x + 10, point.y, text)
    painter.end()


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        "color:#8492a6; font-size:11px; font-weight:700; margin-top:4px;"
    )
    return label


def _spin_box(minimum: float, maximum: float, value: float, suffix: str) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(2)
    spin.setSingleStep(0.05)
    spin.setValue(value)
    spin.setSuffix(suffix)
    return spin


def _stylesheet() -> str:
    return """
    QMainWindow, QWidget {
        background: #10151c;
        color: #dbe3ed;
        font-family: "Microsoft YaHei UI";
        font-size: 12px;
    }
    QLabel[imagePanel="true"] {
        background: #080c11;
        border: 1px solid #293342;
        border-radius: 8px;
        color: #607086;
    }
    QFrame#sidebar {
        background: #171e27;
        border: 1px solid #2a3544;
        border-radius: 10px;
    }
    QFrame[metricCard="true"] {
        background: #202936;
        border: 1px solid #313e50;
        border-radius: 8px;
    }
    QPushButton {
        background: #273241;
        border: 1px solid #3a485b;
        border-radius: 6px;
        padding: 8px 7px;
        font-weight: 600;
    }
    QPushButton:hover { background: #334154; border-color: #52657d; }
    QPushButton:pressed { background: #1d2631; }
    QComboBox, QDoubleSpinBox, QListWidget {
        background: #111820;
        border: 1px solid #334052;
        border-radius: 6px;
        padding: 6px;
        selection-background-color: #315b69;
    }
    QListWidget { color: #cbd5e2; }
    QStatusBar { color: #8e9caf; }
    """
