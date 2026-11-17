import 'dart:async';
import 'dart:convert';
import 'dart:io' show HttpDate;

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../models/models.dart';
import 'repository.dart';

/// URL base de Django. Se cambia al compilar:
///   emulador:     --dart-define=API_BASE_URL=http://10.0.2.2:8000   (valor por defecto)
///   celular real: --dart-define=API_BASE_URL=http://<IP del PC>:8000
const String kApiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');

/// Cada cuanto la app vuelve a consultar a Django.
const Duration kIntervaloConsulta = Duration(seconds: 30);

/// Una lectura se considera "en vivo" si tiene a lo sumo estos segundos (3 intervalos del sensor).
const int kSegundosEnVivo = 90;

/// Error de la API con un mensaje listo para mostrar al usuario.
class ApiException implements Exception {
  final String mensaje;
  final int? statusCode;
  const ApiException(this.mensaje, {this.statusCode});

  @override
  String toString() => mensaje;
}

/// Datos desde el backend Django del equipo: login real con PIN + JWT, corrales
/// (`/api/corrales/`), alertas (`/api/alertas/`) e historial. La app NO habla con
/// Firebase: Django lee `/telemetria` y la app solo consulta a Django.
/// Lo que aun no esta conectado (lista de sensores) sigue viniendo de [MockRepository].
class ApiRepository extends MockRepository {
  ApiRepository({http.Client? cliente, String? baseUrl, Duration? intervalo})
      : _cliente = cliente ?? http.Client(),
        _baseUrl = (baseUrl ?? kApiBaseUrl).replaceAll(RegExp(r'/+$'), ''),
        _intervalo = intervalo ?? kIntervaloConsulta;

  final http.Client _cliente;
  final String _baseUrl;
  final Duration _intervalo;
  static const Duration _timeout = Duration(seconds: 10);

  // Tokens solo en memoria.
  String? _access;
  String? _refresh;
  Future<bool>? _renovando;
  String? _ultimoError;

  @override
  String? get ultimoErrorLogin => _ultimoError;

  Uri _uri(String ruta) => Uri.parse('$_baseUrl$ruta');

  // ---------------------------------------------------------------- login

  @override
  Future<bool> login(String usuario, String pin) async {
    _ultimoError = null;
    _access = null;
    _refresh = null;
    try {
      final r = await _cliente
          .post(
            _uri('/api/auth/login-pin/'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode({'email': usuario.trim(), 'pin': pin}),
          )
          .timeout(_timeout);
      final cuerpo = _decodificar(r);
      final tokens = cuerpo is Map ? cuerpo['tokens'] : null;
      if (r.statusCode == 200 && tokens is Map && tokens['access'] is String) {
        _access = tokens['access'] as String;
        _refresh = tokens['refresh'] is String ? tokens['refresh'] as String : null;
        return true;
      }
      _ultimoError = _mensajeDeError(cuerpo, r.statusCode);
      return false;
    } on TimeoutException {
      _ultimoError = 'El servidor no respondió ($_baseUrl).';
      return false;
    } catch (e) {
      debugPrint('Login: sin conexión con Django: $e');
      _ultimoError = 'No se pudo conectar con el servidor ($_baseUrl).';
      return false;
    }
  }

  /// Pide un par de tokens nuevo con el refresh. Varias consultas simultaneas
  /// comparten una sola renovacion.
  Future<bool> _renovar() => _renovando ??= _renovarSinCompartir().whenComplete(() => _renovando = null);

  Future<bool> _renovarSinCompartir() async {
    final refresh = _refresh;
    if (refresh == null) return false;
    try {
      final r = await _cliente
          .post(
            _uri('/api/auth/token/refresh/'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode({'refresh': refresh}),
          )
          .timeout(_timeout);
      final cuerpo = _decodificar(r);
      if (r.statusCode == 200 && cuerpo is Map && cuerpo['access'] is String) {
        _access = cuerpo['access'] as String;
        _refresh = cuerpo['refresh'] is String ? cuerpo['refresh'] as String : refresh;
        return true;
      }
    } catch (e) {
      debugPrint('No se pudo renovar la sesión: $e');
    }
    _access = null;
    _refresh = null;
    return false;
  }

  // --------------------------------------------------------------- corrales

  @override
  Stream<List<Corral>> watchCorrales() => _sondeo(_corralesDesdeApi);

  @override
  Stream<Corral> watchCorral(Corral corral) => _sondeo(() async {
        final lista = await _corralesDesdeApi();
        return lista.firstWhere((c) => c.id == corral.id, orElse: () => corral);
      });

  Future<List<Corral>> _corralesDesdeApi() async {
    final r = await _get('/api/corrales/');
    final cuerpo = r.cuerpo;
    final lista = cuerpo is Map ? cuerpo['corrales'] : null;
    if (lista is! List) throw const ApiException('Respuesta inesperada del servidor.');
    return [
      for (final c in lista)
        if (_corralDeJson(c, r.ahora) case final corral?) corral,
    ];
  }

  /// [ahora] es la hora del servidor (encabezado Date): asi un reloj mal puesto en
  /// el celular no hace parecer viejas las lecturas.
  Corral? _corralDeJson(Object? c, DateTime ahora) {
    if (c is! Map || c['id'] is! num || c['humedad'] is! num || c['temperatura'] is! num) return null;
    final id = (c['id'] as num).toInt();

    int? antiguedad;
    var enVivo = c['enVivo'] == true;
    if (enVivo) {
      final ts = DateTime.tryParse('${c['timestamp']}');
      if (ts != null) {
        antiguedad = ahora.difference(ts).inSeconds;
        if (antiguedad < 0) antiguedad = 0;
        if (antiguedad > kSegundosEnVivo) enVivo = false; // dato real, pero viejo
      }
    }

    return Corral(
      id: id,
      nombre: '${c['nombre'] ?? 'Corral $id'}',
      descripcion: '${c['descripcion'] ?? ''}',
      humedad: (c['humedad'] as num).toDouble(),
      temperatura: (c['temperatura'] as num).toDouble(),
      enVivo: enVivo,
      antiguedadSegundos: antiguedad,
      dispositivo: c['dispositivo'] is String ? c['dispositivo'] as String : null,
    );
  }

  /// Consulta ahora y luego cada [_intervalo]. Un error se emite al stream pero
  /// no lo cierra: la siguiente consulta lo recupera sola cuando vuelve la red.
  Stream<T> _sondeo<T>(Future<T> Function() consulta) {
    late final StreamController<T> ctrl;
    Timer? timer;
    var enCurso = false;

    Future<void> tick() async {
      if (enCurso || ctrl.isClosed) return;
      enCurso = true;
      try {
        final valor = await consulta();
        if (!ctrl.isClosed) ctrl.add(valor);
      } catch (e, st) {
        if (!ctrl.isClosed) ctrl.addError(e, st);
      } finally {
        enCurso = false;
      }
    }

    ctrl = StreamController<T>(
      onListen: () {
        tick();
        timer = Timer.periodic(_intervalo, (_) => tick());
      },
      onCancel: () => timer?.cancel(),
    );
    return ctrl.stream;
  }

  // -------------------------------------------------------------- historial

  /// Serie de humedad del corral desde Django; si hay menos de 2 puntos se usa la simulada.
  @override
  Future<List<double>> getHumedad24h(int corralId) async {
    try {
      final r = await _get('/api/corrales/$corralId/historial/?limit=25');
      final cuerpo = r.cuerpo;
      final serie = cuerpo is Map ? cuerpo['humedad_serie'] : null;
      if (serie is List) {
        final valores = [for (final v in serie) if (v is num) v.toDouble()];
        if (valores.length >= 2) return valores;
      }
    } catch (e) {
      debugPrint('No se pudo leer el historial: $e');
    }
    return super.getHumedad24h(corralId);
  }

  // ----------------------------------------------------------------- avisos

  /// Alertas reales primero (las guardadas en la base y las detectadas en vivo),
  /// seguidas de los avisos simulados.
  @override
  Future<List<Aviso>> getAvisos() async {
    final simulados = await super.getAvisos();
    try {
      final r = await _get('/api/alertas/');
      final cuerpo = r.cuerpo;
      if (cuerpo is! Map) return simulados;

      final reales = <Aviso>[];
      final tiposPendientes = <String>{};
      final guardadas = cuerpo['alertas'];
      if (guardadas is List) {
        for (final a in guardadas) {
          final aviso = _avisoDeAlerta(a, r.ahora);
          if (aviso == null) continue;
          reales.add(aviso);
          if (aviso.pendiente && a is Map) tiposPendientes.add('${a['tipo_alerta']}');
        }
      }
      // Las detectadas en vivo aun no estan en la base: se muestran si no hay una igual pendiente.
      final enVivo = cuerpo['alertas_en_vivo_firebase'];
      if (enVivo is List) {
        var n = 0;
        for (final a in enVivo) {
          if (a is Map && tiposPendientes.contains('${a['tipo_alerta']}')) continue;
          final aviso = _avisoDeAlerta(a, r.ahora, id: -(++n), prefijo: 'En vivo');
          if (aviso != null) reales.add(aviso);
        }
      }
      return [...reales, ...simulados];
    } catch (e) {
      debugPrint('No se pudieron leer las alertas: $e');
      return simulados;
    }
  }

  Aviso? _avisoDeAlerta(Object? a, DateTime ahora, {int? id, String? prefijo}) {
    if (a is! Map) return null;
    final idAlerta = id ?? (a['id'] is num ? 1000 + (a['id'] as num).toInt() : null); // evita chocar con los simulados
    if (idAlerta == null) return null;

    final fecha = DateTime.tryParse('${a['fecha_hora']}');
    final tipo = '${a['tipo_alerta']}';
    final tipoTexto = switch (tipo) {
      'ESTRES_FRIO_TERNERO' => 'Temperatura baja',
      'ESTRES_CALOR_TERNERO' => 'Temperatura alta',
      'CAMAS_CALIENTES_HUMEDAD' => 'Humedad alta',
      _ => 'Alerta',
    };
    final lugar = prefijo ?? (a['sensor_ubicacion'] is String ? a['sensor_ubicacion'] as String : 'Corral 1');
    final estado = '${a['estado_lectura']}';

    return Aviso(
      id: idAlerta,
      titulo: '$lugar — $tipoTexto',
      detalle: '${a['mensaje'] ?? ''}',
      tiempo: fecha == null ? '' : _hace(ahora.difference(fecha)),
      pendiente: estado == 'PENDIENTE',
      resueltoTexto: estado == 'LEIDA' ? 'leída' : 'sin hora registrada',
    );
  }

  static String _hace(Duration d) {
    if (d.inMinutes < 1) return 'Hace instantes';
    if (d.inMinutes < 60) return 'Hace ${d.inMinutes} min';
    if (d.inHours < 24) return 'Hace ${d.inHours} h';
    return 'Hace ${d.inDays} d';
  }

  // ------------------------------------------------------------------- HTTP

  /// GET con token Bearer. Si el token venció (401) intenta renovarlo una vez.
  Future<({Object? cuerpo, DateTime ahora})> _get(String ruta) async {
    for (var intento = 0; intento < 2; intento++) {
      final token = _access;
      if (token == null) throw const ApiException('Inicia sesión para ver los datos.', statusCode: 401);

      final http.Response r;
      try {
        r = await _cliente.get(_uri(ruta), headers: {'Authorization': 'Bearer $token'}).timeout(_timeout);
      } on TimeoutException {
        throw ApiException('El servidor no respondió ($_baseUrl).');
      } catch (e) {
        debugPrint('Sin conexión con Django: $e');
        throw ApiException('No se pudo conectar con el servidor ($_baseUrl).');
      }

      if (r.statusCode == 401) {
        if (intento == 0 && await _renovar()) continue;
        _access = null;
        throw const ApiException('La sesión expiró. Vuelve a iniciar sesión.', statusCode: 401);
      }
      final cuerpo = _decodificar(r);
      if (r.statusCode != 200) throw ApiException(_mensajeDeError(cuerpo, r.statusCode), statusCode: r.statusCode);
      return (cuerpo: cuerpo, ahora: _horaServidor(r));
    }
    throw const ApiException('La sesión expiró. Vuelve a iniciar sesión.', statusCode: 401);
  }

  DateTime _horaServidor(http.Response r) {
    final fecha = r.headers['date'];
    if (fecha != null) {
      try {
        return HttpDate.parse(fecha);
      } catch (_) {}
    }
    return DateTime.now().toUtc();
  }

  Object? _decodificar(http.Response r) {
    try {
      return jsonDecode(utf8.decode(r.bodyBytes));
    } catch (_) {
      return null;
    }
  }

  String _mensajeDeError(Object? cuerpo, int status) {
    if (status == 429) return 'Demasiados intentos. Espera un minuto e inténtalo de nuevo.';
    if (cuerpo is Map) {
      if (cuerpo['error'] is String) return cuerpo['error'] as String;
      if (cuerpo['detail'] is String) return cuerpo['detail'] as String;
      if (cuerpo.containsKey('email')) return 'Ingresa un correo válido.';
      if (cuerpo.containsKey('pin')) return 'El PIN debe tener 6 dígitos numéricos.';
    }
    return 'Error del servidor ($status).';
  }
}
