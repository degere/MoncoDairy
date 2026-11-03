import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../data/repository.dart';
import '../models/models.dart';
import '../widgets/common.dart';

class SensoresScreen extends StatelessWidget {
  const SensoresScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Sensor>>(
      future: Repository.instance.getSensores(),
      builder: (_, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final sensores = snap.data!;
        final ok = sensores.where((s) => s.estado == EstadoSensor.activo).length;
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 16, 16, 4),
            child: Text('Estado de Sensores',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.green)),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('${sensores.length} sensores instalados', style: const TextStyle(fontWeight: FontWeight.w600)),
              Pill('$ok OK', bg: const Color(0xFFEDEDED), fg: Colors.black87),
            ]),
          ),
          Expanded(
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              itemCount: sensores.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (_, i) => _SensorTile(sensor: sensores[i]),
            ),
          ),
        ]);
      },
    );
  }
}

class _SensorTile extends StatelessWidget {
  final Sensor sensor;
  const _SensorTile({required this.sensor});

  @override
  Widget build(BuildContext context) {
    final revisar = sensor.estado == EstadoSensor.revisar;
    return AppCard(
      color: revisar ? AppColors.orangeSoft : null,
      borderColor: revisar ? AppColors.orange : null,
      borderWidth: revisar ? 1.5 : 1,
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(sensor.codigo, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
            Text(sensor.nombre, style: const TextStyle(fontWeight: FontWeight.w600)),
          ]),
        ),
        switch (sensor.estado) {
          EstadoSensor.activo => const OnlineBadge(text: 'Activo'),
          EstadoSensor.inactivo => const Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.circle_outlined, size: 10, color: AppColors.textMuted),
              SizedBox(width: 6),
              Text('Inactivo', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
            ]),
          EstadoSensor.revisar => const Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.circle, size: 10, color: AppColors.orange),
              SizedBox(width: 6),
              Text('Revisar',
                  style: TextStyle(fontSize: 12, color: AppColors.orange, fontWeight: FontWeight.w700)),
            ]),
        },
      ]),
    );
  }
}
