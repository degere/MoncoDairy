import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_database/firebase_database.dart';

import 'data/telemetria_repository.dart';
import 'firebase_options.dart'; // lo genera `flutterfire configure`

const String kDatabaseUrl =
    'https://appmoncopullisensores-default-rtdb.firebaseio.com';

/// Inicializa Firebase y devuelve el repositorio listo para inyectar.
/// Llamar en main() despues de WidgetsFlutterBinding.ensureInitialized().
Future<TelemetriaRepository> inicializarFirebase() async {
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  final db = FirebaseDatabase.instanceFor(
    app: Firebase.app(),
    databaseURL: kDatabaseUrl,
  );
  db.setPersistenceEnabled(true); // muestra el ultimo dato sin red
  return TelemetriaRepository(db);
}
