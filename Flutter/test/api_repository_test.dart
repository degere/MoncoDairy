import 'dart:convert';
import 'dart:io' show HttpDate;

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:moncodairy_sense/data/api_repository.dart';
import 'package:moncodairy_sense/models/models.dart';

http.Response _json(Object cuerpo, [int status = 200]) => http.Response(
      jsonEncode(cuerpo),
      status,
      headers: {
        'content-type': 'application/json; charset=utf-8',
        'date': HttpDate.format(DateTime.now().toUtc()),
      },
    );

const _corral1 = Corral(id: 1, nombre: 'Corral 1', descripcion: 'Galpón 1', humedad: 50, temperatura: 12);

ApiRepository _repo(MockClient cliente) =>
    ApiRepository(cliente: cliente, baseUrl: 'http://prueba', intervalo: const Duration(hours: 1));

Map<String, Object?> _tokens([String access = 'A', String refresh = 'R']) => {
      'status': 'success',
      'tokens': {'access': access, 'refresh': refresh},
    };

/// Forma de GET /api/corrales/: 20 corrales; el 1 trae la lectura real.
Map<String, Object?> _corrales({bool enVivo = true, int antig = 5}) {
  final ts = DateTime.now().toUtc().subtract(Duration(seconds: antig)).toIso8601String();
  return {
    'status': 'success',
    'total': 20,
    'corrales': [
      for (var i = 1; i <= 20; i++)
        {
          'id': i,
          'nombre': 'Corral $i',
          'descripcion': 'Galpón $i',
          'humedad': i == 1 ? 71.0 : 60.0,
          'temperatura': i == 1 ? 18.5 : 12.0,
          'enVivo': i == 1 && enVivo,
          'dispositivo': i == 1 && enVivo ? 'WEMOS-D1-01' : null,
          'timestamp': i == 1 && enVivo ? ts : null,
        },
    ],
  };
}

Map<String, Object?> _alerta(int id, String tipo, String estado) => {
      'id': id,
      'sensor_ubicacion': 'Corral 1 - WEMOS-D1-01',
      'tipo_alerta': tipo,
      'nivel': 'ROJO',
      'fecha_hora': DateTime.now().toUtc().toIso8601String(),
      'mensaje': 'Mensaje $tipo',
      'estado_lectura': estado,
    };

Future<ApiRepository> _conSesion(http.Response Function(http.Request) responder) async {
  final repo = _repo(MockClient((req) async {
    if (req.url.path == '/api/auth/login-pin/') return _json(_tokens());
    return responder(req);
  }));
  expect(await repo.login('ana@ejemplo.cl', '123456'), isTrue);
  return repo;
}

void main() {
  group('login', () {
    test('ok: envía correo y PIN y usa el access token en las consultas', () async {
      String? auth;
      final repo = _repo(MockClient((req) async {
        if (req.url.path == '/api/auth/login-pin/') {
          expect(jsonDecode(req.body), {'email': 'ana@ejemplo.cl', 'pin': '123456'});
          return _json(_tokens('TKN'));
        }
        auth = req.headers['Authorization'];
        return _json(_corrales());
      }));

      expect(await repo.login(' ana@ejemplo.cl ', '123456'), isTrue);
      await repo.watchCorrales().first;
      expect(auth, 'Bearer TKN');
    });

    test('credenciales inválidas: false y el mensaje de la API', () async {
      final repo = _repo(MockClient((_) async => _json({'error': 'Credenciales inválidas o usuario inactivo.'}, 401)));
      expect(await repo.login('ana@ejemplo.cl', '000000'), isFalse);
      expect(repo.ultimoErrorLogin, 'Credenciales inválidas o usuario inactivo.');
    });

    test('límite de intentos (429): mensaje en español', () async {
      final repo = _repo(MockClient((_) async => _json({'detail': 'Request was throttled. Expected available in 40 seconds.'}, 429)));
      expect(await repo.login('ana@ejemplo.cl', '000000'), isFalse);
      expect(repo.ultimoErrorLogin, contains('Demasiados intentos'));
    });

    test('sin conexión: false y mensaje con la URL', () async {
      final repo = _repo(MockClient((_) async => throw Exception('sin red')));
      expect(await repo.login('ana@ejemplo.cl', '123456'), isFalse);
      expect(repo.ultimoErrorLogin, contains('http://prueba'));
    });
  });

  group('corrales', () {
    test('en vivo: toma los 20 corrales de Django y marca el Corral 1', () async {
      final repo = await _conSesion((_) => _json(_corrales()));
      final lista = await repo.watchCorrales().first;
      expect(lista.length, 20);
      expect(lista.first.temperatura, 18.5);
      expect(lista.first.humedad, 71.0);
      expect(lista.first.enVivo, isTrue);
      expect(lista.first.dispositivo, 'WEMOS-D1-01');
      expect(lista.skip(1).any((c) => c.enVivo || c.antiguedadSegundos != null), isFalse);
    });

    test('lectura real pero vieja: sin "en vivo" y con antigüedad', () async {
      final repo = await _conSesion((_) => _json(_corrales(antig: 300)));
      final c = (await repo.watchCorrales().first).first;
      expect(c.enVivo, isFalse);
      expect(c.antiguedadSegundos, greaterThanOrEqualTo(299));
    });

    test('sin lectura real (enVivo false): dato de base, sin antigüedad', () async {
      final repo = await _conSesion((_) => _json(_corrales(enVivo: false)));
      final c = (await repo.watchCorrales().first).first;
      expect(c.enVivo, isFalse);
      expect(c.antiguedadSegundos, isNull);
    });

    test('watchCorral entrega solo el corral pedido', () async {
      final repo = await _conSesion((_) => _json(_corrales()));
      final c = await repo.watchCorral(_corral1).first;
      expect(c.id, 1);
      expect(c.humedad, 71.0);
    });

    test('token vencido (401): renueva con el refresh y reintenta', () async {
      final autorizaciones = <String?>[];
      final repo = _repo(MockClient((req) async {
        if (req.url.path == '/api/auth/login-pin/') return _json(_tokens('VIEJO', 'R1'));
        if (req.url.path == '/api/auth/token/refresh/') {
          expect(jsonDecode(req.body), {'refresh': 'R1'});
          return _json({'access': 'NUEVO', 'refresh': 'R2'});
        }
        autorizaciones.add(req.headers['Authorization']);
        return req.headers['Authorization'] == 'Bearer NUEVO' ? _json(_corrales()) : _json({'detail': 'expirado'}, 401);
      }));
      await repo.login('ana@ejemplo.cl', '123456');
      final lista = await repo.watchCorrales().first;
      expect(lista.length, 20);
      expect(autorizaciones, ['Bearer VIEJO', 'Bearer NUEVO']);
    });

    test('sesión vencida y refresh rechazado: el stream emite un ApiException', () async {
      final repo = _repo(MockClient((req) async {
        if (req.url.path == '/api/auth/login-pin/') return _json(_tokens());
        if (req.url.path == '/api/auth/token/refresh/') return _json({'error': 'Token refresh inválido o expirado.'}, 401);
        return _json({'detail': 'expirado'}, 401);
      }));
      await repo.login('ana@ejemplo.cl', '123456');
      await expectLater(repo.watchCorrales(), emitsError(isA<ApiException>()));
    });
  });

  group('historial', () {
    test('usa la serie de humedad de Django', () async {
      final repo = await _conSesion((req) {
        expect(req.url.path, '/api/corrales/1/historial/');
        return _json({'status': 'success', 'humedad_serie': [60, 65.5, 70]});
      });
      expect(await repo.getHumedad24h(1), [60.0, 65.5, 70.0]);
    });

    test('si Django falla usa la serie simulada', () async {
      final repo = _repo(MockClient((_) async => throw Exception('sin red')));
      expect((await repo.getHumedad24h(1)).length, 25);
    });
  });

  group('avisos', () {
    test('alertas guardadas y en vivo primero (sin duplicar tipos pendientes), luego simulados', () async {
      final repo = await _conSesion((_) => _json({
            'status': 'success',
            'alertas': [_alerta(7, 'CAMAS_CALIENTES_HUMEDAD', 'PENDIENTE')],
            'alertas_en_vivo_firebase': [
              _alerta(0, 'CAMAS_CALIENTES_HUMEDAD', 'PENDIENTE')..remove('id'), // mismo tipo pendiente: se omite
              _alerta(0, 'ESTRES_FRIO_TERNERO', 'PENDIENTE')..remove('id'),
            ],
          }));
      final avisos = await repo.getAvisos();
      expect(avisos.length, 12); // 2 reales + 10 simulados
      expect(avisos.first.titulo, 'Corral 1 - WEMOS-D1-01 — Humedad alta');
      expect(avisos.first.pendiente, isTrue);
      expect(avisos[1].titulo, 'En vivo — Temperatura baja');
    });

    test('alerta resuelta no figura como pendiente', () async {
      final repo = await _conSesion((_) => _json({
            'alertas': [_alerta(3, 'ESTRES_FRIO_TERNERO', 'RESUELTA')],
            'alertas_en_vivo_firebase': [],
          }));
      expect((await repo.getAvisos()).first.pendiente, isFalse);
    });

    test('si Django falla, igual se muestran los simulados', () async {
      final repo = _repo(MockClient((_) async => throw Exception('sin red')));
      expect((await repo.getAvisos()).length, 10);
    });
  });
}
