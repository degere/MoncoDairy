import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_database/firebase_database.dart';
import 'package:flutter/foundation.dart';

import '../firebase_options.dart'; // lo genera `flutterfire configure`
import '../models/models.dart';
import 'repository.dart';
import 'telemetria_registro.dart';

const String kDatabaseUrl = 'https://appmoncopullisensores-default-rtdb.firebaseio.com';
const String kNodoTelemetria = 'telemetria';

/// Corral que hoy recibe las lecturas reales del sensor DHT22.
const int kCorralConSensorReal = 1;

/// Campo por el que se ordenan los registros para obtener el mas reciente
/// (ej. 'timestamp'). null = se ordena por clave, correcto si los $registro_id
/// son claves automaticas (push IDs) de Firebase.
final String? kCampoOrden = null;

/// Lecturas reales desde Firebase Realtime Database.
/// Hereda de [MockRepository] lo que aun no esta conectado (login, avisos,
/// sensores, historial) y reemplaza con datos reales el [kCorralConSensorReal].
class FirebaseRepository extends MockRepository {
  FirebaseRepository._(this._db);
  final FirebaseDatabase _db;

  /// Inicializa Firebase, inicia sesion anonima (las reglas exigen auth)
  /// y devuelve el repositorio listo para asignar a [Repository.instance].
  static Future<FirebaseRepository> inicializar() async {
    await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

    final db = FirebaseDatabase.instanceFor(app: Firebase.app(), databaseURL: kDatabaseUrl);
    db.setPersistenceEnabled(true); // muestra el ultimo dato aunque no haya red

    try {
      final auth = FirebaseAuth.instance;
      if (auth.currentUser == null) await auth.signInAnonymously();
    } catch (e) {
      // No detiene la app: si falla, la lectura dara permission-denied y la UI lo mostrara.
      debugPrint('Firebase Auth anonimo fallo: $e');
    }
    return FirebaseRepository._(db);
  }

  /// Ultimo registro de /telemetria; null si no hay o el ultimo no es valido.
  Stream<TelemetriaRegistro?> _ultimoRegistro() {
    final ref = _db.ref(kNodoTelemetria);
    final campo = kCampoOrden;
    final Query ordenada = campo == null ? ref.orderByKey() : ref.orderByChild(campo);
    return ordenada.limitToLast(1).onValue.map((event) {
      final snap = event.snapshot;
      if (!snap.exists || snap.children.isEmpty) return null;
      final hijo = snap.children.last;
      return TelemetriaRegistro.tryParse(hijo.key ?? '', hijo.value);
    });
  }

  Corral _conLectura(Corral base, TelemetriaRegistro? r) {
    if (r == null) return base; // sin lectura valida: se conserva el dato simulado
    return Corral(
      id: base.id,
      nombre: base.nombre,
      descripcion: base.descripcion,
      humedad: r.humedadPct,
      temperatura: r.temperaturaC,
      enVivo: true,
      dispositivo: r.dispositivo,
    );
  }

  @override
  Stream<List<Corral>> watchCorrales() async* {
    final base = await getCorrales();
    await for (final r in _ultimoRegistro()) {
      yield [
        for (final c in base) c.id == kCorralConSensorReal ? _conLectura(c, r) : c,
      ];
    }
  }

  @override
  Stream<Corral> watchCorral(Corral corral) {
    if (corral.id != kCorralConSensorReal) return Stream.value(corral);
    return _ultimoRegistro().map((r) => _conLectura(corral, r));
  }
}
