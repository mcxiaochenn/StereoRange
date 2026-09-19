// 集成测试日志用于记录实机统计，不在应用正式入口运行。
// ignore_for_file: avoid_print
import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:stereorange/session.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('真实 USB 帧进入 Rust 并完成测距与离线识别', (tester) async {
    final backend = NativeBackend();
    final info = await backend.prepare();
    expect(info['hasCamera'], true, reason: '需要已连接的 USB 双目相机');
    await backend.configure(const RangeSettings(), 0);
    final first = Completer<FrameData>();
    final samples = <FrameData>[];
    final frames = backend.frames.listen((f) {
      if (f.running && !f.demo && f.number('depth_fps') > 0) {
        samples.add(f);
        if (!first.isCompleted) first.complete(f);
      }
    });
    final devices = backend.devices.listen((event) {
      // 只记录设备状态，不记录图像或个人标定内容。
      print('USB 状态：$event');
    });
    try {
      await backend.start(false);
      final uncalibrated = await first.future.timeout(
        const Duration(seconds: 90),
      );
      expect(uncalibrated.points, isEmpty);
      expect(uncalibrated.warnings.join(), contains('标定'));
      if (info['calibration'] != null) {
        await backend.calibration(info['calibration'] as String);
      }
      samples.clear();
      final elapsed = Stopwatch()..start();
      await Future<void>.delayed(const Duration(seconds: 30));
      elapsed.stop();
      expect(samples, isNotEmpty);
      final last = samples.last;
      expect(last.json['width'], 320);
      expect(last.json['height'], 240);
      expect(samples.any((f) => f.number('detection_fps') > 0), true);
      print(
        '实机统计：${jsonEncode({'received_results': samples.length, 'seconds': elapsed.elapsedMilliseconds / 1000, 'processed_fps': samples.length * 1000 / elapsed.elapsedMilliseconds, 'capture_fps': last.number('capture_fps'), 'detection_fps': last.number('detection_fps'), 'latency_ms': last.number('latency_ms'), 'points': last.points, 'warnings': last.warnings})}',
      );
      print('验证停止');
      await backend.stop().timeout(const Duration(seconds: 10));
      print('验证停止后点击');
      expect(await backend.sample(160, 120), isNull);
      // 验证停止后的资源重载不重复初始化桥接层。
      print('验证重载');
      await backend.prepare().timeout(const Duration(seconds: 10));
      print('重载通过');
      samples.clear();
      await backend.start(false);
      await Future<void>.delayed(const Duration(seconds: 3));
      expect(samples, isNotEmpty, reason: '停止后必须可以重新打开相机并出帧');
      print('相机重连通过');
    } finally {
      await backend.stop().timeout(const Duration(seconds: 10));
      print('取消结果订阅');
      await frames.cancel().timeout(const Duration(seconds: 10));
      print('取消设备订阅');
      await devices.cancel().timeout(const Duration(seconds: 10));
    }
  }, timeout: const Timeout(Duration(minutes: 3)));
}
