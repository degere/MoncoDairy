import 'package:flutter/material.dart';
import '../core/theme.dart';
import 'avisos_screen.dart';
import 'corrales_screen.dart';
import 'historial_screen.dart';
import 'sensores_screen.dart';

class HomeShell extends StatefulWidget {
  final String usuario;
  const HomeShell({super.key, required this.usuario});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _tabs = [
    (Icons.grid_view_rounded, 'Corrales'),
    (Icons.warning_amber_rounded, 'Avisos'),
    (Icons.thermostat_rounded, 'Sensores'),
    (Icons.history_rounded, 'Historial'),
  ];

  @override
  Widget build(BuildContext context) {
    final pages = [
      CorralesScreen(usuario: widget.usuario),
      const AvisosScreen(),
      const SensoresScreen(),
      const HistorialScreen(),
    ];

    return Scaffold(
      body: SafeArea(child: IndexedStack(index: _index, children: pages)),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: AppColors.border))),
        padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
        child: SafeArea(
          top: false,
          child: Row(
            children: List.generate(_tabs.length, (i) {
              final sel = i == _index;
              return Expanded(
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => setState(() => _index = i),
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    decoration: BoxDecoration(
                      color: sel ? AppColors.green : Colors.transparent,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Icon(_tabs[i].$1, color: sel ? Colors.white : AppColors.textMuted, size: 22),
                      const SizedBox(height: 2),
                      Text(_tabs[i].$2,
                          style: TextStyle(fontSize: 11, color: sel ? Colors.white : AppColors.textMuted)),
                    ]),
                  ),
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}
