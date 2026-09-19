import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:stereorange/main.dart';
import 'package:stereorange/session.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('手机完整界面自动连接、模式切换、暂停恢复及页面导航', (tester) async {
    final controller = RangeController(NativeBackend());
    await tester.pumpWidget(StereoRangeApp(controller: controller));
    Future<void> waitFor(bool Function() condition) async {
      final deadline = DateTime.now().add(const Duration(seconds: 30));
      while (!condition() && DateTime.now().isBefore(deadline)) {
        await tester.pump(const Duration(milliseconds: 100));
        await Future<void>.delayed(const Duration(milliseconds: 100));
      }
      expect(condition(), true);
    }

    await waitFor(() => controller.running && controller.frame.value.id > 0);
    expect(controller.demo, false);
    await tester.tap(find.text('仅识别物体'));
    await waitFor(() => controller.settings.objectsOnly);
    await tester.tap(find.text('暂停'));
    await waitFor(() => !controller.running && !controller.busy);
    expect(controller.frame.value.points, isEmpty);
    await tester.tap(find.text('开始测距'));
    await waitFor(() => controller.running && controller.frame.value.id > 0);
    await tester.tap(find.text('设备').last);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('设备与标定'), findsOneWidget);
    await tester.tap(find.text('设置').last);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('测距设置'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await controller.apply(const RangeSettings());
    await controller.pause();
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(milliseconds: 300));
  });
}
