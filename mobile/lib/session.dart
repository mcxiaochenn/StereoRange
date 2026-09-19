import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'src/rust/api.dart' as rust;
import 'src/rust/frb_generated.dart';

class RangeSettings {
  const RangeSettings({
    this.minimum = .2,
    this.maximum = 3,
    this.confidence = .4,
    this.objectsOnly = false,
    this.boxes = true,
    this.points = true,
    this.theme = 'system',
  });
  final double minimum, maximum, confidence;
  final bool objectsOnly, boxes, points;
  final String theme;
  Map<String, dynamic> toJson() => {
    'minimum_m': minimum,
    'maximum_m': maximum,
    'confidence': confidence,
    'objects_only': objectsOnly,
    'boxes': boxes,
    'points': points,
    'theme': theme,
  };
  factory RangeSettings.fromJson(Map<String, dynamic> j) => RangeSettings(
    minimum: (j['minimum_m'] as num?)?.toDouble() ?? .2,
    maximum: (j['maximum_m'] as num?)?.toDouble() ?? 3,
    confidence: (j['confidence'] as num?)?.toDouble() ?? .4,
    objectsOnly: j['objects_only'] == true,
    boxes: j['boxes'] != false,
    points: j['points'] != false,
    theme: j['theme'] as String? ?? 'system',
  );
  RangeSettings copyWith({
    double? minimum,
    double? maximum,
    double? confidence,
    bool? objectsOnly,
    bool? boxes,
    bool? points,
    String? theme,
  }) => RangeSettings(
    minimum: minimum ?? this.minimum,
    maximum: maximum ?? this.maximum,
    confidence: confidence ?? this.confidence,
    objectsOnly: objectsOnly ?? this.objectsOnly,
    boxes: boxes ?? this.boxes,
    points: points ?? this.points,
    theme: theme ?? this.theme,
  );
  void validate() {
    if (!minimum.isFinite ||
        !maximum.isFinite ||
        minimum <= 0 ||
        maximum <= minimum) {
      throw const FormatException('距离范围必须为正数，且最大值大于最小值');
    }
    if (!confidence.isFinite || confidence <= 0 || confidence > 1) {
      throw const FormatException('置信度必须大于 0 且不超过 1');
    }
  }
}

class FrameData {
  const FrameData(this.json);
  final Map<String, dynamic> json;
  static const empty = FrameData({});
  int get id => (json['frame_id'] as num?)?.toInt() ?? 0;
  bool get running => json['running'] == true;
  bool get demo => json['demo'] == true;
  bool get modelReady => json['model_ready'] == true;
  double? get rms => (json['rms'] as num?)?.toDouble();
  double number(String key) => (json[key] as num?)?.toDouble() ?? 0;
  List<Map<String, dynamic>> get detections =>
      (json['detections'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
  List<Map<String, dynamic>> get points => (json['points'] as List? ?? [])
      .map((e) => Map<String, dynamic>.from(e as Map))
      .toList();
  List<String> get warnings => (json['warnings'] as List? ?? []).cast<String>();
  double? distance(String kind) {
    for (final point in points) {
      if (point['kind'] == kind) return (point['distance_m'] as num).toDouble();
    }
    return null;
  }
}

/// 测试通过假后端复现状态，无需加载 Android 或 Rust 动态库。
abstract class RangeBackend {
  Stream<FrameData> get frames;
  Stream<Map<String, dynamic>> get devices;
  Future<Map<String, dynamic>> prepare();
  Future<void> start(bool demo);
  Future<void> stop();
  Future<void> configure(RangeSettings settings, int view);
  Future<double> calibration(String json);
  Future<String?> importCalibration();
  Future<void> saveCalibration(String json);
  Future<double?> sample(int x, int y);
  Future<String?> screenshot();
}

class NativeBackend implements RangeBackend {
  static bool _rustReady = false;
  static const channel = MethodChannel('stereorange/android');
  static const eventChannel = EventChannel('stereorange/device');
  @override
  Stream<FrameData> get frames {
    late StreamSubscription<String> subscription;
    late StreamController<FrameData> controller;
    controller = StreamController<FrameData>(
      onListen: () {
        subscription = rust.subscribeResults().listen(
          (s) =>
              controller.add(FrameData(jsonDecode(s) as Map<String, dynamic>)),
          onError: controller.addError,
          onDone: controller.close,
        );
      },
      onCancel: () async {
        await rust.unsubscribeResults();
        await subscription.cancel();
      },
    );
    return controller.stream;
  }

  @override
  Stream<Map<String, dynamic>> get devices => eventChannel
      .receiveBroadcastStream()
      .map((v) => Map<String, dynamic>.from(v as Map));
  @override
  Future<Map<String, dynamic>> prepare() async {
    final info = Map<String, dynamic>.from(
      (await channel.invokeMethod<Map>('prepare'))!,
    );
    if (!_rustReady) {
      await RustLib.init();
      _rustReady = true;
    }
    await rust.initialize(
      modelPath: info['modelPath'] as String,
      runtimePath: info['runtimePath'] as String,
    );
    return info;
  }

  @override
  Future<void> start(bool demo) async {
    await channel.invokeMethod<void>('disconnect');
    await rust.startSession(demo: demo);
    await channel.invokeMethod<void>('render', {'active': true});
    try {
      if (!demo) await channel.invokeMethod<void>('connect');
    } catch (_) {
      await stop();
      rethrow;
    }
  }

  @override
  Future<void> stop() async {
    await rust.stopSession();
    await channel.invokeMethod<void>('render', {'active': false});
    await channel.invokeMethod<void>('disconnect');
  }

  @override
  Future<void> configure(RangeSettings settings, int view) async {
    await rust.updateSettings(json: jsonEncode(settings.toJson()));
    await channel.invokeMethod<void>('view', {
      'index': view,
      'boxes': settings.boxes,
      'points': settings.points,
    });
  }

  @override
  Future<double> calibration(String json) => rust.loadCalibration(json: json);
  @override
  Future<String?> importCalibration() =>
      channel.invokeMethod<String>('importCalibration');
  @override
  Future<void> saveCalibration(String json) =>
      channel.invokeMethod<void>('saveCalibration', {'json': json});
  @override
  Future<double?> sample(int x, int y) => rust.sampleDistance(x: x, y: y);
  @override
  Future<String?> screenshot() => channel.invokeMethod<String>('screenshot');
}

class RangeController extends ChangeNotifier {
  RangeController(this.backend);
  final RangeBackend backend;
  final frame = ValueNotifier<FrameData>(FrameData.empty);
  RangeSettings settings = const RangeSettings();
  SharedPreferences? preferences;
  StreamSubscription<FrameData>? _frames;
  StreamSubscription<Map<String, dynamic>>? _devices;
  bool ready = false,
      busy = false,
      running = false,
      demo = false,
      fullscreen = false;
  bool _disposed = false, _resume = false, _foreground = true;
  bool modelReady = false;
  int page = 0, view = 0;
  int? textureId;
  double? calibrationRms;
  String device = '连接 USB 双目相机后即可开始', status = '未连接', error = '';
  String? tapReading;
  Timer? _tapTimer;

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  Future<void> initialize() async {
    var autoConnect = false;
    await _action(() async {
      preferences = await SharedPreferences.getInstance();
      final saved = preferences?.getString('settings');
      if (saved != null) {
        try {
          settings = RangeSettings.fromJson(
            jsonDecode(saved) as Map<String, dynamic>,
          );
          settings.validate();
        } catch (_) {
          settings = const RangeSettings();
        }
      }
      final info = await backend.prepare();
      textureId = (info['textureId'] as num).toInt();
      _frames ??= backend.frames.listen(
        (value) {
          if (_disposed) return;
          frame.value = value;
          modelReady = value.modelReady;
          if (running && !value.running) {
            running = false;
            _notify();
          }
        },
        onError: (Object e) {
          error = '处理结果读取失败：$e';
          _notify();
        },
      );
      _devices ??= backend.devices.listen(
        (event) {
          device = event['message'] as String? ?? '';
          final state = event['state'];
          if (state == 'connected') status = '实时测距';
          if (state == 'connecting') status = '连接中';
          if (state == 'error' || state == 'disconnected') {
            error = device;
            running = false;
            status = '未连接';
            frame.value = FrameData.empty;
            unawaited(backend.stop().catchError((Object _) {}));
          }
          _notify();
        },
        onError: (Object e) {
          error = '$e';
          _notify();
        },
      );
      final calibration = info['calibration'] as String?;
      if (calibration != null) {
        try {
          calibrationRms = await backend.calibration(calibration);
        } catch (e) {
          error = '内置标定不可用：$e';
        }
      }
      await backend.configure(settings, view);
      ready = true;
      autoConnect = info['hasCamera'] == true;
    });
    if (ready && autoConnect && !running && _foreground) {
      await start();
    }
  }

  Future<void> _action(Future<void> Function() task) async {
    if (busy || _disposed) return;
    busy = true;
    error = '';
    _notify();
    try {
      await task();
    } catch (e) {
      error = e is PlatformException ? (e.message ?? e.code) : '$e';
    } finally {
      busy = false;
      _notify();
      if (_resume && _foreground && ready && !running) {
        _resume = false;
        unawaited(start(simulation: demo));
      }
    }
  }

  Future<void> start({bool simulation = false}) => _action(() async {
    if (!ready) throw StateError('请先重试初始化');
    demo = simulation;
    status = simulation ? '模拟演示' : '连接中';
    tapReading = null;
    await backend.start(simulation);
    running = true;
  });
  Future<void> pause() => _action(() async {
    _resume = false;
    await backend.stop();
    running = false;
    status = '已暂停';
    tapReading = null;
    frame.value = FrameData.empty;
  });
  Future<void> suspend() async {
    _foreground = false;
    _resume = _resume || running;
    if (running) {
      await backend.stop();
      running = false;
      status = '已暂停';
      frame.value = FrameData.empty;
      _notify();
    }
  }

  Future<void> resume() async {
    _foreground = true;
    if (_resume && !busy) {
      _resume = false;
      await start(simulation: demo);
    }
  }

  Future<void> apply(RangeSettings next) => _action(() async {
    next.validate();
    await backend.configure(next, view);
    settings = next;
    await preferences?.setString('settings', jsonEncode(next.toJson()));
  });
  Future<void> selectView(int value) => _action(() async {
    await backend.configure(settings, value);
    view = value;
    tapReading = null;
  });
  Future<void> importCalibration() => _action(() async {
    final json = await backend.importCalibration();
    if (json == null) return;
    calibrationRms = await backend.calibration(json);
    await backend.saveCalibration(json);
  });
  Future<void> screenshot() => _action(() async {
    final message = await backend.screenshot();
    if (message != null) tapReading = message;
  });
  Future<void> sample(int x, int y) async {
    if (!running || view == 1) return;
    try {
      final value = await backend.sample(x, y);
      tapReading = value == null
          ? '($x, $y) 距离不可用'
          : '($x, $y) ${value.toStringAsFixed(2)} m';
    } catch (e) {
      tapReading = '测距失败：$e';
    }
    _tapTimer?.cancel();
    _tapTimer = Timer(const Duration(seconds: 3), () {
      tapReading = null;
      _notify();
    });
    _notify();
  }

  void selectPage(int value) {
    page = value;
    _notify();
  }

  void toggleFullscreen() {
    fullscreen = !fullscreen;
    SystemChrome.setEnabledSystemUIMode(
      fullscreen ? SystemUiMode.immersiveSticky : SystemUiMode.edgeToEdge,
    );
    _notify();
  }

  @override
  void dispose() {
    _disposed = true;
    _tapTimer?.cancel();
    _frames?.cancel();
    _devices?.cancel();
    if (ready) unawaited(backend.stop().catchError((Object _) {}));
    frame.dispose();
    super.dispose();
  }
}
