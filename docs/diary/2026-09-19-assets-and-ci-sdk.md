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
- 发布 tag：`v1.0.2+<提交次数>`（本轮将随修复提交后的次数生成）
- 注意：此前失败 tag `v1.0.2+15` 仍留在远程，可忽略；正式以成功 CI 的 tag 为准

## 遗留

- `platforms;android-37` 若所有 channel 均不可用，需把 `mobile/android/app/build.gradle.kts` 的 `compileSdk` 改为远程可用版本，或改用本机已有 SDK 的 CI runner
- 失败 tag `v1.0.2+15` 需所有者手动删除：`git push origin :refs/tags/v1.0.2+15`
