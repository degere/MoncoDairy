enum Nivel { ok, alerta, critico }

class Corral {
  final int id;
  final String nombre;
  final String descripcion;
  final double humedad;
  final double temperatura;

  const Corral({
    required this.id,
    required this.nombre,
    required this.descripcion,
    required this.humedad,
    required this.temperatura,
  });

  /// Umbrales según el diseño: <=60 ok, <75 alerta, >=75 crítico.
  Nivel get nivelHumedad {
    if (humedad >= 75) return Nivel.critico;
    if (humedad > 60) return Nivel.alerta;
    return Nivel.ok;
  }

  /// Rango óptimo de temperatura: 12–18 °C.
  bool get temperaturaBaja => temperatura < 12;

  // Para cuando conectes Django: factory Corral.fromJson(Map<String, dynamic> j)
}

enum EstadoSensor { activo, inactivo, revisar }

class Sensor {
  final String codigo; // S-H-001
  final String nombre; // Humedad Corral 1
  final EstadoSensor estado;
  const Sensor(this.codigo, this.nombre, this.estado);
}

class Aviso {
  final int id;
  final String titulo;
  final String detalle;
  final String tiempo;
  final bool pendiente;
  final String? resueltoTexto;

  const Aviso({
    required this.id,
    required this.titulo,
    required this.detalle,
    required this.tiempo,
    required this.pendiente,
    this.resueltoTexto,
  });
}
