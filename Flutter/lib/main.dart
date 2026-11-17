import 'package:flutter/material.dart';
import 'core/theme.dart';
import 'data/api_repository.dart';
import 'data/repository.dart';
import 'screens/login_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // La app solo habla con Django (login real y lecturas de sensores). Django lee
  // Firebase por su cuenta; la app no toca Firebase.
  Repository.instance = ApiRepository();
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
