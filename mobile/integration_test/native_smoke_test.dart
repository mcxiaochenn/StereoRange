import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:stereorange/session.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('原生 OpenCV、ONNX 与 Flutter/Rust 桥接冒烟', (tester) async {
    final backend = NativeBackend();
    final info = await backend.prepare();
    expect(info['textureId'], isA<int>());
    await backend.configure(const RangeSettings(), 0);
    final output = backend.frames
        .firstWhere(
          (f) => f.id >= 3 && f.modelReady && f.number('detection_fps') > 0,
        )
        .timeout(const Duration(seconds: 30));
    await backend.start(true);
    final result = await output;
    expect(result.demo, true);
    expect(result.points, isNotEmpty);
    final distance = await backend.sample(200, 120);
    expect(distance, inInclusiveRange(.80, 1.10));
    await backend.stop();
    expect(await backend.sample(200, 120), isNull);
  });
}
