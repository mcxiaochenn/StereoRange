"""基于官方 YOLOX-Nano ONNX 模型的离线 COCO 物体识别。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from stereorange.analysis import DetectionResult
from stereorange.core import Image

COCO_LABELS_ZH = (
    "人", "自行车", "汽车", "摩托车", "飞机", "公交车", "火车", "卡车",
    "船", "交通灯", "消防栓", "停车标志", "停车计时器", "长椅", "鸟",
    "猫", "狗", "马", "羊", "牛", "大象", "熊", "斑马", "长颈鹿",
    "背包", "雨伞", "手提包", "领带", "行李箱", "飞盘", "滑雪板",
    "单板滑雪", "运动球", "风筝", "棒球棒", "棒球手套", "滑板",
    "冲浪板", "网球拍", "瓶子", "酒杯", "杯子", "叉子", "刀", "勺子",
    "碗", "香蕉", "苹果", "三明治", "橙子", "西兰花", "胡萝卜",
    "热狗", "披萨", "甜甜圈", "蛋糕", "椅子", "沙发", "盆栽", "床",
    "餐桌", "马桶", "电视", "笔记本电脑", "鼠标", "遥控器", "键盘",
    "手机", "微波炉", "烤箱", "烤面包机", "水槽", "冰箱", "书", "时钟",
    "花瓶", "剪刀", "泰迪熊", "吹风机", "牙刷",
)


class YoloXDetector:
    def __init__(
        self,
        model_path: Path,
        confidence: float = 0.40,
        nms_threshold: float = 0.45,
    ) -> None:
        if not model_path.is_file():
            raise ValueError(f"识别模型不存在：{model_path}")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ValueError("缺少 onnxruntime，请重新安装 requirements.txt。") from exc
        self.model_path = model_path
        self.confidence = confidence
        self.nms_threshold = nms_threshold
        self.input_size = (416, 416)
        self._session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self._session.get_inputs()[0].name

    def detect(self, image: Image) -> tuple[DetectionResult, ...]:
        tensor, ratio = _preprocess(image, self.input_size)
        output = self._session.run(None, {self._input_name: tensor})[0]
        predictions = _decode_outputs(output, self.input_size)
        return _postprocess(
            predictions[0],
            ratio,
            image.shape[1],
            image.shape[0],
            self.confidence,
            self.nms_threshold,
        )


def _preprocess(
    image: Image, input_size: tuple[int, int]
) -> tuple[np.ndarray, float]:
    input_height, input_width = input_size
    ratio = min(input_height / image.shape[0], input_width / image.shape[1])
    resized = cv2.resize(
        image,
        (int(image.shape[1] * ratio), int(image.shape[0] * ratio)),
        interpolation=cv2.INTER_LINEAR,
    )
    padded = np.full((input_height, input_width, 3), 114, dtype=np.uint8)
    padded[: resized.shape[0], : resized.shape[1]] = resized
    tensor = padded[:, :, ::-1].transpose(2, 0, 1).astype(np.float32)
    return np.ascontiguousarray(tensor[None]), ratio


def _decode_outputs(outputs: np.ndarray, input_size: tuple[int, int]) -> np.ndarray:
    grids = []
    strides = []
    for stride in (8, 16, 32):
        height, width = input_size[0] // stride, input_size[1] // stride
        yv, xv = np.meshgrid(np.arange(height), np.arange(width), indexing="ij")
        grid = np.stack((xv, yv), axis=2).reshape(1, -1, 2)
        grids.append(grid)
        strides.append(np.full((*grid.shape[:2], 1), stride))
    grid = np.concatenate(grids, axis=1)
    stride_values = np.concatenate(strides, axis=1)
    decoded = outputs.copy()
    decoded[..., :2] = (decoded[..., :2] + grid) * stride_values
    decoded[..., 2:4] = np.exp(decoded[..., 2:4]) * stride_values
    return decoded


def _postprocess(
    predictions: np.ndarray,
    ratio: float,
    image_width: int,
    image_height: int,
    confidence: float,
    nms_threshold: float,
) -> tuple[DetectionResult, ...]:
    boxes = predictions[:, :4]
    scores = predictions[:, 4:5] * predictions[:, 5:]
    class_ids = np.argmax(scores, axis=1)
    confidences = scores[np.arange(scores.shape[0]), class_ids]
    keep = confidences >= confidence
    boxes = boxes[keep]
    class_ids = class_ids[keep]
    confidences = confidences[keep]
    if boxes.size == 0:
        return ()
    xyxy = np.empty_like(boxes)
    xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
    xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
    xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
    xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2
    xyxy /= ratio
    nms_boxes = [
        [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]
        for x1, y1, x2, y2 in xyxy
    ]
    indices = cv2.dnn.NMSBoxes(
        nms_boxes,
        confidences.tolist(),
        confidence,
        nms_threshold,
    )
    results = []
    for index in np.asarray(indices).reshape(-1):
        x1, y1, x2, y2 = xyxy[index]
        class_id = int(class_ids[index])
        results.append(
            DetectionResult(
                class_id=class_id,
                label=COCO_LABELS_ZH[class_id],
                confidence=float(confidences[index]),
                bbox=(
                    max(0, int(x1)),
                    max(0, int(y1)),
                    min(image_width, int(x2)),
                    min(image_height, int(y2)),
                ),
            )
        )
    return tuple(results)
