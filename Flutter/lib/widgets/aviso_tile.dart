import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../models/models.dart';
import 'common.dart';

class AvisoTile extends StatelessWidget {
  final Aviso aviso;
  const AvisoTile({super.key, required this.aviso});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: Text(aviso.titulo, style: const TextStyle(fontWeight: FontWeight.w600))),
          const SizedBox(width: 8),
          aviso.pendiente
              ? const Pill('PENDIENTE', bg: AppColors.redSoft, fg: AppColors.red)
              : Pill('RESUELTO — ${aviso.resueltoTexto}', bg: AppColors.greenSoft, fg: AppColors.green),
        ]),
        const SizedBox(height: 6),
        Text(aviso.detalle, style: const TextStyle(fontSize: 13)),
        const SizedBox(height: 6),
        Row(children: [
          const Icon(Icons.schedule, size: 13, color: AppColors.textMuted),
          const SizedBox(width: 4),
          Text(aviso.tiempo, style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
        ]),
      ]),
    );
  }
}
