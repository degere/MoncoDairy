import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../models/models.dart';

Color nivelColor(Nivel n) => switch (n) {
      Nivel.ok => AppColors.greenLight,
      Nivel.alerta => AppColors.orange,
      Nivel.critico => AppColors.red,
    };

class AppCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final Color? borderColor;
  final double borderWidth;
  final Color? color;
  final VoidCallback? onTap;

  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(14),
    this.borderColor,
    this.borderWidth = 1,
    this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color ?? AppColors.card,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: borderColor ?? AppColors.border, width: borderWidth),
          ),
          child: child,
        ),
      ),
    );
  }
}

class LevelBar extends StatelessWidget {
  final double value; // 0..100
  final Color color;
  const LevelBar({super.key, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(6),
      child: LinearProgressIndicator(
        value: (value / 100).clamp(0.0, 1.0),
        minHeight: 8,
        backgroundColor: const Color(0xFFE6E6E6),
        valueColor: AlwaysStoppedAnimation(color),
      ),
    );
  }
}

class Pill extends StatelessWidget {
  final String text;
  final Color bg;
  final Color fg;
  const Pill(this.text, {super.key, required this.bg, required this.fg});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Text(text, style: TextStyle(color: fg, fontSize: 11, fontWeight: FontWeight.w700)),
    );
  }
}

class OnlineBadge extends StatelessWidget {
  final String text;
  const OnlineBadge({super.key, this.text = 'En línea'});

  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      const Icon(Icons.circle, size: 8, color: AppColors.green),
      const SizedBox(width: 6),
      Text(text, style: const TextStyle(color: AppColors.green, fontSize: 12, fontWeight: FontWeight.w600)),
    ]);
  }
}
