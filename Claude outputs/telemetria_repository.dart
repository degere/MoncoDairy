import 'package:firebase_database/firebase_database.dart';

import 'telemetria_registro.dart';

class TelemetriaRepository {
  TelemetriaRepository(this._db);
  final FirebaseDatabase _db;

  /// Ultimo registro de /telemetria. Las claves push de Firebase son
  /// cronologicas, asi que orderByKey().limitToLast(1) trae el mas reciente.
  /// Emite null si no hay nodos o el ultimo no es valido.
  Stream<TelemetriaRegistro?> ultimoRegistro() {
    final query = _db.ref('telemetria').orderByKey().limitToLast(1);
    return query.onValue.map((event) {
      if (!event.snapshot.exists || event.snapshot.children.isEmpty) {
        return null;
      }
      final child = event.snapshot.children.last;
      return TelemetriaRegistro.tryParse(child.key ?? '', child.value);
    });
  }

  /// true/false segun haya conexion con Firebase.
  Stream<bool> conectado() =>
      _db.ref('.info/connected').onValue.map((e) => e.snapshot.value == true);
}
