// Pruebas Eva-3 (AgroSalud Tech) para HU-006 (modo sin conexion) en la app Flutter.
//
// Archivo NUEVO: no modifica codigo de la app. Para ejecutarlo se copia a Flutter/test/ y se corre:
//   flutter test test/eva3_offline_test.dart
//
// F-040 y F-041 afirman lo que la app SI hace; F-042 y F-043 afirman lo que pide el informe base
// (guardar el ultimo dato y permitir el ingreso sin red) y por eso FALLAN: son la evidencia de que
// HU-006 esta implementada solo en parte.
import 'dart:async';
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

Map<String, Object?> _corrales() => {
      'status': 'success',
      'total': 20,
      'corrales': [
        for (var i = 1; i <= 20; i++)
          {
            'id': i,
            'nombre': 'Corral $i',
            'descripcion': 'Galpón $i',
            'humedad': 60.0,
            'temperatura': 12.0,
            'enVivo': false,
            'dispositivo': null,
            'timestamp': null,
          },
      ],
    };

final _tokens = {
  'status': 'success',
  'tokens': {'access': 'A', 'refresh': 'R'},
};

ApiRepository _repo(MockClient c) =>
    ApiRepository(cliente: c, baseUrl: 'http://prueba', intervalo: const Duration(milliseconds: 40));

void main() {
  test('F-040 sin red: la lista de corrales emite un error de conexión entendible', () async {
    final repo = _repo(MockClient((req) async {
      if (req.url.path == '/api/auth/login-pin/') return _json(_tokens);
      throw http.ClientException('sin red');
    }));
    expect(await repo.login('ana@ejemplo.cl', '123456'), isTrue);
    await expectLater(
      repo.watchCorrales(),
      emitsError(isA<ApiException>().having((e) => e.mensaje, 'mensaje', contains('No se pudo conectar'))),
    );
  });

  test('F-041 al volver la red, el siguiente ciclo recupera los 20 corrales', () async {
    var llamadas = 0;
    final repo = _repo(MockClient((req) async {
      if (req.url.path == '/api/auth/login-pin/') return _json(_tokens);
      llamadas++;
      if (llamadas == 1) throw http.ClientException('sin red');
      return _json(_corrales());
    }));
    expect(await repo.login('ana@ejemplo.cl', '123456'), isTrue);
    await expectLater(
      repo.watchCorrales(),
      emitsInOrder([
        emitsError(isA<ApiException>()),
        predicate<List<Corral>>((l) => l.length == 20, '20 corrales'),
      ]),
    );
  });

  test('F-042 (HU-006) tras un dato válido, un corte de red conserva el último dato', () async {
    var llamadas = 0;
    final repo = _repo(MockClient((req) async {
      if (req.url.path == '/api/auth/login-pin/') return _json(_tokens);
      llamadas++;
      if (llamadas == 1) return _json(_corrales());
      throw http.ClientException('sin red');
    }));
    expect(await repo.login('ana@ejemplo.cl', '123456'), isTrue);
    final eventos = await repo
        .watchCorrales()
        .transform<Object>(StreamTransformer.fromHandlers(
            handleData: (d, s) => s.add(d!), handleError: (e, st, s) => s.add(e)))
        .take(2)
        .toList();
    expect(eventos[0], isA<List<Corral>>());
    expect(eventos[1], isA<List<Corral>>(), reason: 'el 2º evento fue un error: el dato anterior se perdió');
  });

  test('F-043 (HU-006) una sesión nueva sin red permite ingresar con el PIN guardado', () async {
    final primera = _repo(MockClient((_) async => _json(_tokens)));
    expect(await primera.login('ana@ejemplo.cl', '123456'), isTrue);

    final despuesDeReiniciar = _repo(MockClient((_) async => throw http.ClientException('sin red')));
    expect(await despuesDeReiniciar.login('ana@ejemplo.cl', '123456'), isTrue,
        reason: 'sin red no hay ingreso: la app no guarda credenciales ni datos en el teléfono');
  });
}
