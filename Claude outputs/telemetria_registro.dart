/// Un registro de /telemetria/$registro_id ya validado.
class TelemetriaRegistro {
  final String id;
  final String dispositivo;
  final double temperaturaC;
  final double humedadPct;

  const TelemetriaRegistro({
    required this.id,
    required this.dispositivo,
    required this.temperaturaC,
    required this.humedadPct,
  });

  static const double tempMin = -20, tempMax = 70;
  static const double humMin = 0, humMax = 100;

  /// Devuelve null si el registro esta incompleto, mal tipado o fuera de rango.
  /// RTDB entrega `int` para numeros enteros, por eso se lee como `num`.
  static TelemetriaRegistro? tryParse(String id, Object? raw) {
    if (raw is! Map) return null;
    final lecturas = raw['lecturas_crudas'];
    if (lecturas is! Map) return null;

    final t = lecturas['temperatura_celsius'];
    final h = lecturas['humedad_ambiente_pct'];
    final disp = raw['dispositivo'];
    if (t is! num || h is! num || disp is! String) return null;

    final temp = t.toDouble();
    final hum = h.toDouble();
    if (temp.isNaN || hum.isNaN) return null;
    if (temp < tempMin || temp > tempMax) return null;
    if (hum < humMin || hum > humMax) return null;

    return TelemetriaRegistro(
      id: id,
      dispositivo: disp,
      temperaturaC: temp,
      humedadPct: hum,
    );
  }
}
