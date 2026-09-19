# 2026-09-19 CI 跑通并发布 v1.0.2 **[重大]**

## 版本颗粒度（已对齐需求）

| 角色 | 格式 | 谁维护 |
|------|------|--------|
| Git tag / GitHub Release | **`vX.Y.Z`**（如 `v1.0.2`） | 人工打 tag |
| 构建版本 / APK 文件名 | `vX.Y.Z+N`（如 `v1.0.2+25`） | 脚本自动附加提交次数 |

带 `+N` 的 tag **不再使用**；CI 遇到会直接失败并提示。

## 结果

- Secrets：`STEREORANGE_KEYSTORE_BASE64` 等四项已配置。
- 失败 tag `v1.0.2+15/16/18/19/20/21/22` 已删除。
- 正式发布 tag：**`v1.0.2`**（提交次数由 CI 自动写入产物名与 versionCode）。

## 目录整理

- `3D-Print/` → `assets/3d-print/`
- 论文 docx → `assets/papers/`

## CI 排障记录 **[重大]**

| 问题 | 处理 |
|------|------|
| setup-android 默认装已废弃 `tools` | `packages: ''`，自管 sdkmanager |
| `--sdk_root path` 被拒 | 改用 `--sdk_root=<path>` |
| `platforms;android-37` 不存在 | 远程包名是 **`platforms;android-37.0`** |
| Flutter 首次 `--machine` 混入非 JSON | 从输出中提取 JSON/正则解析版本 |
| sync-version 返回对象导致 `$LASTEXITCODE` 误判 | try/catch + pubspec 格式校验；勿用 `$args` |

## 注意

- `versionCode` 为 git 提交次数；若低于历史包（如手工版 code 101），需卸载旧包后再装。
- 发流程：改 `VERSION` → 提交 push → `git tag vX.Y.Z` → `git push origin vX.Y.Z`。

