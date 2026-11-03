import 'package:flutter/material.dart';

class AppColors {
  static const green = Color(0xFF1B5E20);
  static const greenLight = Color(0xFF66BB6A);
  static const greenSoft = Color(0xFFE3F1E4);
  static const bg = Color(0xFFF8F5EC);
  static const card = Colors.white;
  static const red = Color(0xFFC62828);
  static const redSoft = Color(0xFFFBD5D5);
  static const orange = Color(0xFFF5A623);
  static const orangeSoft = Color(0xFFFFF4D6);
  static const blue = Color(0xFF1976D2);
  static const blueSoft = Color(0xFFDCEBFA);
  static const textMuted = Color(0xFF6B6B6B);
  static const border = Color(0xFFE4DFD0);
}

ThemeData buildTheme() {
  return ThemeData(
    useMaterial3: true,
    scaffoldBackgroundColor: AppColors.bg,
    colorScheme: ColorScheme.fromSeed(
      seedColor: AppColors.green,
      primary: AppColors.green,
      surface: AppColors.bg,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.bg,
      elevation: 0,
      scrolledUnderElevation: 0,
      foregroundColor: Colors.black87,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.green,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        textStyle: const TextStyle(fontSize: 16, letterSpacing: 1),
      ),
    ),
  );
}
