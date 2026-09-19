import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:stereorange/repository_card.dart';

void main() {
  const channel = MethodChannel('stereorange/android');
  TestWidgetsFlutterBinding.ensureInitialized();
  tearDown(
    () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null),
  );
  testWidgets('仓库卡片展示正确地址，点击请求外部浏览器', (tester) async {
    String? method;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          method = call.method;
          return null;
        });
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: RepositoryCard())),
    );
    expect(find.text(repositoryUrl), findsOneWidget);
    await tester.tap(find.text('GitHub 项目仓库'));
    await tester.pumpAndSettle();
    expect(method, 'openRepository');
  });
  testWidgets('缺少浏览器时显示中文错误而不崩溃', (tester) async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (_) async {
          throw PlatformException(code: 'browser', message: '未找到浏览器');
        });
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: RepositoryCard())),
    );
    await tester.tap(find.text('GitHub 项目仓库'));
    await tester.pumpAndSettle();
    expect(find.text('未找到浏览器'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
