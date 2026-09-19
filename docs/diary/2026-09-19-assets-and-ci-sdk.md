# 2026-09-19 目录整理与 CI SDK 安装修复 **[重大]**

## 目录整理

根目录不再直接摊放二进制资源，统一收入 `assets/`：

| 原路径 | 新路径 |
|--------|--------|
| `3D-Print/` | `assets/3d-print/` |
| `基于双目视觉…实现.docx` | `assets/papers/…docx` |
| （已有）棋盘格 PDF/SVG | 仍在 `assets/` 根下 |

README、AGENTS、发布说明中的路径已同步更新。

## CI：Android SDK 安装 **[重大]**

失败原因：

1. `android-actions/setup-android@v3` 默认安装已废弃的 `tools` 包。
2. 远程 `sdkmanager` 找不到 `platforms;android-37`（compileSdk 37 可能需 preview/channel）。

修复：

- setup-android 不再传入 `tools`；
- 自建安装步骤：用 Process 调 `sdkmanager`，自动答许可证；
- 对每个包依次尝试 default / channel 0–3；
- 失败时打印 `--list` 便于诊断，并校验平台、NDK、zipalign 目录确实存在。

## 版本

- 语义版本源 `VERSION=1.0.2`
- 后续约定：**tag 只打 `vX.Y.Z`**，`+提交次数` 由脚本自动附加（见当日后续日记）
- 失败的 `v1.0.2+N` tag 已清理

## 后续处理

- `platforms;android-37` 问题已定位为远程包名 `platforms;android-37.0`，CI 安装逻辑已兼容
- 失败 tag 已删除；正式 Release 见 tag `v1.0.2`

