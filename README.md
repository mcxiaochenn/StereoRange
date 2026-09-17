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
- 生成具有准确物理尺寸的 A4 棋盘格 PDF/SVG；
- 从横向拼接双目摄像头采集标定图像并求解双目标定参数；
- 自动加载标定参数，对左右画面完成去畸变和立体校正；
- 支持传入已校正的本地左右图；
- 可选保存原始数组、预览图和 JSON 摘要；
- 支持无窗口运行，便于自动化验证。

## 环境要求

- Python 3.10 或 3.11
- OpenCV
- NumPy
- ReportLab（只用于生成可打印 PDF）

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

## 双目标定

仓库已经包含默认标定板：

- `assets/stereorange_checkerboard_9x6_25mm_a4.pdf`：推荐直接打印；
- `assets/stereorange_checkerboard_9x6_25mm_a4.svg`：需要重新排版时使用。

它是 A4 横向、`9 × 6` 个内角点、`25 mm` 方格，对应 `10 × 7` 个黑白方格。商家所说的“90° 无畸变”只说明镜头设计目标，本项目仍按普通针孔相机模型从实拍图片估计畸变参数，不将畸变强制设为零。

### 1. 打印并准备标定板

1. 用 PDF 阅读器打开上述 PDF。
2. 选择 A4、横向，缩放设为“实际大小”或 `100%`。
3. 关闭“适合页面”“缩小超大页面”等自动缩放选项。
4. 打印后用直尺测量一个方格边长，应为 `25 mm`。
5. 将纸张平整粘贴到硬质平板上，不能卷曲或产生波浪。

如果实测不是 `25 mm`，求解时必须把 `--square-mm` 改成实测值。方格尺寸误差会按相同比例传递到基线和测距结果。

需要重新生成图案时运行：

```powershell
python calibrate.py pattern --output-dir assets
```

### 2. 采集标定图像

连接当前横向拼接双目摄像头后运行：

```powershell
python calibrate.py capture --camera 0 --target 25
```

窗口中左右两侧都显示角点连线并出现 `READY` 后，按空格保存一组；按 `Q` 或 `Esc` 结束。图像默认保存到 `calibration/images`。

建议采集 `25～30` 组，过程中保持相机本体和左右镜头相对位置不变，并让标定板：

- 分别出现在画面中央、四角和边缘；
- 有近、中、远不同距离，但始终让两侧都看到完整棋盘；
- 绕水平轴、垂直轴做不同角度倾斜；
- 清晰、无强反光、无运动模糊；
- 每次姿态有明显变化，不连续保存几乎相同的画面。

### 3. 求解标定参数

确认打印方格实测为 `25 mm` 后运行：

```powershell
python calibrate.py solve --square-mm 25
```

程序只使用左右图都成功识别全部 `9 × 6` 内角点的图像对，至少需要 10 组。结果默认写入：

```text
calibration/calibration.npz
```

终端会显示左右相机和双目标定的 RMS、校正后焦距与基线。RMS 越低通常越好；若结果明显偏大，应删除模糊、反光或姿态重复的图像后重新采集。标定文件与采集图片属于具体设备数据，已被 `.gitignore` 忽略。

### 4. 使用标定结果

默认启动命令会自动加载 `calibration/calibration.npz`：

```powershell
python main.py
```

也可以显式指定其他标定文件：

```powershell
python main.py --calibration path\to\calibration.npz
```

程序会先对左右画面去畸变并做立体校正，再计算视差和深度。标定分辨率必须与每侧实时画面的分辨率一致；当前相机总画面为 `640 × 240` 时，每侧标定分辨率应为 `320 × 240`。

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

如果默认标定文件尚不存在，实时模式会退回 `stereorange/config.py` 中的占位焦距 `700 px` 和占位基线 `0.12 m`，并在终端明确警告。占位值只用于跑通流程。也可以临时覆盖：

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

处理已经完成立体校正的本地左右图：

```powershell
python main.py --left left.png --right right.png
```

如果本地左右图是标定时分辨率一致的原始图，可显式指定标定文件，让程序先完成校正：

```powershell
python main.py --left left.png --right right.png --calibration calibration\calibration.npz
```

同时提供焦距和基线后，可以计算深度：

```powershell
python main.py --left left.png --right right.png --focal-px 700 --baseline-m 0.12
```

`--focal-px` 的单位是像素，`--baseline-m` 的单位是米。这两个参数必须同时提供且大于零，且不能与 `--calibration` 同时使用。本地图像既没有可用标定文件也未提供这两个参数时，程序仍会生成视差图，但会明确提示深度不可用。

## 输出文件

指定 `--output-dir` 后会生成：

- `disparity.npy`：浮点视差数组；
- `disparity.png`：彩色视差预览；
- `depth.npy`：以米为单位的浮点深度数组，仅在深度参数可用时生成；
- `depth.png`：彩色深度预览，仅在深度参数可用时生成；
- `result.json`：输入模式、图像尺寸、相机参数和有效视差统计。

## 当前限制

- 不存在标定文件时，实时模式的默认焦距和基线仍是占位值；
- 默认要求单设备输出可横向等分的左右画面；
- 双设备模式只是依次读取两个摄像头，不包含硬件级帧同步；
- 标定结果只适用于标定时未改变镜头相对位置和分辨率的同一套设备；
- 当前使用普通针孔相机模型，不是鱼眼模型；若实拍呈现明显鱼眼畸变，需要另行改用 OpenCV fisheye 模型；
- 当前版本未实现点云生成、硬件同步和测距精度优化；
- 当前目标是跑通数据流和交互，不代表已经具备实际工程测距精度。

## 项目状态

基础可运行版本及标定流程已完成，仍需使用实际设备采集图像、生成设备专属标定文件并做实物距离验证。
