import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../data/repository.dart';
import '../models/models.dart';
import '../widgets/common.dart';
import 'corral_detail_screen.dart';

class CorralesScreen extends StatefulWidget {
  final String usuario;
  const CorralesScreen({super.key, required this.usuario});

  @override
  State<CorralesScreen> createState() => _CorralesScreenState();
}

class _CorralesScreenState extends State<CorralesScreen> {
  // El stream se crea una sola vez: crearlo en build() reabriria la suscripcion en cada rebuild.
  late Stream<List<Corral>> _corrales = Repository.instance.watchCorrales();

  void _reintentar() => setState(() => _corrales = Repository.instance.watchCorrales());

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
              Text('Hola, ${widget.usuario}', style: const TextStyle(fontWeight: FontWeight.w600)),
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
          child: StreamBuilder<List<Corral>>(
            stream: _corrales,
            builder: (context, snap) {
              if (snap.hasError) {
                return _ErrorConexion(error: snap.error!, onReintentar: _reintentar);
              }
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

class _ErrorConexion extends StatelessWidget {
  final Object error;
  final VoidCallback onReintentar;
  const _ErrorConexion({required this.error, required this.onReintentar});

  @override
  Widget build(BuildContext context) {
    final sinPermiso = error.toString().contains('permission-denied');
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 48, color: AppColors.textMuted),
            const SizedBox(height: 8),
            Text(
              sinPermiso
                  ? 'Sin permiso para leer los sensores. Revisa las reglas de Firebase y el inicio de sesión.'
                  : 'No se pudo conectar con los sensores.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            OutlinedButton(onPressed: onReintentar, child: const Text('Reintentar')),
          ],
        ),
      ),
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
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(corral.nombre,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.green)),
              if (corral.enVivo) const Pill('EN VIVO', bg: AppColors.greenSoft, fg: AppColors.green),
            ],
          ),
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
