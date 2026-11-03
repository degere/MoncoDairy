import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../widgets/common.dart';
import 'sensor_detail_screen.dart';

class CorralDetailScreen extends StatelessWidget {
  final Corral corral;
  const CorralDetailScreen({super.key, required this.corral});

  @override
  Widget build(BuildContext context) {
    final critico = corral.nivelHumedad == Nivel.critico;
    return Scaffold(
      appBar: AppBar(
        title: Text(corral.nombre, style: const TextStyle(fontSize: 16)),
        actions: const [Padding(padding: EdgeInsets.only(right: 16), child: OnlineBadge())],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('${corral.nombre} — ${corral.descripcion}',
              style: const TextStyle(color: AppColors.green, fontWeight: FontWeight.w600)),
          const Text('Actualizado hace 3 seg', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
          const SizedBox(height: 14),
          if (critico) ...[
            AppCard(
              color: AppColors.redSoft,
              borderColor: AppColors.red,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  const Icon(Icons.warning_amber_rounded, color: AppColors.red, size: 20),
                  const SizedBox(width: 6),
                  const Expanded(
                      child: Text('AVISO PREVENTIVO',
                          style: TextStyle(color: AppColors.red, fontWeight: FontWeight.w600))),
                  const Pill('URGENTE', bg: Colors.white, fg: AppColors.red),
                ]),
                const SizedBox(height: 8),
                const Text('Humedad en aumento', style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                  const Text('Nivel actual:', style: TextStyle(fontSize: 12)),
                  Text('${corral.humedad.toStringAsFixed(0)}%', style: const TextStyle(fontWeight: FontWeight.w700)),
                ]),
                const Text('Variación: Subió 8% en las últimas 2 horas', style: TextStyle(fontSize: 12)),
                const SizedBox(height: 8),
                const Row(children: [
                  Icon(Icons.info_outline, size: 16, color: AppColors.red),
                  SizedBox(width: 6),
                  Text('Posible cambio de paja necesario', style: TextStyle(color: AppColors.red, fontSize: 12)),
                ]),
              ]),
            ),
            const SizedBox(height: 12),
          ],
          _MedidaCard(
            icono: Icons.water_drop,
            iconoColor: AppColors.blue,
            titulo: 'HUMEDAD DE LA PAJA',
            pill: critico ? const Pill('Crítico', bg: AppColors.redSoft, fg: AppColors.red) : null,
            valor: '${corral.humedad.toStringAsFixed(0)}%',
            valorColor: nivelColor(corral.nivelHumedad),
            detalle: 'Límite seguro: 65%',
            progreso: corral.humedad,
            color: nivelColor(corral.nivelHumedad),
          ),
          const SizedBox(height: 12),
          _MedidaCard(
            icono: Icons.thermostat,
            iconoColor: AppColors.blue,
            titulo: 'TEMPERATURA',
            pill: corral.temperaturaBaja ? const Pill('Baja', bg: AppColors.blueSoft, fg: AppColors.blue) : null,
            valor: '${corral.temperatura.toStringAsFixed(0)}°C',
            valorColor: AppColors.blue,
            detalle: 'Rango óptimo: 12-18°C',
            progreso: (corral.temperatura / 30 * 100),
            color: AppColors.blue,
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            style: OutlinedButton.styleFrom(
              minimumSize: const Size.fromHeight(52),
              foregroundColor: AppColors.green,
              side: const BorderSide(color: AppColors.green, width: 1.5),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            icon: const Icon(Icons.manage_search),
            label: const Text('Ver detalle del sensor'),
            onPressed: () =>
                Navigator.of(context).push(MaterialPageRoute(builder: (_) => SensorDetailScreen(corral: corral))),
          ),
        ],
      ),
    );
  }
}

class _MedidaCard extends StatelessWidget {
  final IconData icono;
  final Color iconoColor;
  final String titulo;
  final Widget? pill;
  final String valor;
  final Color valorColor;
  final String detalle;
  final double progreso;
  final Color color;

  const _MedidaCard({
    required this.icono,
    required this.iconoColor,
    required this.titulo,
    required this.pill,
    required this.valor,
    required this.valorColor,
    required this.detalle,
    required this.progreso,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icono, size: 18, color: iconoColor),
          const SizedBox(width: 8),
          Expanded(child: Text(titulo, style: const TextStyle(fontSize: 13))),
          if (pill != null) pill!,
        ]),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(valor, style: TextStyle(color: valorColor, fontWeight: FontWeight.w600)),
          Text(detalle, style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
        ]),
        const SizedBox(height: 8),
        LevelBar(value: progreso, color: color),
      ]),
    );
  }
}
