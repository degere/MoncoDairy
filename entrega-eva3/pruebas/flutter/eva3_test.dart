// Pruebas Eva-3 (AgroSalud Tech) para la app Flutter MoncoDairy Sense.
// Archivo NUEVO: no modifica codigo de produccion. Se copia a Flutter/test/ en
// una copia del proyecto y se ejecuta con `flutter test test/eva3_test.dart`.
// Cada prueba afirma el comportamiento ESPERADO segun el informe base; un fallo
// se reporta como discrepancia en el informe. El ID (F-xxx) es el del informe.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moncodairy_sense/data/repository.dart';
import 'package:moncodairy_sense/data/telemetria_registro.dart';
import 'package:moncodairy_sense/main.dart';
import 'package:moncodairy_sense/models/models.dart';

Corral _c(double h, double t) => Corral(id: 1, nombre: 'C', descripcion: 'd', humedad: h, temperatura: t);

Map<String, Object?> _payload(Object? t, Object? h, {Object? disp = 'WEMOS-D1-01'}) => {
      'dispositivo': disp,
      'lecturas_crudas': {'temperatura_celsius': t, 'humedad_ambiente_pct': h},
    };

Future<void> _entrar(WidgetTester tester, String usuario, String pin) async {
  await tester.pumpWidget(const MoncoDairyApp());
  await tester.enterText(find.byType(TextField).at(0), usuario);
  await tester.enterText(find.byType(TextField).at(1), pin);
  await tester.tap(find.text('ENTRAR'));
  await tester.pump(const Duration(milliseconds: 500)); // MockRepository.login demora 400 ms
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => Repository.instance = MockRepository());

  group('Semaforo de humedad (Corral.nivelHumedad)', () {
    test('F-001 bordes 60 / 60.1 / 74.9 / 75', () {
      expect(_c(60, 15).nivelHumedad, Nivel.ok);
      expect(_c(60.1, 15).nivelHumedad, Nivel.alerta);
      expect(_c(74.9, 15).nivelHumedad, Nivel.alerta);
      expect(_c(75, 15).nivelHumedad, Nivel.critico);
    });
    test('F-002 temperatura baja < 12 C', () {
      expect(_c(50, 11.9).temperaturaBaja, isTrue);
      expect(_c(50, 12).temperaturaBaja, isFalse);
    });
    test('F-003 umbral critico de la app coincide con HU-002 / backend (>= 80 %)', () {
      // El backend (views.py) alerta camas humedas desde 80 %; HU-002 tambien usa 80 %.
      expect(_c(78, 15).nivelHumedad, isNot(Nivel.critico));
    });
  });

  group('TelemetriaRegistro (lectura Firebase del DHT22)', () {
    test('F-010 acepta el formato real del sketch WeMos (dispositivo como mapa)', () {
      final r = TelemetriaRegistro.tryParse('-Nx', _payload(18.4, 64.2, disp: {'node_id': 'WEMOS-D1-01', 'mac_address': 'x'}));
      expect(r, isNotNull);
      expect(r!.dispositivo, 'WEMOS-D1-01');
    });
    test('F-011 acepta enteros (RTDB entrega int) y bordes -20 / 70 / 0 / 100', () {
      expect(TelemetriaRegistro.tryParse('a', _payload(-20, 0)), isNotNull);
      expect(TelemetriaRegistro.tryParse('a', _payload(70, 100)), isNotNull);
    });
    test('F-012 rechaza fuera de rango, NaN, tipos erroneos y campos faltantes', () {
      expect(TelemetriaRegistro.tryParse('a', _payload(70.1, 50)), isNull);
      expect(TelemetriaRegistro.tryParse('a', _payload(20, 100.1)), isNull);
      expect(TelemetriaRegistro.tryParse('a', _payload(double.nan, 50)), isNull);
      expect(TelemetriaRegistro.tryParse('a', _payload('20', 50)), isNull);
      expect(TelemetriaRegistro.tryParse('a', _payload(20, 50, disp: null)), isNull);
      expect(TelemetriaRegistro.tryParse('a', 'texto'), isNull);
    });
    test('F-013 paquete ERROR_SENSOR del sketch (sin lecturas_crudas) se descarta', () {
      expect(TelemetriaRegistro.tryParse('a', {
        'dispositivo': {'node_id': 'WEMOS-D1-01'},
        'filtro_y_validacion': {'estado_filtrado': 'ERROR_SENSOR'},
      }), isNull);
    });
    test('F-014 rango de temperatura de la app es coherente con el backend (-20..45 C)', () {
      // views.py descarta > 45 C; la app acepta hasta 70 C.
      expect(TelemetriaRegistro.tryParse('a', _payload(60, 50)), isNull);
    });
  });

  group('Repositorio simulado', () {
    test('F-020 20 corrales y 40 sensores (2 inactivos, 1 por revisar)', () async {
      final repo = MockRepository();
      expect((await repo.getCorrales()).length, 20);
      final s = await repo.getSensores();
      expect(s.length, 40);
      expect(s.where((x) => x.estado == EstadoSensor.inactivo).length, 2);
      expect(s.where((x) => x.estado == EstadoSensor.revisar).length, 1);
    });
    test('F-021 login rechaza usuario vacio y PIN de largo distinto de 6', () async {
      final repo = MockRepository();
      expect(await repo.login('  ', '123456'), isFalse);
      expect(await repo.login('ana', '12345'), isFalse);
    });
    test('F-022 login rechaza PIN no numerico (politica de PIN de 6 digitos)', () async {
      expect(await MockRepository().login('ana', 'abcdef'), isFalse);
    });
    test('F-023 login rechaza credenciales no registradas', () async {
      expect(await MockRepository().login('usuario-inexistente', '000000'), isFalse);
    });
  });

  group('Interfaz (widget)', () {
    testWidgets('F-030 login vacio muestra error y no navega', (tester) async {
      await _entrar(tester, '', '');
      expect(find.text('Revisa tu usuario y que el PIN tenga 6 dígitos.'), findsOneWidget);
      expect(find.text('Selecciona un Corral'), findsNothing);
    });

    testWidgets('F-031 login valido abre navegacion inferior de 4 vistas', (tester) async {
      await _entrar(tester, 'Ana', '482913');
      expect(find.text('Hola, Ana'), findsOneWidget);
      for (final t in ['Corrales', 'Avisos', 'Sensores', 'Historial']) {
        expect(find.text(t), findsWidgets);
      }
    });

    testWidgets('F-032 Avisos muestra solo los 3 pendientes', (tester) async {
      await _entrar(tester, 'Ana', '482913');
      await tester.tap(find.text('Avisos'));
      await tester.pumpAndSettle();
      expect(find.text('Avisos activos'), findsOneWidget);
      expect(find.text('PENDIENTE'), findsNWidgets(3));
    });

    testWidgets('F-033 Historial filtra Resueltos', (tester) async {
      await _entrar(tester, 'Ana', '482913');
      await tester.tap(find.text('Historial'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Resueltos'));
      await tester.pumpAndSettle();
      expect(find.text('PENDIENTE'), findsNothing);
    });

    testWidgets('F-034 detalle de corral critico en 1 toque (Corral 3 = 85 %)', (tester) async {
      await _entrar(tester, 'Ana', '482913');
      await tester.tap(find.text('Corral 3'));
      await tester.pumpAndSettle();
      expect(find.text('AVISO PREVENTIVO'), findsOneWidget);
      expect(find.text('Datos simulados'), findsOneWidget);
    });

    testWidgets('F-035 indicador de conexion refleja modo offline (RNF-01 / mejora de piloto)', (tester) async {
      // El diseno exige un indicador "Modo Offline"; la app muestra siempre "En linea".
      await _entrar(tester, 'Ana', '482913');
      expect(find.textContaining('Offline'), findsOneWidget);
    });
    // F-036 (RBAC visual) se verifica por inspeccion: HomeShell no recibe rol (ver informe).
  });
}
