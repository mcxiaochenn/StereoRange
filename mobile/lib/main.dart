import 'dart:async';

import 'package:flutter/material.dart';

import 'session.dart';
import 'measurement_view.dart';
import 'repository_card.dart';
import 'native_licenses.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  registerNativeLicenses();
  runApp(StereoRangeApp(controller: RangeController(NativeBackend())));
}

class StereoRangeApp extends StatefulWidget {
  const StereoRangeApp({
    super.key,
    required this.controller,
    this.initialize = true,
  });
  final RangeController controller;
  final bool initialize;
  @override
  State<StereoRangeApp> createState() => _StereoRangeAppState();
}

class _StereoRangeAppState extends State<StereoRangeApp>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (widget.initialize) unawaited(widget.controller.initialize());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) {
      unawaited(widget.controller.suspend());
    }
    if (state == AppLifecycleState.resumed) {
      unawaited(widget.controller.resume());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.controller,
    builder: (context, _) {
      ThemeData theme(Brightness brightness) => ThemeData(
        useMaterial3: true,
        brightness: brightness,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xff147d70),
          brightness: brightness,
        ),
        scaffoldBackgroundColor: brightness == Brightness.light
            ? const Color(0xfff5f8f6)
            : const Color(0xff101716),
      );
      return MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'StereoRange',
        theme: theme(Brightness.light),
        darkTheme: theme(Brightness.dark),
        themeMode: switch (widget.controller.settings.theme) {
          'light' => ThemeMode.light,
          'dark' => ThemeMode.dark,
          _ => ThemeMode.system,
        },
        home: RangeHome(controller: widget.controller),
      );
    },
  );
}

class RangeHome extends StatelessWidget {
  const RangeHome({super.key, required this.controller});
  final RangeController controller;
  @override
  Widget build(BuildContext context) {
    final c = controller;
    final wide = MediaQuery.sizeOf(context).width >= 800;
    final content = switch (c.page) {
      1 => DevicePage(controller: c),
      2 => SettingsPage(controller: c),
      _ => MeasurePage(controller: c),
    };
    return PopScope(
      canPop: !c.fullscreen,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && c.fullscreen) c.toggleFullscreen();
      },
      child: Scaffold(
        appBar: c.fullscreen
            ? null
            : AppBar(
                title: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'StereoRange',
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        letterSpacing: -.5,
                      ),
                    ),
                    Text('双目视觉 · 智能测距', style: TextStyle(fontSize: 12)),
                  ],
                ),
                actions: [
                  IconButton(
                    tooltip: '使用帮助',
                    onPressed: () => showHelp(context),
                    icon: const Icon(Icons.help_outline),
                  ),
                  const SizedBox(width: 8),
                ],
              ),
        body: SafeArea(
          child: Column(
            children: [
              if (c.busy) const LinearProgressIndicator(minHeight: 2),
              if (c.error.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                  child: Material(
                    color: Theme.of(context).colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(14),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline),
                          const SizedBox(width: 10),
                          Expanded(child: Text(c.error)),
                          TextButton(
                            onPressed: c.busy
                                ? null
                                : () => c.ready
                                      ? c.start(simulation: c.demo)
                                      : c.initialize(),
                            child: const Text('重试'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              Expanded(
                child: Row(
                  children: [
                    if (wide && !c.fullscreen)
                      NavigationRail(
                        selectedIndex: c.page,
                        onDestinationSelected: c.selectPage,
                        labelType: NavigationRailLabelType.all,
                        destinations: const [
                          NavigationRailDestination(
                            icon: Icon(Icons.center_focus_strong),
                            label: Text('测距'),
                          ),
                          NavigationRailDestination(
                            icon: Icon(Icons.usb_rounded),
                            label: Text('设备'),
                          ),
                          NavigationRailDestination(
                            icon: Icon(Icons.tune_rounded),
                            label: Text('设置'),
                          ),
                        ],
                      ),
                    Expanded(
                      child: c.fullscreen
                          ? MeasurementView(controller: c)
                          : content,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        bottomNavigationBar: wide || c.fullscreen
            ? null
            : NavigationBar(
                selectedIndex: c.page,
                onDestinationSelected: c.selectPage,
                destinations: const [
                  NavigationDestination(
                    icon: Icon(Icons.center_focus_strong),
                    label: '测距',
                  ),
                  NavigationDestination(
                    icon: Icon(Icons.usb_rounded),
                    label: '设备',
                  ),
                  NavigationDestination(
                    icon: Icon(Icons.tune_rounded),
                    label: '设置',
                  ),
                ],
              ),
      ),
    );
  }
}

class MeasurePage extends StatelessWidget {
  const MeasurePage({super.key, required this.controller});
  final RangeController controller;
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final c = controller;
      final view = Column(
        children: [
          Expanded(child: MeasurementView(controller: c)),
          const SizedBox(height: 10),
          ViewSelector(controller: c),
        ],
      );
      if (constraints.maxWidth >= 680) {
        return Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(child: view),
              const SizedBox(width: 16),
              SizedBox(
                width: 310,
                child: SingleChildScrollView(child: Controls(controller: c)),
              ),
            ],
          ),
        );
      }
      return ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
        children: [
          SizedBox(
            height: (constraints.maxWidth * .72).clamp(210, 360),
            child: MeasurementView(controller: c),
          ),
          const SizedBox(height: 10),
          ViewSelector(controller: c),
          const SizedBox(height: 16),
          Controls(controller: c),
        ],
      );
    },
  );
}

class ViewSelector extends StatelessWidget {
  const ViewSelector({super.key, required this.controller});
  final RangeController controller;
  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    scrollDirection: Axis.horizontal,
    child: Row(
      children: [
        for (final (i, label) in ['左图', '右图', '视差', '深度'].indexed)
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              label: Text(label),
              selected: controller.view == i,
              onSelected: controller.busy
                  ? null
                  : (_) => controller.selectView(i),
            ),
          ),
      ],
    ),
  );
}

class Controls extends StatelessWidget {
  const Controls({super.key, required this.controller});
  final RangeController controller;
  @override
  Widget build(BuildContext context) {
    final c = controller;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ValueListenableBuilder(
          valueListenable: c.frame,
          builder: (context, frame, _) => Column(
            children: [
              DistanceReadings(frame: frame),
              const SizedBox(height: 10),
              Text(
                '采集 ${frame.number('capture_fps').toStringAsFixed(0)} · 深度 ${frame.number('depth_fps').toStringAsFixed(0)} · 识别 ${frame.number('detection_fps').toStringAsFixed(0)} FPS',
                style: Theme.of(context).textTheme.labelMedium,
              ),
              if (frame.warnings.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    frame.warnings.join('\n'),
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        SegmentedButton<bool>(
          segments: const [
            ButtonSegment(
              value: false,
              label: Text('全场景'),
              icon: Icon(Icons.grid_view),
            ),
            ButtonSegment(
              value: true,
              label: Text('仅识别物体'),
              icon: Icon(Icons.category_outlined),
            ),
          ],
          selected: {c.settings.objectsOnly},
          onSelectionChanged: c.busy
              ? null
              : (s) => c.apply(c.settings.copyWith(objectsOnly: s.single)),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 8),
          child: Text(
            '只影响最近 / 最远点，中心点保持固定',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12),
          ),
        ),
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: c.busy || !c.ready
                    ? null
                    : () => c.running ? c.pause() : c.start(simulation: c.demo),
                icon: Icon(
                  c.running ? Icons.pause_rounded : Icons.play_arrow_rounded,
                ),
                label: Text(c.running ? '暂停' : '开始测距'),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filledTonal(
              tooltip: '截图',
              onPressed: c.running && !c.busy ? c.screenshot : null,
              icon: const Icon(Icons.photo_camera_outlined),
            ),
          ],
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextButton.icon(
              onPressed: c.busy || !c.ready ? null : () => c.start(),
              icon: const Icon(Icons.usb),
              label: const Text('连接相机'),
            ),
            TextButton.icon(
              onPressed: c.busy || !c.ready
                  ? null
                  : () => c.start(simulation: true),
              icon: const Icon(Icons.science_outlined),
              label: const Text('体验演示'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text('画面中的物体', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        ValueListenableBuilder(
          valueListenable: c.frame,
          builder: (context, frame, _) => frame.detections.isEmpty
              ? const Padding(
                  padding: EdgeInsets.symmetric(vertical: 20),
                  child: Text(
                    '暂无识别结果\n将瓶子、杯子或其他常见物体放入画面',
                    textAlign: TextAlign.center,
                    style: TextStyle(height: 1.8),
                  ),
                )
              : Column(
                  children: [
                    for (final d in frame.detections)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: const Icon(Icons.crop_free),
                        title: Text(d['label'] as String),
                        subtitle: Text(
                          '置信度 ${((d['confidence'] as num) * 100).round()}% · 有效深度 ${((d['valid_depth_ratio'] as num) * 100).round()}%',
                        ),
                        trailing: Text(
                          d['distance_m'] == null
                              ? '--'
                              : '${(d['distance_m'] as num).toStringAsFixed(2)} m',
                        ),
                      ),
                  ],
                ),
        ),
      ],
    );
  }
}

class DevicePage extends StatelessWidget {
  const DevicePage({super.key, required this.controller});
  final RangeController controller;
  @override
  Widget build(BuildContext context) {
    final c = controller;
    final rms = c.calibrationRms;
    final color = rms == null
        ? Theme.of(context).colorScheme.outline
        : rms <= 1
        ? Colors.green
        : rms <= 2
        ? Colors.orange
        : Colors.red;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('设备与标定', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 20),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.usb_rounded),
          title: const Text('USB 双目相机'),
          subtitle: Text(c.device),
        ),
        const ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(Icons.aspect_ratio),
          title: Text('每侧 320 × 240'),
          subtitle: Text('横向拼接 640 × 240 · 请求 30 FPS'),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton.tonalIcon(
            onPressed: c.busy || !c.ready ? null : () => c.start(),
            icon: const Icon(Icons.refresh),
            label: const Text('重新连接'),
          ),
        ),
        const Divider(height: 36),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(Icons.verified_outlined, color: color),
          title: Text(
            rms == null ? '尚未加载标定' : '双目 RMS ${rms.toStringAsFixed(3)} px',
          ),
          subtitle: Text(
            rms == null
                ? '无匹配标定时，距离不可用'
                : rms > 2
                ? '误差较高，距离仅供参考'
                : '已加载 320×240 标定，可进行物距测距',
          ),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: OutlinedButton.icon(
            onPressed: c.busy || !c.ready ? null : c.importCalibration,
            icon: const Icon(Icons.file_open_outlined),
            label: const Text('导入标定 JSON'),
          ),
        ),
        const SizedBox(height: 10),
        const Text(
          '在电脑完成标定并导出安卓 JSON，再通过系统文件选择器导入。更换镜头位置或相机后需要重新标定。',
          style: TextStyle(height: 1.7),
        ),
        const Divider(height: 36),
        ValueListenableBuilder(
          valueListenable: c.frame,
          builder: (context, frame, _) => ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(c.modelReady ? Icons.memory : Icons.warning_amber),
            title: const Text('YOLOX-Nano · COCO 80 类'),
            subtitle: Text(c.modelReady ? '离线模型已加载' : '模型尚未就绪，请检查资源或重试初始化'),
          ),
        ),
        OutlinedButton(
          onPressed: c.busy ? null : c.initialize,
          child: const Text('重新加载资源'),
        ),
      ],
    );
  }
}

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key, required this.controller});
  final RangeController controller;
  @override
  Widget build(BuildContext context) {
    final c = controller;
    final s = c.settings;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('测距设置', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 18),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('可靠距离范围'),
          subtitle: Text(
            '${s.minimum.toStringAsFixed(2)} ～ ${s.maximum.toStringAsFixed(2)} m',
          ),
          trailing: const Icon(Icons.edit_outlined),
          onTap: c.busy ? null : () => editRange(context, c),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('识别置信度'),
          trailing: Text('${(s.confidence * 100).round()}%'),
        ),
        ConfidenceSlider(controller: c),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('物体识别框'),
          value: s.boxes,
          onChanged: c.busy ? null : (v) => c.apply(s.copyWith(boxes: v)),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('三点测距标记'),
          value: s.points,
          onChanged: c.busy ? null : (v) => c.apply(s.copyWith(points: v)),
        ),
        const Divider(height: 32),
        const Text('外观'),
        const SizedBox(height: 12),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'system', label: Text('跟随系统')),
            ButtonSegment(value: 'light', label: Text('浅色')),
            ButtonSegment(value: 'dark', label: Text('深色')),
          ],
          selected: {s.theme},
          onSelectionChanged: c.busy
              ? null
              : (v) => c.apply(s.copyWith(theme: v.single)),
        ),
        const SizedBox(height: 24),
        OutlinedButton.icon(
          onPressed: c.busy ? null : () => c.apply(const RangeSettings()),
          icon: const Icon(Icons.restart_alt),
          label: const Text('恢复默认设置'),
        ),
        const Divider(height: 40),
        Text('StereoRange', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 10),
        const Text(
          '平湖技师学院\n陆逸尘（辰渊尘 ChenDusk · @mcxiaochenn）\n周璟雯 · 胡乐毅\n指导教师 张梁',
          style: TextStyle(height: 1.8),
        ),
        const SizedBox(height: 12),
        TextButton(
          onPressed: () =>
              showLicensePage(context: context, applicationName: 'StereoRange'),
          child: const Text('开源许可'),
        ),
        const RepositoryCard(),
      ],
    );
  }
}

/// 拖动时仅更新标签，松手后才保存设置，避免每个移动事件重置处理状态。
class ConfidenceSlider extends StatefulWidget {
  const ConfidenceSlider({super.key, required this.controller});
  final RangeController controller;
  @override
  State<ConfidenceSlider> createState() => _ConfidenceSliderState();
}

class _ConfidenceSliderState extends State<ConfidenceSlider> {
  double? dragging;
  @override
  Widget build(BuildContext context) => Slider(
    value: dragging ?? widget.controller.settings.confidence.clamp(.1, .9),
    min: .1,
    max: .9,
    divisions: 16,
    label:
        '${((dragging ?? widget.controller.settings.confidence) * 100).round()}%',
    onChanged: widget.controller.busy
        ? null
        : (v) => setState(() => dragging = v),
    onChangeEnd: (v) async {
      await widget.controller.apply(
        widget.controller.settings.copyWith(confidence: v),
      );
      if (mounted) setState(() => dragging = null);
    },
  );
}

Future<void> editRange(BuildContext context, RangeController c) async {
  final minimum = TextEditingController(text: c.settings.minimum.toString());
  final maximum = TextEditingController(text: c.settings.maximum.toString());
  String? error;
  final value = await showDialog<RangeSettings>(
    context: context,
    builder: (context) => StatefulBuilder(
      builder: (context, setState) => AlertDialog(
        title: const Text('可靠距离范围'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: minimum,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(labelText: '最近距离（m）'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: maximum,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: InputDecoration(
                labelText: '最远距离（m）',
                errorText: error,
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              try {
                final next = c.settings.copyWith(
                  minimum: double.parse(minimum.text),
                  maximum: double.parse(maximum.text),
                );
                next.validate();
                Navigator.pop(context, next);
              } catch (_) {
                setState(() => error = '请输入有效范围，最远值须大于最近值');
              }
            },
            child: const Text('保存'),
          ),
        ],
      ),
    ),
  );
  // 对话框退场动画仍会访问输入控件，等待其完成后释放。
  await Future<void>.delayed(const Duration(milliseconds: 300));
  minimum.dispose();
  maximum.dispose();
  if (value != null) await c.apply(value);
}

void showHelp(BuildContext context) => showDialog<void>(
  context: context,
  builder: (context) => AlertDialog(
    title: const Text('开始一次测距'),
    content: const SingleChildScrollView(
      child: Text(
        '1. 用 OTG 转接器连接双目相机，允许相机及 USB 访问。\n\n2. 在设备页检查标定；需要时导入电脑导出的 JSON。\n\n3. 将有纹理的物体放入画面，查看识别框和三个距离读数；轻点画面可测量指定位置。\n\n全场景会扫描可靠深度区域；仅识别物体只比较已识别且距离有效的物体。\n\n透明、反光、纯色或遮挡区域可能无法测距。演示数据使用虚拟参数，不代表实测精度。',
        style: TextStyle(height: 1.6),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('知道了'),
      ),
    ],
  ),
);
