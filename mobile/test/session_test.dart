import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:stereorange/main.dart';
import 'package:stereorange/session.dart';

class FakeBackend implements RangeBackend {
  final output = StreamController<FrameData>.broadcast();
  final device = StreamController<Map<String, dynamic>>.broadcast();
  bool failStart = false, started = false;
  int selectedView = 0, stops = 0;
  String? imported;
  RangeSettings settings = const RangeSettings();
  @override
  Stream<FrameData> get frames => output.stream;
  @override
  Stream<Map<String, dynamic>> get devices => device.stream;
  @override
  Future<Map<String, dynamic>> prepare() async => {'textureId': 1};
  @override
  Future<void> start(bool demo) async {
    if (failStart) {
      throw PlatformException(code: 'permission', message: '相机权限被拒绝');
    }
    started = true;
  }

  @override
  Future<void> stop() async {
    stops++;
    started = false;
  }

  @override
  Future<void> configure(RangeSettings settings, int view) async {
    this.settings = settings;
    selectedView = view;
  }

  @override
  Future<double> calibration(String json) async {
    if (json == 'invalid') throw const FormatException('标定无效');
    return 4.09;
  }

  @override
  Future<String?> importCalibration() async => imported;
  @override
  Future<void> saveCalibration(String json) async {}
  @override
  Future<double?> sample(int x, int y) async => x == 0 ? null : 1.25;
  @override
  Future<String?> screenshot() async => '截图已保存';
  Future<void> close() async {
    await output.close();
    await device.close();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));
  test('启动、暂停、切换模式与后台恢复', () async {
    final b = FakeBackend();
    final c = RangeController(b);
    await c.initialize();
    await c.start(simulation: true);
    expect(c.running, true);
    expect(c.demo, true);
    await c.apply(c.settings.copyWith(objectsOnly: true));
    expect(b.settings.objectsOnly, true);
    await c.suspend();
    expect(c.running, false);
    await c.resume();
    expect(c.running, true);
    await c.pause();
    await c.resume();
    expect(c.running, false);
    c.dispose();
    await b.close();
  });
  test('权限失败与断连清除距离', () async {
    final b = FakeBackend();
    final c = RangeController(b);
    await c.initialize();
    b.failStart = true;
    await c.start();
    expect(c.error, contains('权限'));
    expect(c.running, false);
    b.failStart = false;
    await c.start();
    b.device.add({'state': 'disconnected', 'message': '相机已拔出'});
    await Future<void>.delayed(Duration.zero);
    expect(c.running, false);
    expect(c.frame.value.points, isEmpty);
    expect(c.error, contains('拔出'));
    c.dispose();
    await b.close();
  });
  test('标定验证失败保留原配置，范围非法不生效', () async {
    final b = FakeBackend();
    final c = RangeController(b);
    await c.initialize();
    b.imported = 'valid';
    await c.importCalibration();
    expect(c.calibrationRms, 4.09);
    b.imported = 'invalid';
    await c.importCalibration();
    expect(c.calibrationRms, 4.09);
    expect(c.error, contains('标定'));
    await c.apply(c.settings.copyWith(minimum: 4, maximum: 2));
    expect(c.settings.minimum, .2);
    c.dispose();
    await b.close();
  });
  testWidgets('竖屏首屏、设备标定告警与设置导航', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final b = FakeBackend();
    final c = RangeController(b);
    await c.initialize();
    c.calibrationRms = 4.09;
    await tester.pumpWidget(StereoRangeApp(controller: c, initialize: false));
    await tester.pumpAndSettle();
    expect(find.text('StereoRange'), findsOneWidget);
    expect(find.text('看见物体，也看见距离'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('设备').last);
    await tester.pumpAndSettle();
    expect(find.textContaining('4.090'), findsOneWidget);
    expect(find.textContaining('仅供参考'), findsOneWidget);
    await tester.tap(find.text('设置').last);
    await tester.pumpAndSettle();
    expect(find.text('测距设置'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpAndSettle();
    await b.close();
  });
  testWidgets('横屏导航与预览选择不会溢出', (tester) async {
    tester.view.physicalSize = const Size(1000, 600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final b = FakeBackend();
    final c = RangeController(b);
    await c.initialize();
    await tester.pumpWidget(StereoRangeApp(controller: c, initialize: false));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationRail), findsOneWidget);
    await tester.tap(find.text('深度'));
    await tester.pumpAndSettle();
    expect(c.view, 3);
    expect(b.selectedView, 3);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpAndSettle();
    await b.close();
  });
}
