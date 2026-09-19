# StereoRange Android

Flutter Material 3 中文界面 + Rust 测距核心。Android 13（API 33）及以上，ARM64 手机，通过 OTG 连接横向拼接 UVC 双目相机。总分辨率固定 640×240、单侧 320×240，请求 30 FPS。Python 桌面版保持独立。

平湖技师学院 · 陆逸尘（辰渊尘 ChenDusk · @mcxiaochenn）· 周璟雯 · 胡乐毅 · 指导教师 张梁

## 手机操作

1. 安装本地生成的 APK；系统询问时，允许本次 APK 安装来源。
2. 插入 OTG 和双目相机，打开 StereoRange，允许相机权限和 USB 设备访问。
3. 资源和设备可用时自动开始。首次授权或连接失败，可点“连接相机 / 重新连接”。无相机时点“演示模式”。
4. 测距页显示左图与识别框；可切换右图、视差、深度，点图查询 7×7 邻域中位距离。右图不叠加左图坐标的识别框，也不提供点击测距。
5. “全场景 / 仅识别物体”只影响最近和最远点，中心点始终使用中心 15×15 邻域。物体模式没有可测物体时，最近和最远会清空。
6. “设备”页导入标定 JSON；“设置”页调整可靠范围、置信度、图层和明暗主题。截图通过系统文件选择器保存，不需要整个存储空间的权限。
7. 暂停、断连、切后台停止采集并清空距离；回到前台尝试恢复之前的采集。手机不做标定求解。

模拟图及其虚拟焦距/基线只验证流程。无匹配标定时可以看图和识别，但不输出物理距离。标定 RMS >2 px 显示红色/文字告警；正式物距以实测与匹配标定为准。

## 标定导出

在仓库根目录、原 Python 环境中执行：

```powershell
.\.venv\Scripts\python.exe calibrate.py export-mobile --input private-data/calibration.npz --output private-data/calibration-mobile.json
```

把 JSON 传到手机，从“设备 → 导入标定 JSON”选择。格式含 `schema_version=1`、米制单位、单目尺寸及原始/校正矩阵。Android 会检查版本、单位、矩阵形状、有限数值、焦距、基线和 320×240 分辨率。导入非法文件不会替换内存中的有效标定。

## 架构与算法

```text
UVCAndroid → Kotlin 帧回调 → JNI 复制到 Rust 自有缓冲区
  → 最新帧队列 → OpenCV 校正 / SGBM → 深度和距离统计
  → 独立 YOLOX 队列（最多每 100 ms 启动一次）→ 框内距离
  → Android 原生 Texture + Flutter 中文图层
```

图像不经 Dart 传输；FRB 只传设置、JSON 结构化结果、标定和点击查询。线程队列只保留最新帧，过期 0.5 秒的检测结果不参与测距。无效深度为 NaN，导出的结构化距离使用 null/缺失点。

- SGBM 与桌面固定参数一致：80 个视差、5×5 窗口、3WAY。
- 深度 `Z=fB/d`；默认可靠范围 0.20～3.00 m。
- 识别框中央 60% 中位数，有效数量至少 `max(10, 区域面积×10%)`。
- 全场景 8×8 网格、有效比例至少 50%；物体模式取可测框距离极值。
- EMA 0.25，0.5 秒无有效数据清空，模式/会话切换重置。
- YOLOX Nano 416×416，置信度 0.40、类无关 NMS 0.45。

## 固定工具链

产品版本以仓库根目录 `VERSION` 为单源，构建前由 `tool/sync-version.ps1` 写入 `pubspec.yaml`（格式 `X.Y.Z+git提交次数`）。CI 工作流见 `.github/workflows/build-apk.yml`。

| 项目 | 版本 |
|---|---|
| Flutter / Dart | 3.47.1 / 3.13.1 |
| Rust / FRB | 1.98.0 / 2.12.0 |
| Android min / compile / target SDK | 33 / 37 / 37 |
| NDK / Java | 28.2.13676358 / 21（编译目标 17） |
| Gradle / AGP | 9.3.1 / 9.1.0 |
| OpenCV / opencv crate | 4.12.0 / 0.95.1 |
| ONNX Runtime / ort crate | 1.22.0 / 2.0.0-rc.10 |
| UVCAndroid | 1.0.13 |

提交保留 `pubspec.lock`、`Cargo.lock` 和 Gradle Wrapper。首次构建需要联网下载依赖，安装后的识别与测距不依赖网络。AGP 9.1 对 compile SDK 37 会提示尚未经其测试；不能据此声称所有 Android 17 设备都已兼容。

## Windows 构建

安装上述 Flutter、Rust、Android SDK/NDK，并确保 `flutter`、`cargo` 在 PATH。Rust 需要 `aarch64-linux-android` target 和 Windows MSVC 工具链；可通过 Android Studio SDK Manager 安装 SDK/NDK。

仓库根目录执行：

```powershell
# 公共源码版本：无私有资源也能构建并运行演示，识别提示模型缺失。
.\mobile\tool\build.ps1

# 个人测试版本：需要 private-data 访问权及原 Python 虚拟环境。
.\mobile\tool\build.ps1 -WithPrivateData

# 公开正式版：只内置官方模型，不带个人标定；需先配置长期签名。
.\mobile\tool\build.ps1 -Mode release -PublicRelease
```

脚本获取官方 OpenCV/ORT AAR 并核对 SHA-256，构建 ARM64 Rust 库，运行检查与单元测试，生成 APK 并检查 ZIP/ELF 的 16 KB 对齐。SDK 默认 `D:\Android\Sdk`，可用 `-AndroidSdk` 指定；脚本不修改系统环境变量。

调试输出：`mobile/build/app/outputs/flutter-apk/app-debug.apk`；正式输出：`mobile/build/app/outputs/flutter-apk/app-release.apk`。Release 缺少正式签名时会停止构建，不用调试密钥代替。签名初始化、备份与从调试版迁移见 [正式签名说明](SIGNING.md)。

私有模型/标定暂存于被 Git 忽略的 `android/app/src/main/assets/private/`。若目录已有个人资源，公共构建入口会拒绝静默打包；改用 `-WithPrivateData` 或全新工作区构建。个人资源 APK 不自动发布。密钥、下载缓存、原生二进制、手机截图及构建产物不入公开仓库。

更改 Rust 桥接接口后，在 `mobile/` 执行固定版本 `flutter_rust_bridge_codegen generate --no-web --no-auto-upgrade-dependency`，再重建原生库和 APK；不能只更新一侧生成文件。

## 测试

实际通过的检查与实机性能统计口径见 [验证记录](VALIDATION.md)。

```powershell
# 仓库根目录
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe mobile/tool/compare-python.py
cargo test --locked --manifest-path mobile/rust/Cargo.toml

# mobile 目录
flutter analyze
flutter test test
flutter test integration_test/native_smoke_test.dart -d <模拟器ID>
flutter test integration_test/camera_smoke_test.dart -d <手机ADB地址>
flutter test integration_test/ui_smoke_test.dart -d <手机ADB地址>
flutter test integration_test/resource_smoke_test.dart -d <模拟器ID>
```

16 KB 模拟器需先用 `tool/build-native.ps1 -Abi x86_64` 准备对应原生库。手机集成测试要求真实相机、保持前台并确认授权，测量 30 秒；测试日志只记录统计，不保存相机图像。Python/Rust 对照覆盖同一组合成深度数据的框距离、模式选择、中心点和有效值过滤，不等同于真实图像全像素校正精度验证。

已知物距误差与连续运行压测已完成验收。处理延迟统计从 UVC 帧到达 Rust 开始，不包含传感器曝光、USB 传输和最终屏幕显示延迟。

## 第三方来源

- [Flutter](https://github.com/flutter/flutter)、[flutter_rust_bridge](https://github.com/fzyzcjy/flutter_rust_bridge)
- [OpenCV](https://github.com/opencv/opencv)、[opencv-rust](https://github.com/twistedfall/opencv-rust)
- [ONNX Runtime](https://github.com/microsoft/onnxruntime)、[ort](https://github.com/pykeio/ort)
- [UVCAndroid](https://github.com/shiyinghan/UVCAndroid)：包含 UVC/USB/JPEG 等第三方组件，分发时需保留各自许可。
- [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX)：现有私有子模块中的模型来源和 SHA-256 继续为准；准备脚本核对 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`。

应用“开源许可”同时展示 Flutter 插件和随包保存的原生组件许可，来源见 [许可来源](licenses/SOURCES.md)。设置页的 GitHub 仓库卡片可直接打开外部浏览器。
