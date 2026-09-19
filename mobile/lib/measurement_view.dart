import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'session.dart';

const pointColors = {
  'nearest': Color(0xffff865d),
  'center': Color(0xff60e1e0),
  'farthest': Color(0xffb1a3ff),
};
const pointNames = {'nearest': '最近', 'center': '中心', 'farthest': '最远'};
String distanceLabel(double? value) =>
    value == null ? '--' : value.toStringAsFixed(2);

class MeasurementView extends StatelessWidget {
  const MeasurementView({super.key, required this.controller});
  final RangeController controller;
  @override
  Widget build(BuildContext context) => ValueListenableBuilder<FrameData>(
    valueListenable: controller.frame,
    builder: (context, frame, _) => LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        final scale = math.min(size.width / 320, size.height / 240);
        final content = Rect.fromLTWH(
          (size.width - 320 * scale) / 2,
          (size.height - 240 * scale) / 2,
          320 * scale,
          240 * scale,
        );
        return ClipRRect(
          borderRadius: BorderRadius.circular(24),
          child: ColoredBox(
            color: const Color(0xff101c24),
            child: Stack(
              children: [
                if (frame.id > 0 &&
                    controller.running &&
                    controller.textureId != null)
                  Positioned.fromRect(
                    rect: content,
                    child: Texture(textureId: controller.textureId!),
                  )
                else
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(
                            Icons.view_in_ar_rounded,
                            size: 54,
                            color: Color(0xff9cd9cf),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            controller.status == '连接中'
                                ? '正在连接双目相机'
                                : '看见物体，也看见距离',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'USB 双目相机 · 完全离线运行',
                            style: TextStyle(color: Colors.white70),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (frame.id > 0 && controller.running && controller.view != 1)
                  Positioned.fill(
                    child: IgnorePointer(
                      child: CustomPaint(
                        painter: MeasurementPainter(
                          frame,
                          content,
                          controller.settings,
                        ),
                      ),
                    ),
                  ),
                Positioned.fill(
                  child: GestureDetector(
                    behavior: HitTestBehavior.translucent,
                    onTapUp: (details) {
                      final p = details.localPosition;
                      if (content.contains(p)) {
                        controller.sample(
                          ((p.dx - content.left) / scale).floor(),
                          ((p.dy - content.top) / scale).floor(),
                        );
                      }
                    },
                  ),
                ),
                Positioned(
                  left: 12,
                  top: 12,
                  child: _Badge(
                    label: controller.demo ? '模拟演示' : controller.status,
                    icon: controller.demo
                        ? Icons.science_outlined
                        : Icons.sensors_rounded,
                  ),
                ),
                Positioned(
                  right: 8,
                  top: 8,
                  child: IconButton.filledTonal(
                    tooltip: controller.fullscreen ? '退出全屏' : '全屏',
                    onPressed: controller.toggleFullscreen,
                    icon: Icon(
                      controller.fullscreen
                          ? Icons.fullscreen_exit
                          : Icons.fullscreen,
                    ),
                  ),
                ),
                if (controller.tapReading != null)
                  Positioned(
                    left: 12,
                    right: 12,
                    bottom: 12,
                    child: _Badge(
                      label: controller.tapReading!,
                      icon: Icons.touch_app_outlined,
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    ),
  );
}

class _Badge extends StatelessWidget {
  const _Badge({required this.label, required this.icon});
  final String label;
  final IconData icon;
  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: const Color(0xdd17252d),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: Colors.white70),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              label,
              style: const TextStyle(color: Colors.white, fontSize: 12),
            ),
          ),
        ],
      ),
    ),
  );
}

class MeasurementPainter extends CustomPainter {
  MeasurementPainter(this.frame, this.viewport, this.settings);
  final FrameData frame;
  final Rect viewport;
  final RangeSettings settings;
  Offset xy(num x, num y) => Offset(
    viewport.left + x * viewport.width / 320,
    viewport.top + y * viewport.height / 240,
  );
  void label(Canvas canvas, String text, Offset position, Color color) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
      textDirection: TextDirection.ltr,
      maxLines: 2,
    )..layout(maxWidth: math.max(1, viewport.width - 12));
    final x = position.dx.clamp(
      viewport.left + 4,
      math.max(viewport.left + 4, viewport.right - tp.width - 8),
    );
    final y = position.dy.clamp(
      viewport.top + 4,
      math.max(viewport.top + 4, viewport.bottom - tp.height - 8),
    );
    final rect = Rect.fromLTWH(x - 3, y - 2, tp.width + 6, tp.height + 4);
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(4)),
      Paint()..color = const Color(0xdd101c24),
    );
    tp.paint(canvas, Offset(x.toDouble(), y.toDouble()));
  }

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.clipRect(viewport);
    if (settings.boxes) {
      for (final d in frame.detections) {
        final b = (d['bbox'] as List).cast<num>();
        final rect = Rect.fromPoints(xy(b[0], b[1]), xy(b[2], b[3]));
        canvas.drawRect(
          rect,
          Paint()
            ..color = const Color(0xff91e5b7)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.5,
        );
        final z = (d['distance_m'] as num?)?.toDouble();
        label(
          canvas,
          '${d['label']} | ${((d['confidence'] as num) * 100).round()}% | ${z == null ? '距离不可用' : '${z.toStringAsFixed(2)} m'}',
          rect.topLeft + const Offset(3, 3),
          Colors.white,
        );
      }
    }
    if (settings.points) {
      for (final p in frame.points) {
        final kind = p['kind'] as String;
        final center = xy(p['x'] as num, p['y'] as num);
        final color = pointColors[kind] ?? Colors.white;
        final paint = Paint()
          ..color = color
          ..strokeWidth = 2;
        canvas.drawCircle(center, 7, paint..style = PaintingStyle.stroke);
        canvas.drawLine(
          center - const Offset(12, 0),
          center + const Offset(12, 0),
          paint,
        );
        canvas.drawLine(
          center - const Offset(0, 12),
          center + const Offset(0, 12),
          paint,
        );
        label(
          canvas,
          '${pointNames[kind]} ${(p['distance_m'] as num).toStringAsFixed(2)} m',
          center + const Offset(12, 12),
          color,
        );
      }
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant MeasurementPainter old) =>
      old.frame != frame ||
      old.viewport != viewport ||
      old.settings != settings;
}

class DistanceReadings extends StatelessWidget {
  const DistanceReadings({super.key, required this.frame});
  final FrameData frame;
  @override
  Widget build(BuildContext context) => Row(
    children: [
      for (final kind in pointNames.keys)
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 3),
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainer,
                borderRadius: BorderRadius.circular(18),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 14,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          kind == 'center'
                              ? Icons.center_focus_strong
                              : Icons.adjust,
                          size: 15,
                          color: pointColors[kind],
                        ),
                        const SizedBox(width: 6),
                        Text(
                          pointNames[kind]!,
                          style: Theme.of(context).textTheme.labelLarge,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.baseline,
                        textBaseline: TextBaseline.alphabetic,
                        children: [
                          Text(
                            distanceLabel(frame.distance(kind)),
                            style: Theme.of(context).textTheme.headlineMedium
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(width: 4),
                          const Text('m'),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
    ],
  );
}
