# 2026-09-19 CI 跑通并发布 v1.0.2+23 **[重大]**

## 结果

- Secrets：`STEREORANGE_KEYSTORE_BASE64` 等四项已用 `gh secret set` 配置到仓库。
- 规范化提交并推送 main；版本源 `VERSION=1.0.2`。
- **CI `build-apk` 在 tag `v1.0.2+23` 上全绿**（约 20 分钟）。
- Release：https://github.com/mcxiaochenn/StereoRange/releases/tag/v1.0.2%2B23
  - `StereoRange-v1.0.2+23-android-arm64.apk`
  - `SHA256SUMS.txt`
- Actions 产物同步上传：`StereoRange-v1.0.2+23-android-arm64`

## 目录整理

- `3D-Print/` → `assets/3d-print/`
- 论文 docx → `assets/papers/`
- README / AGENTS / 发布说明路径已更新

## CI 排障记录 **[重大]**

| 问题 | 处理 |
|------|------|
| setup-android 默认装已废弃 `tools` | `packages: ''`，自管 sdkmanager |
| `--sdk_root path` 被拒 | 改用 `--sdk_root=<path>` |
| `platforms;android-37` 不存在 | 远程包名是 **`platforms;android-37.0`**，安装候选含 37.x |
| Flutter 首次 `--machine` 混入非 JSON | 从输出中提取 JSON/正则解析版本 |
| sync-version 返回对象导致 `$LASTEXITCODE` 误判 | try/catch + pubspec 格式校验；勿用 `$args` |

## 注意

- 正式包 `versionCode=23`，低于此前手工发布的 v1.0.1（code 101），真机覆盖安装会失败，需先卸载旧包。
- 失败历史 tag（`v1.0.2+15/16/18/19/20/21/22`）仍留在远程，可手动清理：  
  `git push origin :refs/tags/<tag>`

## 目录现状（根目录）

仅保留入口与工程文件；静态资源集中在 `assets/`。
