# 2026-09-19 CI 跑通并发布 v1.0.2 **[重大]**

## 版本颗粒度（已对齐需求）

| 角色 | 格式 | 谁维护 |
|------|------|--------|
| Git tag / GitHub Release | **`vX.Y.Z`**（如 `v1.0.2`） | 人工打 tag |
| 构建版本 / APK 文件名 | `vX.Y.Z+N`（如 `v1.0.2+26`） | 脚本自动附加提交次数 |

带 `+N` 的 tag **不再使用**；CI 遇到会直接失败并提示。

## 结果

- Secrets：`STEREORANGE_KEYSTORE_BASE64` 等四项已配置。
- 失败 tag 与错误格式 tag（`v1.0.2+15…+23`）已删除。
- **正式 Release**：https://github.com/mcxiaochenn/StereoRange/releases/tag/v1.0.2
  - tag：`v1.0.2`
  - APK：`StereoRange-v1.0.2+26-android-arm64.apk`（versionCode=26 自动附加）
  - SHA-256：`43eb855a33b99303c10ea9d893728019818ccc31aa8ccbb7f3b3293ed741297c`
- 本地 tag 可能仍指向旧提交；以远程 `v1.0.2` → `2cbb15f` 为准。

## 目录整理

- `3D-Print/` → `assets/3d-print/`
- 论文 docx → `assets/papers/`

## 发版流程（之后照此）

1. 需要升语义版本时：只改根目录 `VERSION`（如 `1.0.3`）并提交 push。
2. `git tag v1.0.3 && git push origin v1.0.3`（**不要**写 `+N`）。
3. CI 自动拼 `X.Y.Z+提交数`、签名构建，并挂到 Release `v1.0.3`。

## CI 排障 **[重大]**

- 平台包名是 `platforms;android-37.0`
- sdkmanager 参数：`--sdk_root=<path>`
- workflow 的 `run` 块内禁止缩进错误的 PowerShell here-string


