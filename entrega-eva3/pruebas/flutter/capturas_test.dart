// Genera capturas PNG de las pantallas reales de MoncoDairy Sense renderizando
// los widgets con flutter_test (sin emulador). Archivo NUEVO de la Eva-3.
// Uso (en una copia del proyecto):
//   flutter test test/capturas_test.dart --update-goldens --dart-define=FLUTTER_ROOT=C:/src/flutter
// Las imagenes quedan en test/capturas/*.png. Usan el MockRepository (datos simulados),
// porque en el entorno de pruebas Firebase no se inicializa.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moncodairy_sense/data/repository.dart';
import 'package:moncodairy_sense/main.dart';

const _root = String.fromEnvironment('FLUTTER_ROOT', defaultValue: 'C:/src/flutter');

Future<void> _cargarFuente(String familia, List<String> archivos) async {
  final loader = FontLoader(familia);
  for (final a in archivos) {
    final bytes = File('$_root/bin/cache/artifacts/material_fonts/$a').readAsBytesSync();
    loader.addFont(Future.value(ByteData.view(bytes.buffer)));
  }
  await loader.load();
}

Future<void> _foto(WidgetTester tester, String nombre) async {
  await tester.pumpAndSettle();
  await expectLater(find.byType(MaterialApp), matchesGoldenFile('capturas/$nombre.png'));
}

void main() {
  setUpAll(() async {
    await _cargarFuente('Roboto', ['roboto-regular.ttf', 'roboto-medium.ttf', 'roboto-bold.ttf']);
    await _cargarFuente('MaterialIcons', ['materialicons-regular.otf']);
    // Nota: textos cuyo TextStyle no define fontFamily (boton ENTRAR, ejes del grafico) se ven
    // como bloques en la captura: es la fuente de pruebas de flutter_test, no un defecto de la app.
  });
  setUp(() => Repository.instance = MockRepository());

  testWidgets('capturas de pantallas', (tester) async {
    tester.view.physicalSize = const Size(1080, 2340);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(const MoncoDairyApp());
    await _foto(tester, '01_login_vacio');

    await tester.enterText(find.byType(TextField).at(0), 'Ana');
    await tester.enterText(find.byType(TextField).at(1), '482913');
    await tester.pump();
    await _foto(tester, '02_login_con_pin');

    await tester.tap(find.text('ENTRAR'));
    await tester.pump(const Duration(milliseconds: 500));
    await _foto(tester, '03_corrales');

    await tester.tap(find.text('Corral 3'));
    await _foto(tester, '04_detalle_corral_critico');

    await tester.tap(find.text('Ver detalle del sensor'));
    await _foto(tester, '05_detalle_sensor');

    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.text('Avisos'));
    await _foto(tester, '06_avisos');

    await tester.tap(find.text('Sensores'));
    await _foto(tester, '07_sensores');

    await tester.tap(find.text('Historial'));
    await _foto(tester, '08_historial');
  });
}
