"""将桌面标定导出为 Android/Rust 使用的版本化 JSON。"""

from dataclasses import fields
import json
from pathlib import Path

import numpy as np

from stereorange.calibration import StereoCalibration, load_calibration


def export_mobile_calibration(source: Path, destination: Path) -> None:
    calibration = load_calibration(source)
    result = {"schema_version": 1, "length_unit": "m"}
    for field in fields(StereoCalibration):
        value = getattr(calibration, field.name)
        if isinstance(value, np.ndarray):
            if not np.all(np.isfinite(value)):
                raise ValueError(f"标定字段 {field.name} 包含非有限数值。")
            value = value.tolist()
        result[field.name] = value
    if not np.isfinite(calibration.focal_px) or calibration.focal_px <= 0:
        raise ValueError("标定焦距必须为有限正数。")
    if not np.isfinite(calibration.baseline_m) or calibration.baseline_m <= 0:
        raise ValueError("标定基线必须为有限正数。")
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(encoded + "\n", encoding="utf-8")
