import 'package:flutter/material.dart';
import 'core/theme.dart';
import 'data/firebase_repository.dart';
import 'data/repository.dart';
import 'screens/login_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    // Conecta con Firebase Realtime Database (lecturas reales de sensores).
    Repository.instance = await FirebaseRepository.inicializar();
  } catch (e) {
    // Si Firebase no esta configurado, la app sigue con datos simulados.
    debugPrint('Firebase no disponible, usando datos simulados: $e');
  }
  runApp(const MoncoDairyApp());
}

class MoncoDairyApp extends StatelessWidget {
  const MoncoDairyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MoncoDairy Sense',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: const LoginScreen(),
    );
  }
}
