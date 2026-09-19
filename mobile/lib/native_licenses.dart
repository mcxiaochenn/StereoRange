import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

void registerNativeLicenses() {
  LicenseRegistry.addLicense(() async* {
    for (final name in const [
      'OpenCV', 'ONNX-Runtime', 'ONNX-ThirdPartyNotices', 'YOLOX',
      'UVCAndroid', 'libjpeg-turbo', 'libusb', 'libuvc', 'libyuv', 'libcxx',
    ]) {
      yield LicenseEntryWithLineBreaks(
        [name], await rootBundle.loadString('licenses/$name.txt'),
      );
    }
  });
}
