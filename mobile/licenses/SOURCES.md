# 原生组件许可来源

这些文本从上游直接保存，用于 v1.0.1 分发；应用“设置 → 开源许可”可查看。组件未在本项目中修改源码，构建脚本使用官方发行 AAR/NDK。完整源码、构建方式和各自第三方声明以下述上游为准。

| 文件 | 对应来源 |
|---|---|
| OpenCV.txt | https://github.com/opencv/opencv/blob/4.12.0/LICENSE |
| ONNX-Runtime.txt | https://github.com/microsoft/onnxruntime/blob/v1.22.0/LICENSE |
| ONNX-ThirdPartyNotices.txt | https://github.com/microsoft/onnxruntime/blob/v1.22.0/ThirdPartyNotices.txt |
| YOLOX.txt | https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE |
| UVCAndroid.txt | https://github.com/shiyinghan/UVCAndroid/blob/main/LICENSE |
| libjpeg-turbo.txt | https://github.com/shiyinghan/UVCAndroid/blob/main/libuvccamera/src/main/jni/libjpeg-turbo/LICENSE.md |
| libusb.txt | https://github.com/shiyinghan/UVCAndroid/blob/main/libuvccamera/src/main/jni/libusb/COPYING |
| libuvc.txt | https://github.com/shiyinghan/UVCAndroid/blob/main/libuvccamera/src/main/jni/libuvc/LICENSE.txt |
| libyuv.txt | https://github.com/lemenkov/libyuv/blob/master/LICENSE |
| libcxx.txt | https://github.com/llvm/llvm-project/blob/llvmorg-19.1.0/libcxx/LICENSE.TXT |

Rust 依赖版本保存在 Cargo.lock，Dart 依赖版本保存在 pubspec.lock；Flutter 的许可登记机制显示 Dart/Flutter 依赖许可。动态原生库随 APK 单独打包，重新构建和替换方式见 mobile/tool/build-native.ps1。
