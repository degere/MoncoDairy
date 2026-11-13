import 'dart:math';
import '../models/models.dart';

/// Contrato de datos de la app. Hoy lo implementa [MockRepository].
/// Más adelante crea `ApiRepository` (Django: usuarios, historial, cache offline)
/// y/o `FirebaseRepository` (lecturas de sensores en tiempo real) sin tocar la UI.
abstract class Repository {
  static Repository instance = MockRepository();

  Future<bool> login(String usuario, String pin);
  Future<List<Corral>> getCorrales();
  Future<List<Sensor>> getSensores();
  Future<List<Aviso>> getAvisos();

  /// Lecturas de humedad de las últimas 24 h (25 puntos, una por hora).
  Future<List<double>> getHumedad24h(int corralId);
}

class MockRepository implements Repository {
  static const _hum = [82, 65, 85, 70, 55, 78, 62, 90, 48, 73, 80, 58, 88, 66, 52, 76, 83, 60, 68, 79];
  static const _temp = [9, 12, 8, 11, 14, 10, 13, 7, 15, 11, 9, 13, 8, 12, 14, 10, 9, 13, 12, 10];

  @override
  Future<bool> login(String usuario, String pin) async {
    await Future.delayed(const Duration(milliseconds: 400));
    return usuario.trim().isNotEmpty && pin.length == 6; // TODO: validar contra Django
  }

  @override
  Future<List<Corral>> getCorrales() async {
    return List.generate(20, (i) {
      return Corral(
        id: i + 1,
        nombre: 'Corral ${i + 1}',
        descripcion: i == 2 ? 'Galpón de partos' : 'Galpón ${i + 1}',
        humedad: _hum[i].toDouble(),
        temperatura: _temp[i].toDouble(),
      );
    });
  }

  @override
  Future<List<Sensor>> getSensores() async {
    final lista = <Sensor>[];
    for (var i = 1; i <= 20; i++) {
      final n = i.toString().padLeft(3, '0');
      lista.add(Sensor(
        'S-H-$n',
        'Humedad Corral $i',
        i == 4 || i == 16
            ? EstadoSensor.inactivo
            : i == 8
                ? EstadoSensor.revisar
                : EstadoSensor.activo,
      ));
      lista.add(Sensor('S-T-$n', 'Temperatura Corral $i', EstadoSensor.activo));
    }
    return lista;
  }

  @override
  Future<List<Aviso>> getAvisos() async {
    return const [
      Aviso(id: 1, titulo: 'Corral 3 — Humedad alta', detalle: 'Humedad 85% — Camas húmedas', tiempo: 'Hace 15 minutos', pendiente: true),
      Aviso(id: 2, titulo: 'Corral 8 — Humedad alta', detalle: 'Humedad 90% — Camas muy húmedas', tiempo: 'Hace 30 minutos', pendiente: true),
      Aviso(id: 3, titulo: 'Corral 13 — Humedad alta', detalle: 'Humedad 88% — Camas húmedas', tiempo: 'Hace 1 hora', pendiente: true),
      Aviso(id: 4, titulo: 'Corral 7 — Humedad alta', detalle: 'Humedad 82% — Camas húmedas', tiempo: 'Hace 2 horas', pendiente: false, resueltoTexto: 'Hace 1 hora'),
      Aviso(id: 5, titulo: 'Corral 17 — Humedad alta', detalle: 'Humedad 83% — Camas húmedas', tiempo: 'Hace 4 horas', pendiente: false, resueltoTexto: 'Hace 3 horas'),
      Aviso(id: 6, titulo: 'Corral 11 — Humedad alta', detalle: 'Humedad 80% — Camas húmedas', tiempo: 'Hace 6 horas', pendiente: false, resueltoTexto: 'Hace 5 horas'),
      Aviso(id: 7, titulo: 'Corral 12 — Temperatura baja', detalle: 'Temperatura 8°C — Camas frías', tiempo: 'Ayer 06:30', pendiente: false, resueltoTexto: 'Ayer 08:15'),
      Aviso(id: 8, titulo: 'Corral 3 — Humedad en aumento', detalle: 'Subió de 70% a 84% en 2 horas', tiempo: 'Ayer 14:20', pendiente: false, resueltoTexto: 'Ayer 16:00'),
      Aviso(id: 9, titulo: 'Corral 19 — Humedad alta', detalle: 'Humedad 79% — Camas húmedas', tiempo: 'Ayer 18:45', pendiente: false, resueltoTexto: 'Ayer 20:30'),
      Aviso(id: 10, titulo: 'Corral 5 — Temperatura baja', detalle: 'Temperatura 9°C — Camas frías', tiempo: 'Hace 2 días', pendiente: false, resueltoTexto: 'Hace 2 días'),
    ];
  }

  @override
  Future<List<double>> getHumedad24h(int corralId) async {
    final actual = _hum[corralId - 1].toDouble();
    return List.generate(25, (i) => actual - 6 + 6 * (i / 24) + sin(i / 3 + corralId));
  }
}
