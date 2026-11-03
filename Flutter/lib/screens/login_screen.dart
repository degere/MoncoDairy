import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../data/repository.dart';
import 'home_shell.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _userCtrl = TextEditingController();
  final _pinCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _userCtrl.dispose();
    _pinCtrl.dispose();
    super.dispose();
  }

  Future<void> _entrar() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final ok = await Repository.instance.login(_userCtrl.text, _pinCtrl.text);
    if (!mounted) return;
    if (ok) {
      Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => HomeShell(usuario: _userCtrl.text.trim())));
    } else {
      setState(() {
        _loading = false;
        _error = 'Revisa tu usuario y que el PIN tenga 6 dígitos.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
          child: Column(
            children: [
              // TODO: reemplazar por la ilustración del Figma (assets/images/portada.png)
              Container(
                height: 200,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: AppColors.greenSoft,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.border),
                ),
                child: const Icon(Icons.agriculture, size: 80, color: AppColors.green),
              ),
              const SizedBox(height: 24),
              const Text('MoncoDairy Sense',
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: AppColors.green)),
              const SizedBox(height: 4),
              const Text('Monitor de Sensores', style: TextStyle(color: AppColors.textMuted, fontSize: 15)),
              const SizedBox(height: 32),
              TextField(
                controller: _userCtrl,
                textInputAction: TextInputAction.next,
                decoration: _decoration('Usuario', Icons.person_outline),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _pinCtrl,
                obscureText: true,
                keyboardType: TextInputType.number,
                maxLength: 6,
                onChanged: (_) => setState(() {}),
                decoration: _decoration('PIN de 6 dígitos', Icons.lock_outline).copyWith(counterText: ''),
              ),
              const SizedBox(height: 14),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(6, (i) {
                  final lleno = i < _pinCtrl.text.length;
                  return Container(
                    margin: const EdgeInsets.symmetric(horizontal: 5),
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: lleno ? AppColors.green : Colors.transparent,
                      border: Border.all(color: lleno ? AppColors.green : AppColors.border, width: 1.5),
                    ),
                  );
                }),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: AppColors.red, fontSize: 13)),
              ],
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _loading ? null : _entrar,
                child: _loading
                    ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('ENTRAR'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  InputDecoration _decoration(String label, IconData icon) {
    return InputDecoration(
      labelText: label,
      suffixIcon: Icon(icon),
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: AppColors.border)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: AppColors.border)),
    );
  }
}
