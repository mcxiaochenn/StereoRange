import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:stereorange/session.dart';
import 'package:stereorange/src/rust/api.dart' as rust;
import 'package:stereorange/src/rust/frb_generated.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('缺失模型不阻断深度，加载有效模型后可恢复', (tester) async {
    final info = (await NativeBackend.channel.invokeMethod<Map>('prepare'))!;
    await RustLib.init();
    await rust.initialize(
      modelPath: '/nonexistent/stereorange.onnx',
      runtimePath: info['runtimePath'] as String,
    );
    FrameData latest = FrameData.empty;
    final frames = rust.subscribeResults().listen((json) {
      latest = FrameData(jsonDecode(json) as Map<String, dynamic>);
    });
    try {
      await rust.startSession(demo: true);
      await Future<void>.delayed(const Duration(seconds: 2));
      expect(latest.id, greaterThan(0));
      expect(latest.points, isNotEmpty);
      expect(latest.modelReady, false);
      expect(latest.warnings.join(), contains('模型不可用'));
      await rust.initialize(
        modelPath: info['modelPath'] as String,
        runtimePath: info['runtimePath'] as String,
      );
      await Future<void>.delayed(const Duration(seconds: 2));
      expect(latest.modelReady, true);
      expect(latest.number('detection_fps'), greaterThan(0));
    } finally {
      await rust.stopSession();
      await rust.unsubscribeResults();
      await frames.cancel().timeout(const Duration(seconds: 5));
    }
  });
}
