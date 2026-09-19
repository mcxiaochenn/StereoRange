# 正式签名与公开发布

v1.0.1：Android versionName `1.0.1`，versionCode `101`，ARM64，最低 Android 13。

正式证书 SHA-256：

```text
0d348f24c796ae569029cb3e37b4a9aad1024c6ad8697778cc66e05337000622
```

这是 StereoRange 的长期 Android 应用签名，不是 Android Debug 证书，也不是应用商店认证。以后升级必须使用同一密钥，并提高 versionCode。

## 本机维护

本机密钥位于仓库外的 `D:\Android\Signing\StereoRange\release.p12`。密码以 Windows DPAPI 加密保存在同目录 `credentials.clixml`，目录限制为当前 Windows 用户和 SYSTEM 可读。初始化脚本拒绝覆盖已有文件。

请备份密钥，并在换电脑、重装系统前把密码安全保存到密码管理器。**只备份 credentials.clixml 不能保证换机解密**，它与当前 Windows 账户/机器绑定。不要把密钥、明文密码或该加密凭据上传 GitHub。丢失长期签名密钥后，不能用新密钥覆盖安装旧应用。

首次建立自己的签名（现有维护机不需要重复执行）：

```powershell
.\mobile\tool\initialize-signing.ps1
```

正式公开构建：

```powershell
.\mobile\tool\build.ps1 -Mode release -PublicRelease
```

也可通过 `STEREORANGE_KEYSTORE`、`STEREORANGE_STORE_PASSWORD`、`STEREORANGE_KEY_ALIAS`、`STEREORANGE_KEY_PASSWORD` 进程环境变量提供其他维护环境的同一密钥。构建结束会还原这些环境变量，不把密码写入 Gradle 配置或日志。

## 公开资源边界

公开构建从官方地址下载 YOLOX-Nano，核对 SHA-256，使用 `.native/public-assets` 独立目录。它不读取私有子模块的标定或采集图片；发布前检查 APK 内 `assets/private/` 仅有官方模型，并拒绝标定、NPZ、密钥文件。

公开 APK 支持离线识别和模拟测距；使用真实相机测距离前，必须自行导入匹配的标定 JSON。个人测试包使用 `-WithPrivateData`，不能作为公开 Release 附件。

## 从调试版迁移

原调试版与正式版签名不同，Android 不允许覆盖安装。请先导出或保留自己的标定 JSON，再由本人卸载调试版、安装正式版并重新导入。发布流程不会自动卸载手机上的应用。

发布前须通过测试、APK 签名、16 KB ZIP/ELF 对齐、版本号和资源检查；上传 APK 与 SHA-256 校验文件，标签指向已推送的同一提交。
