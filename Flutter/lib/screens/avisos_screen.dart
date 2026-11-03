import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../data/repository.dart';
import '../models/models.dart';
import '../widgets/aviso_tile.dart';

/// Avisos activos (pendientes). El Figma aún no incluye esta pantalla: es una versión base.
class AvisosScreen extends StatelessWidget {
  const AvisosScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Padding(
        padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: Text('Avisos activos',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.green)),
      ),
      Expanded(
        child: FutureBuilder<List<Aviso>>(
          future: Repository.instance.getAvisos(),
          builder: (_, snap) {
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            final pendientes = snap.data!.where((a) => a.pendiente).toList();
            if (pendientes.isEmpty) {
              return const Center(child: Text('No hay avisos pendientes.'));
            }
            return ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              itemCount: pendientes.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) => AvisoTile(aviso: pendientes[i]),
            );
          },
        ),
      ),
    ]);
  }
}
