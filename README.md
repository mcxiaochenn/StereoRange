# StereoRange

基于双目视觉视差原理的任意表面测距系统，计划使用 Python 实现。

## 项目简介

StereoRange 旨在通过双目相机获取同一场景的左右视图，利用对应点之间的视差估算深度，从而实现对任意表面的非接触式距离测量。

对于完成标定并校正后的平行双目相机，目标深度可由下式估算：

```text
Z = fB / d
```

其中：

- `Z`：目标点到相机的深度；
- `f`：相机焦距；
- `B`：左右相机光心之间的基线距离；
- `d`：同一目标点在左右图像中的视差。

## 当前功能

- 单设备横向拼接双目画面实时拆分，并持续刷新左右图、视差图和深度图；
- 可选使用两个独立摄像头作为左右输入；
- 无需相机即可运行的确定性模拟双目演示；
- 使用 OpenCV StereoSGBM 计算浮点视差图；
- 根据焦距、基线和视差生成深度图；
- OpenCV 窗口展示左右图、视差图和深度图；
- 点击深度图，以 `7 × 7` 邻域中位数查询模拟距离；
- 支持传入已校正的本地左右图；
- 可选保存原始数组、预览图和 JSON 摘要；
- 支持无窗口运行，便于自动化验证。

## 环境要求

- Python 3.10 或 3.11
- OpenCV
- NumPy

建议使用虚拟环境安装依赖：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

运行测试需要额外安装开发依赖：

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## 快速开始

默认读取索引 `0` 的双目摄像头，并将横向拼接画面等分为左右视图：

```powershell
python main.py
```

如需指定其他双目摄像头索引：

```powershell
python main.py --stereo-camera 1
```

程序会持续刷新左右画面、视差图和深度图。点击深度图可查看当前估算距离，按 `Q` 或 `Esc` 退出。

若使用两个独立摄像头，则显式启用双设备模式：

```powershell
python main.py --dual-camera --left-camera 0 --right-camera 1
```

当前实时模式暂时使用 `stereorange/config.py` 中的默认焦距 `700 px` 和默认基线 `0.12 m`。这两个值已用 `TODO(标定)` 注释明确标记，后续必须替换为真实标定结果。也可以在启动时临时覆盖：

```powershell
python main.py --focal-px 700 --baseline-m 0.12
```

不连接摄像头，启动内置模拟演示：

```powershell
python main.py --demo
```

以无窗口模式运行模拟演示并保存结果：

```powershell
python main.py --demo --no-gui --output-dir output
```

实时模式必须显示窗口，不能与 `--no-gui` 同时使用。实时模式指定 `--output-dir` 时，会在退出时保存最后一帧的视差、深度和摘要。

处理已完成立体校正的本地左右图：

```powershell
python main.py --left left.png --right right.png
```

同时提供焦距和基线后，可以计算深度：

```powershell
python main.py --left left.png --right right.png --focal-px 700 --baseline-m 0.12
```

`--focal-px` 的单位是像素，`--baseline-m` 的单位是米。这两个参数必须同时提供且大于零。本地图像未提供这两个参数时，程序仍会生成视差图，但会明确提示深度不可用。

## 输出文件

指定 `--output-dir` 后会生成：

- `disparity.npy`：浮点视差数组；
- `disparity.png`：彩色视差预览；
- `depth.npy`：以米为单位的浮点深度数组，仅在深度参数可用时生成；
- `depth.png`：彩色深度预览，仅在深度参数可用时生成；
- `result.json`：输入模式、图像尺寸、相机参数和有效视差统计。

## 当前限制

- 实时模式的默认焦距和基线是占位值，不能替代真实双目标定；
- 默认要求单设备输出可横向等分的左右画面；
- 双设备模式只是依次读取两个摄像头，不包含硬件级帧同步；
- 实时画面尚未根据相机内参、畸变参数和双目外参进行校正；
- 本地图像必须已经完成立体校正，程序不会自动校正未标定图像；
- 当前版本未实现标定、点云生成和测距精度优化；
- 当前目标是跑通数据流和交互，不代表已经具备实际工程测距精度。

## 项目状态

基础可运行版本已完成，后续仍需结合实际双目设备进行标定、采集和精度验证。
