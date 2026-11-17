import 'package:flutter_test/flutter_test.dart';

import 'package:moncodairy_sense/data/telemetria_registro.dart';
import 'package:moncodairy_sense/main.dart';

void main() {
  testWidgets('Muestra la pantalla de login', (WidgetTester tester) async {
    await tester.pumpWidget(const MoncoDairyApp());

    expect(find.text('MoncoDairy Sense'), findsOneWidget);
    expect(find.text('ENTRAR'), findsOneWidget);
  });

  test('TelemetriaRegistro acepta el formato del simulador DHT22', () {
    final r = TelemetriaRegistro.tryParse('-Nabc', {
      'dispositivo': {'node_id': 'NODE-PARTOS-02'},
      'lecturas_crudas': {'temperatura_celsius': 18, 'humedad_ambiente_pct': 64.5},
    });
    expect(r, isNotNull);
    expect(r!.dispositivo, 'NODE-PARTOS-02');
    expect(r.temperaturaC, 18.0);
    expect(r.humedadPct, 64.5);
  });

  test('TelemetriaRegistro descarta lecturas fuera de rango o incompletas', () {
    expect(TelemetriaRegistro.tryParse('x', {'dispositivo': 'a'}), isNull);
    expect(
      TelemetriaRegistro.tryParse('x', {
        'dispositivo': 'a',
        'lecturas_crudas': {'temperatura_celsius': 200, 'humedad_ambiente_pct': 50},
      }),
      isNull,
    );
  });
}
