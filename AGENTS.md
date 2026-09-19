# AGENTS.md

给在本仓库工作的 Agent / 协作者的强制规范。先读本文件，再改代码。

## 项目是什么

StereoRange：双目视觉 + 目标识别的实时测距系统。

- 桌面端：Python（OpenCV StereoSGBM、YOLOX-Nano ONNX、PySide6）
- Android 端：Flutter Material 3 + Rust（OpenCV/ORT）+ 少量 Kotlin（UVC/USB）
- 署名：平湖技师学院 · 陆逸尘（辰渊尘 ChenDusk · @mcxiaochenn，同一人）· 周璟雯 · 胡乐毅 · 指导教师 张梁
- 分工：陆逸尘（项目主负责/软件/论文实践与审阅）、周璟雯（双目相机外壳建模）、胡乐毅（论文基础理论）；张梁为导师
- 仓库：https://github.com/mcxiaochenn/StereoRange（GitHub 账号归属陆逸尘，不是独立作者名）

## 硬约束

1. **交流、提交说明、文档、日记一律用中文**；代码标识符遵循项目现有风格。
2. **Commit 使用 Conventional Commits**：`feat:` / `fix:` / `docs:` / `chore:` / `test:` 等。
3. **默认不 push**；仅当用户明确说「提交并推送 / commit and push」时才推远程。
4. **禁止把个人标定、实拍图片、签名密钥写进公开仓库**。个人数据只在私有子模块 `private-data/`。
5. **禁止提交**：`*.p12` / `*.jks` / `credentials.clixml` / `mobile/build/` / `mobile/.native/` / `mobile/rust/target/` / `jniLibs` / `assets/private/` 构建产物。
6. **Windows PowerShell 脚本请用 `pwsh` 执行**（`mobile/tool/*.ps1` 为 UTF-8 无 BOM；Windows PowerShell 5.1 会把中文字符串解析坏）。
7. **不要自行创建 git worktree** 去改主工作区；需要隔离时先问用户。
8. 改完代码要跑测试再提交；不能只改不验。

## 目录速览

| 路径 | 用途 |
|------|------|
| `main.py` / `calibrate.py` | 桌面入口与标定 CLI |
| `stereorange/` | Python 核心：采集、标定、视差、识别、UI、导出 |
| `mobile/` | Android（Flutter + Rust + Kotlin） |
| `private-data/` | 私有子模块：标定、模型、实拍图（未授权不可见） |
| `assets/3d-print/` | 3D 打印底座与公差测试模型 |
| `assets/papers/` | 论文等文档稿 |
| `docs/releases/` | 版本发布说明 |
| `docs/diary/` | 开发日记 + 索引 |
| `assets/` | 公开静态资源：棋盘格、3D 模型、论文 |
| `tests/` | Python 测试 |

## 常用命令

### 桌面 Python

```powershell
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe main.py --demo
.\.venv\Scripts\python.exe calibrate.py pattern --output-dir assets
.\.venv\Scripts\python.exe calibrate.py capture --camera 0 --target 30 --output-dir private-data\images_320x240
.\.venv\Scripts\python.exe calibrate.py solve --images private-data\images_320x240 --square-mm 25
.\.venv\Scripts\python.exe calibrate.py export-mobile --input private-data/calibration.npz --output private-data/calibration-mobile.json
```

### Android

```powershell
# 必须用 pwsh，不要用 Windows PowerShell 5.1
cd mobile
pwsh -File tool\build.ps1                          # 公共调试
pwsh -File tool\build.ps1 -WithPrivateData        # 个人测试（需 private-data）
pwsh -File tool\build.ps1 -Mode release -PublicRelease   # 公开正式签名
flutter analyze
flutter test test
cargo +1.98.0 test --locked --manifest-path rust/Cargo.toml
```

固定工具链见 `mobile/README.md`（Flutter 3.47.1、Rust 1.98.0、NDK 28.2.13676358、minSdk 33）。改 Rust 桥接接口后必须重新 `flutter_rust_bridge_codegen generate`，两侧生成文件一起提交。

## 采集与标定约定

- 当前比赛/演示默认：**总画面 640×240、每侧 320×240、MJPG、30 FPS、MSMF 优先**。
- 标定分辨率必须与每侧运行分辨率一致；换分辨率必须重标定。
- 棋盘：`9×6` 内角点、`25 mm` 方格；打印后需实测方格边长。
- 重新标定使用**新目录**，不要把不同分辨率图片混进旧目录。
- 运行时必须先 `remap` 立体校正，再算视差；只改占位焦距/基线不够。
- 当前正式标定双目 RMS 约 **0.378 px**（`private-data/calibration.npz`）。已知物距与连续运行压测已完成；换设备/分辨率/镜头位置后仍须重标定并按现场复核，标定 RMS 不能单独代替物距结论。

## 算法与 UI 口径（两端保持一致）

- 深度：`Z = fB/d`；无效/零/负视差记为 NaN。
- SGBM：与桌面固定参数对齐（约 80 视差、5×5、3WAY 等）。
- 物体框距离：框中央 60% 区域有效深度中位数。
- 全场景最近/最远：深度图 `8×8` 网格，有效比例 ≥50%。
- 中心点：画面中心 `15×15` 邻域中位数。
- 点击测距：`7×7` 邻域中位数。
- 跟踪：EMA `0.25`，`0.5 s` 无有效数据清空。
- 「全场景可靠深度」与「仅识别物体」**只影响最近/最远点**，中心点不变。

## 版本管理（单源）

- **唯一主版本位置**：仓库根目录 `VERSION`，只维护语义版本 `X.Y.Z`（例如 `1.0.2`）。
- **Git tag 颗粒度**：**只打 `vX.Y.Z`**（例：`v1.0.2`）。tag 上**不要**写提交次数。
- **提交次数**：由 `mobile/tool/sync-version.ps1` / CI **自动**读取 `git rev-list --count HEAD`，拼成产物版本 `X.Y.Z+N`。
  - 例：`VERSION=1.0.2`，打 tag `v1.0.2` 时提交数为 25 → 构建 `versionName=1.0.2`、`versionCode=25`，APK 名 `StereoRange-v1.0.2+25-android-arm64.apk`。
- `mobile/pubspec.yaml` 的 `version: X.Y.Z+N` **由构建同步生成**，不要当主版本手改；Flutter 将 `+N` 用作 `versionCode`，`X.Y.Z` 用作 `versionName`。
- 同步命令：`pwsh -File mobile\tool\sync-version.ps1`（可选 `-OverrideTag v1.0.2`）。
- 本地 `build.ps1` 与 CI `build-apk` 构建前都会自动同步。
- **tag 构建**：校验 tag 形如 `^v(\d+\.\d+\.\d+)$`；若与 `VERSION` 不一致，**以 tag 为准替换本次构建版本**（不改写远程 main 历史）。
- 若错误地打了 `vX.Y.Z+N` 这类 tag，CI 会直接失败并提示改用 `vX.Y.Z`。
- 提升正式语义版本时只改 `VERSION` 并提交；然后 `git tag vX.Y.Z && git push origin vX.Y.Z`。
- **注意**：`versionCode` 必须单调递增，否则真机无法覆盖安装。

## CI：`build-apk`

- 文件：`.github/workflows/build-apk.yml`，一 CI 两用。
- **push 到 main**：自动同步版本（`X.Y.Z+提交数`）并构建 APK，上传 Actions 产物。
- **发布 tag（仅 `vX.Y.Z`）**：校验/替换语义版本后构建；产物文件名带自动 `+N`；APK + `SHA256SUMS.txt` 挂到 **tag=`vX.Y.Z`** 的 GitHub Release。
- tag 正式包需要 Secrets：`STEREORANGE_KEYSTORE_BASE64`、`STEREORANGE_STORE_PASSWORD`、`STEREORANGE_KEY_ALIAS`、`STEREORANGE_KEY_PASSWORD`。
- 未配置签名时：普通 push 会构建 debug APK 供下载；tag 构建直接失败并提示配置密钥。

## Git 与 Release

- 分支：`main`。提交信息用 Conventional Commits（中文摘要可接受）。
- 私有子模块更新顺序：先在 `private-data/` commit+push，再在主仓库更新子模块指针。
- 公开 APK **只内置官方 YOLOX 模型**，不含个人标定；真实测距需导入自己的标定 JSON。
- Release 产物命名：
  - tag / Release 名：`vX.Y.Z`（人工）
  - APK 文件名：`StereoRange-vX.Y.Z+<自动提交数>-android-arm64.apk`
  - `SHA256SUMS.txt`
  - `StereoRange-vX.Y.Z+<自动提交数>-3d-print.zip`（如包含）
- 发布说明写在 `docs/releases/vX.Y.Z.md`；下载链接与版本叙述以 `VERSION` 与 CI 产物为准。
- 签名密钥在仓库外 `D:\Android\Signing\StereoRange\`，**永不入库**。

## 日记规范

- 每轮有用户可见结果的工作，在 `docs/diary/` 新增或追加一篇摘要。
- 维护 `docs/diary/INDEX.md` 索引：日期、主题、链接、标记。
- **重大事件**（大型变更、踩坑、发布、数据回滚）在日记标题或索引中标记 `**[重大]**`。
- 日记写清：做了什么、验证结果、遗留项；不要写无信息量的过程流水。

## 提交前检查清单

- [ ] 测试通过：`pytest`（47 项量级）/ `flutter test` / `cargo test`
- [ ] `flutter analyze` 无问题
- [ ] 公开 APK 仅 `arm64-v8a`，且 `assets/private` 只有官方模型
- [ ] 未提交密钥、个人标定、构建缓存
- [ ] README / 发布说明 / 日记索引已按本次变更更新
- [ ] Commit 信息符合 Conventional Commits
