import 'package:flutter/material.dart';
import 'core/theme.dart';
import 'screens/login_screen.dart';

void main() {
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
