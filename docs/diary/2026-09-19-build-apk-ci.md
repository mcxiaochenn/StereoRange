# 2026-09-19 新增 build-apk CI 与版本单源 **[重大]**

## 需求

- 工作流名 `build-apk`，一 CI 两用。
- push → `main`：构建 APK，放入 Actions 产物。
- 发布版本 tag：正则校验源码版本与 tag；不一致则**以 tag 为准替换本次构建版本**。
- 版本格式：`vX.Y.Z+<git提交次数>`（例：`1.0.2` + 150 次提交 → `v1.0.2+150`）。
- 源码只保留一处主版本位置，其余从该处同步。

## 方案

| 项 | 约定 |
|----|------|
| 单源 | 根目录 `VERSION`，只写 `X.Y.Z` |
| 产物版本 | `vX.Y.Z+N`，`N = git rev-list --count HEAD`（tag 带了 `+N` 则用 tag 的 N） |
| Flutter 写入 | `mobile/pubspec.yaml` → `version: X.Y.Z+N`（`versionName` / `versionCode`） |
| 同步脚本 | `mobile/tool/sync-version.ps1`；`build.ps1` 构建前自动调用 |
| tag 正则 | `^v(\d+\.\d+\.\d+)(?:\+(\d+))?$` |
| 替换策略 | 仅影响本次 CI 工作区构建，不改写远程 main 历史 |

## 工作流行为

- 文件：`.github/workflows/build-apk.yml`
- push main：有签名 Secrets → 公开 release APK；无 Secrets → debug APK（产物仍上传）
- tag：必须配置签名 Secrets，否则失败；成功后 APK + `SHA256SUMS.txt` 挂到该 tag 的 Release
- Secrets：`STEREORANGE_KEYSTORE_BASE64` / `STEREORANGE_STORE_PASSWORD` / `STEREORANGE_KEY_ALIAS` / `STEREORANGE_KEY_PASSWORD`

## 本地验证

- `sync-version.ps1`：`1.0.1+13` 同步成功
- `-OverrideTag v1.0.2+999`：VERSION 被替换为 `1.0.2`，pubspec 为 `1.0.2+999`
- 非法 tag 会抛错

## 注意 **[重大]**

当前仓库提交次数仅 **13**，而已发布 v1.0.1 的 `versionCode` 为 **101**。按「提交次数」生成的新包 `versionCode` 会更小，真机**无法覆盖安装**。处理方式任选：

1. 卸载旧包后安装 CI 产物；
2. 或先提高 `VERSION` 语义版本，并等提交数超过历史 `versionCode`；
3. 或在足够多次提交后再打正式 tag。

## 后续状态

- 签名 Secrets 已配置，tag 正式包由 CI 自动签名发布。
- 发版约定已对齐为：**tag=`vX.Y.Z`**，产物文件名带自动 `+提交次数`。
- 历史 `v1.0.1` Release 文件名不含 `+N`，属旧命名；新包按 `StereoRange-vX.Y.Z+N-android-arm64.apk`。

