import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../data/repository.dart';
import '../models/models.dart';
import '../widgets/common.dart';
import 'corral_detail_screen.dart';

class CorralesScreen extends StatelessWidget {
  final String usuario;
  const CorralesScreen({super.key, required this.usuario});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Hola, $usuario', style: const TextStyle(fontWeight: FontWeight.w600)),
              const OnlineBadge(),
            ],
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, 0),
          child: Text('Selecciona un Corral',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.green)),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 2, 16, 10),
          child: Text('20 corrales monitoreados', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
        ),
        Expanded(
          child: FutureBuilder<List<Corral>>(
            future: Repository.instance.getCorrales(),
            builder: (context, snap) {
              if (!snap.hasData) return const Center(child: CircularProgressIndicator());
              final corrales = snap.data!;
              return GridView.builder(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  mainAxisSpacing: 10,
                  crossAxisSpacing: 10,
                  childAspectRatio: 1.35,
                ),
                itemCount: corrales.length,
                itemBuilder: (_, i) => _CorralCard(corral: corrales[i]),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _CorralCard extends StatelessWidget {
  final Corral corral;
  const _CorralCard({required this.corral});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CorralDetailScreen(corral: corral))),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(corral.nombre,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.green)),
          _fila('Humedad', '${corral.humedad.toStringAsFixed(0)}%'),
          _fila('Temp', '${corral.temperatura.toStringAsFixed(0)}°C'),
          LevelBar(value: corral.humedad, color: nivelColor(corral.nivelHumedad)),
        ],
      ),
    );
  }

  Widget _fila(String label, String valor) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
        Text(valor, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
      ],
    );
  }
}
