import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../data/repository.dart';
import '../models/models.dart';
import '../widgets/aviso_tile.dart';

class HistorialScreen extends StatefulWidget {
  const HistorialScreen({super.key});

  @override
  State<HistorialScreen> createState() => _HistorialScreenState();
}

class _HistorialScreenState extends State<HistorialScreen> {
  int _filtro = 0; // 0 todos, 1 pendientes, 2 resueltos
  static const _filtros = ['Todos', 'Pendientes', 'Resueltos'];

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Padding(
        padding: EdgeInsets.fromLTRB(16, 16, 16, 4),
        child: Text('Historial de Avisos',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.green)),
      ),
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
        child: Wrap(
          spacing: 8,
          children: List.generate(_filtros.length, (i) {
            return ChoiceChip(
              label: Text(_filtros[i]),
              selected: _filtro == i,
              selectedColor: AppColors.green,
              labelStyle: TextStyle(color: _filtro == i ? Colors.white : Colors.black87),
              showCheckmark: false,
              onSelected: (_) => setState(() => _filtro = i),
            );
          }),
        ),
      ),
      Expanded(
        child: FutureBuilder<List<Aviso>>(
          future: Repository.instance.getAvisos(),
          builder: (_, snap) {
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            final lista = snap.data!.where((a) {
              if (_filtro == 1) return a.pendiente;
              if (_filtro == 2) return !a.pendiente;
              return true;
            }).toList();
            return ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              itemCount: lista.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) => AvisoTile(aviso: lista[i]),
            );
          },
        ),
      ),
    ]);
  }
}
