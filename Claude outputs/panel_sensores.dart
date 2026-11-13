import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../data/telemetria_registro.dart';
import '../data/telemetria_repository.dart';

/// Reemplaza al "corral de testeo". Escucha Firebase en tiempo real.
///
/// Para usar TU diseno, pasa [contenidoBuilder] y construye ahi tus tarjetas
/// con los valores reales (registro.temperaturaC / registro.humedadPct).
class PanelSensores extends StatefulWidget {
  const PanelSensores({super.key, this.contenidoBuilder});

  final Widget Function(BuildContext context, TelemetriaRegistro registro)?
      contenidoBuilder;

  @override
  State<PanelSensores> createState() => _PanelSensoresState();
}

class _PanelSensoresState extends State<PanelSensores> {
  // Se crean una sola vez: crearlos en build() reabriria la suscripcion.
  late final Stream<TelemetriaRegistro?> _datos;
  late final Stream<bool> _conexion;

  @override
  void initState() {
    super.initState();
    final repo = context.read<TelemetriaRepository>();
    _datos = repo.ultimoRegistro();
    _conexion = repo.conectado();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        StreamBuilder<bool>(
          stream: _conexion,
          builder: (context, s) {
            if (s.data == false) {
              return Container(
                width: double.infinity,
                padding: const EdgeInsets.all(8),
                color: Colors.orange.shade700,
                child: const Text(
                  'Sin conexion. Mostrando el ultimo dato guardado.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white),
                ),
              );
            }
            return const SizedBox.shrink();
          },
        ),
        Expanded(
          child: StreamBuilder<TelemetriaRegistro?>(
            stream: _datos,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return _Mensaje(
                  icono: Icons.cloud_off,
                  texto: 'No se pudo leer la telemetria.\n${snapshot.error}',
                );
              }
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              final registro = snapshot.data;
              if (registro == null) {
                return const _Mensaje(
                  icono: Icons.sensors_off,
                  texto: 'Sin lecturas validas todavia.',
                );
              }
              final builder = widget.contenidoBuilder;
              return builder != null
                  ? builder(context, registro)
                  : _ContenidoPorDefecto(registro: registro);
            },
          ),
        ),
      ],
    );
  }
}

class _ContenidoPorDefecto extends StatelessWidget {
  const _ContenidoPorDefecto({required this.registro});
  final TelemetriaRegistro registro;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Dispositivo: ${registro.dispositivo}',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        _Tarjeta(
          icono: Icons.thermostat,
          titulo: 'Temperatura',
          valor: '${registro.temperaturaC.toStringAsFixed(1)} °C',
        ),
        _Tarjeta(
          icono: Icons.water_drop,
          titulo: 'Humedad',
          valor: '${registro.humedadPct.toStringAsFixed(0)} %',
        ),
      ],
    );
  }
}

class _Tarjeta extends StatelessWidget {
  const _Tarjeta(
      {required this.icono, required this.titulo, required this.valor});
  final IconData icono;
  final String titulo;
  final String valor;

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: Icon(icono, size: 32),
          title: Text(titulo),
          trailing: Text(valor, style: Theme.of(context).textTheme.headlineSmall),
        ),
      );
}

class _Mensaje extends StatelessWidget {
  const _Mensaje({required this.icono, required this.texto});
  final IconData icono;
  final String texto;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icono, size: 48),
            const SizedBox(height: 8),
            Text(texto, textAlign: TextAlign.center),
          ]),
        ),
      );
}
