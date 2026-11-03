import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../data/repository.dart';
import '../models/models.dart';
import '../widgets/common.dart';

class SensorDetailScreen extends StatelessWidget {
  final Corral corral;
  const SensorDetailScreen({super.key, required this.corral});

  @override
  Widget build(BuildContext context) {
    final critico = corral.nivelHumedad == Nivel.critico;
    final codigo = 'S-H-${corral.id.toString().padLeft(3, '0')}';
    return Scaffold(
      appBar: AppBar(title: const Text('Sensor de Humedad', style: TextStyle(fontSize: 16))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Flexible(
              child: Text('${corral.nombre} — ${corral.descripcion}',
                  style: const TextStyle(color: AppColors.green, fontWeight: FontWeight.w600)),
            ),
            const Pill('Activo', bg: AppColors.greenSoft, fg: AppColors.green),
          ]),
          const SizedBox(height: 12),
          AppCard(
            borderColor: critico ? AppColors.red : AppColors.border,
            borderWidth: critico ? 2 : 1,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                const Text('Humedad actual', style: TextStyle(fontSize: 13)),
                if (critico) const Pill('ALERTA CRÍTICA', bg: AppColors.redSoft, fg: AppColors.red),
              ]),
              Text.rich(TextSpan(children: [
                TextSpan(
                    text: '${corral.humedad.toStringAsFixed(0)}%',
                    style: TextStyle(fontSize: 56, fontWeight: FontWeight.w800, color: nivelColor(corral.nivelHumedad))),
                TextSpan(
                    text: ' HR',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: nivelColor(corral.nivelHumedad))),
              ])),
              const Row(children: [
                Icon(Icons.schedule, size: 14, color: AppColors.textMuted),
                SizedBox(width: 4),
                Text('Última lectura: hace 3 seg', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
              ]),
            ]),
          ),
          const SizedBox(height: 12),
          AppCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                const Text('Últimas 24 horas', style: TextStyle(fontWeight: FontWeight.w600)),
                const Pill('Límites: 60% - 80%', bg: AppColors.orangeSoft, fg: Color(0xFF8A5A00)),
              ]),
              const SizedBox(height: 12),
              SizedBox(
                height: 180,
                child: FutureBuilder<List<double>>(
                  future: Repository.instance.getHumedad24h(corral.id),
                  builder: (_, snap) {
                    if (!snap.hasData) return const Center(child: CircularProgressIndicator());
                    return CustomPaint(size: Size.infinite, painter: _ChartPainter(snap.data!));
                  },
                ),
              ),
            ]),
          ),
          const SizedBox(height: 12),
          AppCard(
            child: Column(children: [
              Row(children: [
                Expanded(child: _dato('ID del sensor', codigo)),
                Expanded(child: _dato('Batería', '87%')),
              ]),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(child: _dato('Señal de enlace', 'Fuerte')),
                Expanded(child: _dato('Última conexión', '14:32')),
              ]),
            ]),
          ),
        ],
      ),
    );
  }

  Widget _dato(String label, String valor) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
        Text(valor, style: const TextStyle(fontWeight: FontWeight.w600)),
      ]);
}

/// Gráfico de línea simple (eje Y 0–100 %) con líneas de límite en 60% y 80%.
class _ChartPainter extends CustomPainter {
  final List<double> datos;
  _ChartPainter(this.datos);

  @override
  void paint(Canvas canvas, Size size) {
    const left = 30.0, bottom = 18.0;
    final w = size.width - left;
    final h = size.height - bottom;
    double y(double v) => h - (v.clamp(0, 100) / 100) * h;

    final grid = Paint()
      ..color = const Color(0xFFE6E6E6)
      ..strokeWidth = 1;
    for (final v in [0, 20, 40, 60, 80, 100]) {
      canvas.drawLine(Offset(left, y(v.toDouble())), Offset(size.width, y(v.toDouble())), grid);
      _text(canvas, '$v%', Offset(0, y(v.toDouble()) - 6), 9, AppColors.textMuted);
    }

    // Límites punteados
    _dashed(canvas, Offset(left, y(80)), Offset(size.width, y(80)), AppColors.red);
    _dashed(canvas, Offset(left, y(60)), Offset(size.width, y(60)), AppColors.orange);

    // Etiquetas de horas
    const horas = ['00:00', '06:00', '12:00', '18:00', '24:00'];
    for (var i = 0; i < horas.length; i++) {
      _text(canvas, horas[i], Offset(left + w * i / 4 - 12, h + 4), 9, AppColors.textMuted);
    }

    // Línea de datos
    final path = Path();
    for (var i = 0; i < datos.length; i++) {
      final p = Offset(left + w * i / (datos.length - 1), y(datos[i]));
      i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = AppColors.green
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );
    canvas.drawCircle(Offset(size.width, y(datos.last)), 4, Paint()..color = AppColors.red);
  }

  void _dashed(Canvas c, Offset a, Offset b, Color color) {
    final p = Paint()
      ..color = color
      ..strokeWidth = 1.2;
    for (double x = a.dx; x < b.dx; x += 8) {
      c.drawLine(Offset(x, a.dy), Offset((x + 4).clamp(a.dx, b.dx), a.dy), p);
    }
  }

  void _text(Canvas c, String s, Offset o, double size, Color color) {
    final tp = TextPainter(
      text: TextSpan(text: s, style: TextStyle(fontSize: size, color: color)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(c, o);
  }

  @override
  bool shouldRepaint(covariant _ChartPainter old) => old.datos != datos;
}
