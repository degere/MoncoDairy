import logging
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import construir_permisos_rol, generar_tokens_para_usuario
from .firebase_service import (
    FirebaseService,
    TEMP_MAX_FISICO_TERNERERA,
    TEMP_MIN_FISICO_TERNERERA,
    HUM_MAX_SENSOR,
    HUM_MIN_SENSOR,
    evaluar_riesgos_sanitarios,
)
from .models import Alerta, Animal, CollarRfid, LecturaSensor, Rol, Sensor, Tratamiento, Usuario
from .permissions import EsAdministradorOVeterinario, PermisoRegistroUsuario
from .serializers import (
    AlertaSerializer,
    IngestaIoTInputSerializer,
    LoginPINSerializer,
    RefreshTokenPINSerializer,
    RegistroUsuarioPINSerializer,
    RolSerializer,
    SensorSerializer,
    TelemetriaFirebaseInputSerializer,
    UsuarioSerializer,
    VerificacionRFIDInputSerializer,
)

logger = logging.getLogger(__name__)


class IngestaIoTAPIView(APIView):
    """
    Recibe lecturas IoT de temperatura (°C) y humedad (%), valida rangos físicos,
    almacena en la base de datos transaccional, evalúa el motor de alertas sanitarias
    para ternereras y publica/sincroniza los datos en Firebase Realtime Database (`/telemetria` y `/alertas`).
    """
    serializer_class = IngestaIoTInputSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'iot_ingesta'

    def post(self, request, *args, **kwargs):
        data = request.data
        sensor_id = data.get('sensor_id')
        valor = data.get('valor')
        unidad = data.get('unidad')  # '°C' o '%'
        dispositivo = str(data.get('dispositivo') or f'Sensor_{sensor_id or 1}').strip()[:64]

        try:
            corral_id = int(data.get('corral_id', 1))
            if not (1 <= corral_id <= 100):
                return Response(
                    {"error": "El ID de corral debe estar entre 1 y 100."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (TypeError, ValueError):
            return Response(
                {"error": "El ID de corral debe ser un entero válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not sensor_id or valor is None or not unidad:
            return Response(
                {"error": "Faltan parámetros obligatorios (sensor_id, valor, unidad)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sensor = Sensor.objects.get(id=sensor_id)
        except (Sensor.DoesNotExist, ValueError):
            return Response({"error": "El sensor especificado no existe."}, status=status.HTTP_404_NOT_FOUND)

        try:
            val_float = float(valor)
        except (TypeError, ValueError):
            return Response({"error": "El valor debe ser numérico."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Filtro de Rango Físico
        if not self._validar_rango_fisico(unidad, val_float):
            logger.warning("Lectura anómala descartada del sensor %s: %s %s", sensor_id, val_float, unidad)
            return Response(
                {"error": "Lectura fuera de rango físico real. Dato descartado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Guardar Lectura en BD Transaccional
        lectura = LecturaSensor.objects.create(
            sensor=sensor,
            valor=val_float,
            unidad=unidad,
            fecha_hora=timezone.now(),
        )

        # 3. Motor de Alertas Sanitarias Enfocado en Terneros + Publicación en Firebase
        alertas_generadas = self._evaluar_riesgo_terneros(sensor, lectura, val_float, unidad, dispositivo, corral_id)

        # 4. Sincronizar lectura con Firebase Realtime Database (/telemetria)
        firebase_sync = self._sincronizar_lectura_firebase(sensor, val_float, unidad, dispositivo, corral_id)

        return Response(
            {
                "status": "success",
                "mensaje": "Lectura de ternerera procesada y sincronizada con Firebase correctamente.",
                "lectura_id": lectura.id,
                "alertas_generadas": alertas_generadas,
                "firebase": firebase_sync,
            },
            status=status.HTTP_201_CREATED,
        )

    def _validar_rango_fisico(self, unidad: str, valor: float) -> bool:
        u = str(unidad).upper()
        if 'C' in u and not (TEMP_MIN_FISICO_TERNERERA <= valor <= TEMP_MAX_FISICO_TERNERERA):
            return False
        if '%' in u and not (HUM_MIN_SENSOR <= valor <= HUM_MAX_SENSOR):
            return False
        return ('C' in u) or ('%' in u)

    def _evaluar_riesgo_terneros(self, sensor, lectura, valor: float, unidad: str, dispositivo: str, corral_id: int) -> list[dict]:
        u = str(unidad).upper()
        temp = valor if 'C' in u else None
        hum = valor if '%' in u else None

        riesgos = evaluar_riesgos_sanitarios(temp, hum, ubicacion=sensor.ubicacion)
        fb = FirebaseService()
        alertas_creadas = []

        for r in riesgos:
            alerta = Alerta.objects.create(
                sensor=sensor,
                lectura_sensor=lectura,
                tipo_alerta=r["tipo_alerta"],
                nivel=r["nivel"],
                fecha_hora=timezone.now(),
                mensaje=r["mensaje"],
                estado_lectura="PENDIENTE",
            )
            fb_key = fb.publicar_alerta({
                **r,
                "sensor_id": sensor.id,
                "dispositivo": dispositivo,
                "corral_id": corral_id,
            })
            alertas_creadas.append({
                "id": alerta.id,
                "tipo_alerta": alerta.tipo_alerta,
                "nivel": alerta.nivel,
                "mensaje": alerta.mensaje,
                "firebase_alerta_id": fb_key,
            })

        return alertas_creadas

    def _sincronizar_lectura_firebase(self, sensor, valor: float, unidad: str, dispositivo: str, corral_id: int) -> dict:
        fb = FirebaseService()
        u = str(unidad).upper()
        try:
            ultima = fb.obtener_ultima_lectura(dispositivo=dispositivo) or fb.obtener_ultima_lectura()
            temp_c = valor if 'C' in u else (ultima["temperatura_celsius"] if ultima else 14.0)
            hum_pct = valor if '%' in u else (ultima["humedad_ambiente_pct"] if ultima else 60.0)
            publicado = fb.publicar_telemetria(
                dispositivo=dispositivo,
                temperatura_celsius=temp_c,
                humedad_ambiente_pct=hum_pct,
                corral_id=corral_id,
            )
            return {"sincronizado": True, "registro_id": publicado["id"]}
        except Exception as exc:
            logger.warning("Lectura guardada en BD local pero diferida hacia Firebase: %s", exc)
            return {"sincronizado": False, "detalle": str(exc)}


class TelemetriaFirebaseAPIView(APIView):
    """
    Maneja los datos de telemetría directamente desde y hacia Firebase Realtime Database (`/telemetria`)
    y los envía mediante la API validando rangos físicos y riesgos sanitarios.
    """
    serializer_class = TelemetriaFirebaseInputSerializer

    def get(self, request, *args, **kwargs):
        limit_raw = request.query_params.get('limit', '25')
        dispositivo = request.query_params.get('dispositivo')
        try:
            limit = max(1, min(int(limit_raw), 200))
        except ValueError:
            limit = 25

        fb = FirebaseService()
        try:
            registros = fb.obtener_telemetria(limit=limit, dispositivo=dispositivo)
        except Exception as exc:
            return Response(
                {"error": "No fue posible obtener la telemetría desde Firebase.", "detalle": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "status": "success",
                "proyecto_firebase": "appmoncopullisensores",
                "nodo": "telemetria",
                "total": len(registros),
                "datos": registros,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        serializer = TelemetriaFirebaseInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        datos = serializer.validated_data
        fb = FirebaseService()
        try:
            publicado = fb.publicar_telemetria(
                dispositivo=datos['dispositivo'],
                temperatura_celsius=datos['temperatura_celsius'],
                humedad_ambiente_pct=datos['humedad_ambiente_pct'],
                corral_id=datos['corral_id'],
            )
            for alerta in publicado.get("alertas_detectadas", []):
                fb.publicar_alerta({
                    **alerta,
                    "dispositivo": datos['dispositivo'],
                    "corral_id": datos['corral_id'],
                })
        except Exception as exc:
            return Response(
                {"error": "No fue posible publicar la telemetría en Firebase.", "detalle": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "status": "success",
                "mensaje": "Telemetría publicada en Firebase Realtime Database correctamente.",
                "registro": publicado,
            },
            status=status.HTTP_201_CREATED,
        )


class UltimaTelemetriaFirebaseAPIView(APIView):
    """
    Obtiene el último registro válido en vivo desde `/telemetria` en Firebase Realtime Database.
    """
    serializer_class = serializers.Serializer

    def get(self, request, *args, **kwargs):
        dispositivo = request.query_params.get('dispositivo')
        fb = FirebaseService()
        try:
            ultima = fb.obtener_ultima_lectura(dispositivo=dispositivo)
        except Exception as exc:
            return Response(
                {"error": "Error al consultar la última lectura en Firebase.", "detalle": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if ultima is None:
            return Response(
                {"status": "empty", "mensaje": "No se encontraron lecturas válidas en /telemetria."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "status": "success",
                "lectura": ultima,
            },
            status=status.HTTP_200_OK,
        )


class SincronizarFirebaseAPIView(APIView):
    """
    Sincroniza los registros recientes de `/telemetria` en Firebase Realtime Database
    con las tablas transaccionales de Django (`Sensor`, `LecturaSensor`, `Alerta`).
    """
    serializer_class = serializers.Serializer

    def post(self, request, *args, **kwargs):
        limit_raw = request.data.get('limit', 20)
        try:
            limit = max(1, min(int(limit_raw), 100))
        except (TypeError, ValueError):
            limit = 20

        fb = FirebaseService()
        try:
            resumen = fb.sincronizar_telemetria_con_bd(limit=limit)
        except Exception as exc:
            return Response(
                {"error": "Error al sincronizar datos desde Firebase.", "detalle": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "status": "success",
                "mensaje": "Sincronización entre Firebase y Django completada.",
                "resumen": resumen,
            },
            status=status.HTTP_200_OK,
        )


class CorralesEstadoAPIView(APIView):
    """
    Envía mediante la API el estado de los corrales combinando los datos en vivo
    de Firebase Realtime Database (`/telemetria`).
    """
    serializer_class = serializers.Serializer

    def get(self, request, *args, **kwargs):
        fb = FirebaseService()
        corrales = fb.obtener_estado_corrales()
        return Response(
            {
                "status": "success",
                "total": len(corrales),
                "corrales": corrales,
            },
            status=status.HTTP_200_OK,
        )


class CorralHistorialAPIView(APIView):
    """
    Envía el historial de humedad y temperatura de un corral desde Firebase `/telemetria`.
    """
    serializer_class = serializers.Serializer

    def get(self, request, corral_id: int, *args, **kwargs):
        if not (1 <= corral_id <= 100):
            return Response({"error": "ID de corral fuera de rango."}, status=status.HTTP_400_BAD_REQUEST)

        limit_raw = request.query_params.get('limit', '25')
        try:
            limit = max(1, min(int(limit_raw), 200))
        except ValueError:
            limit = 25

        fb = FirebaseService()
        try:
            historial = fb.obtener_historial_corral(corral_id=corral_id, limit=limit)
        except Exception as exc:
            return Response(
                {"error": "Error al obtener historial desde Firebase.", "detalle": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "status": "success",
                **historial,
            },
            status=status.HTTP_200_OK,
        )


class SensoresListCreateAPIView(APIView):
    """
    Lista e inscribe sensores en el sistema.
    """
    serializer_class = SensorSerializer

    def get(self, request, *args, **kwargs):
        sensores = Sensor.objects.all().order_by('id')
        return Response(
            {
                "status": "success",
                "total": sensores.count(),
                "sensores": SensorSerializer(sensores, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        perm = EsAdministradorOVeterinario()
        if not perm.has_permission(request, self):
            return Response({"error": perm.message}, status=status.HTTP_403_FORBIDDEN)

        serializer = SensorSerializer(data=request.data)
        if serializer.is_valid():
            sensor = serializer.save()
            return Response(SensorSerializer(sensor).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AlertasAPIView(APIView):
    """
    Lista las alertas sanitarias registradas y las alertas activas detectadas en Firebase.
    """
    serializer_class = AlertaSerializer

    def get(self, request, *args, **kwargs):
        estado = request.query_params.get('estado_lectura')
        qs = Alerta.objects.select_related('sensor').order_by('-fecha_hora')
        if estado:
            qs = qs.filter(estado_lectura=estado.strip().upper())

        alertas_bd = AlertaSerializer(qs[:100], many=True).data

        fb = FirebaseService()
        ultima_fb = None
        try:
            ultima_fb = fb.obtener_ultima_lectura()
        except Exception:
            pass

        return Response(
            {
                "status": "success",
                "total_bd": len(alertas_bd),
                "alertas": alertas_bd,
                "alertas_en_vivo_firebase": ultima_fb.get("alertas_detectadas", []) if ultima_fb else [],
            },
            status=status.HTTP_200_OK,
        )


class AlertaDetailAPIView(APIView):
    """
    Permite actualizar el `estado_lectura` (`PENDIENTE` -> `LEIDA` o `RESUELTA`) de una alerta.
    """
    serializer_class = AlertaSerializer

    def patch(self, request, alerta_id: int, *args, **kwargs):
        try:
            alerta = Alerta.objects.select_related('sensor').get(id=alerta_id)
        except Alerta.DoesNotExist:
            return Response({"error": "Alerta no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AlertaSerializer(alerta, data=request.data, partial=True)
        if serializer.is_valid():
            alerta_actualizada = serializer.save()
            return Response(
                {
                    "status": "success",
                    "alerta": AlertaSerializer(alerta_actualizada).data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerificacionRFIDOrdeñaAPIView(APIView):
    """
    Integra la lectura de collares RFID en las 38 bajadas de la lechería
    y valida el bloqueo de leche por antibióticos.
    """
    serializer_class = VerificacionRFIDInputSerializer

    def post(self, request, *args, **kwargs):
        codigo_rfid = request.data.get('codigo_rfid')
        bajada = request.data.get('bajada')  # 1 al 38

        if not codigo_rfid:
            return Response({"error": "Código RFID de collar requerido."}, status=status.HTTP_400_BAD_REQUEST)

        if bajada is not None:
            try:
                bajada_int = int(bajada)
                if not (1 <= bajada_int <= 38):
                    return Response(
                        {"error": "El número de bajada debe estar entre 1 y 38."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (TypeError, ValueError):
                return Response({"error": "El número de bajada debe ser un entero."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            collar = CollarRfid.objects.get(codigo=str(codigo_rfid).strip(), activo=True)
            animal = Animal.objects.get(collar_rfid=collar)
        except (CollarRfid.DoesNotExist, Animal.DoesNotExist):
            return Response(
                {"error": "Collar RFID no registrado o inactivo en el hato."},
                status=status.HTTP_404_NOT_FOUND,
            )

        tratamiento_activo = (
            Tratamiento.objects.filter(
                evento_sanitario=animal.evento_sanitario,
                bloqueo_leche=True,
                fecha_fin__isnull=True,
            ).exists()
            if animal.evento_sanitario
            else False
        )

        if tratamiento_activo:
            return Response(
                {
                    "rfid": codigo_rfid,
                    "animal_id": animal.id,
                    "bajada": bajada,
                    "bloquear_ordenia": True,
                    "alerta_visual": "ALERTA CRÍTICA: Leche con Antibiótico – Aislar",
                    "color": "ROJO",
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "rfid": codigo_rfid,
                "animal_id": animal.id,
                "bajada": bajada,
                "bloquear_ordenia": False,
                "alerta_visual": "Ordeña Habilitada",
                "color": "VERDE",
            },
            status=status.HTTP_200_OK,
        )


class LoginPINAPIView(APIView):
    """
    Endpoint para autenticación de usuarios operacionales y administrativos mediante PIN de 6 dígitos.
    Emite tokens JWT firmados (`access` y `refresh`) y retorna el rol y permisos RBAC.
    Protegido con rate-limiting (`login_pin`) contra ataques de fuerza bruta.
    """
    serializer_class = LoginPINSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login_pin'

    def post(self, request, *args, **kwargs):
        serializer = LoginPINSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        pin = serializer.validated_data['pin']

        try:
            usuario = Usuario.objects.select_related('rol').get(email=email, activo=True)
        except Usuario.DoesNotExist:
            return Response(
                {"error": "Credenciales inválidas o usuario inactivo."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Verificación criptográfica segura en tiempo constante del PIN hasheado
        if not check_password(pin, usuario.password_hash):
            logger.warning("Intento fallido de login por PIN para el usuario: %s", email)
            return Response({"error": "Credenciales inválidas o usuario inactivo."}, status=status.HTTP_401_UNAUTHORIZED)

        rol_nombre = usuario.rol.nombre.upper() if usuario.rol else "OPERADOR"
        tokens = generar_tokens_para_usuario(usuario)

        return Response(
            {
                "status": "success",
                "mensaje": f"Bienvenido, {usuario.nombre}",
                "tokens": tokens,
                "usuario": UsuarioSerializer(usuario).data,
                "permisos": construir_permisos_rol(rol_nombre),
            },
            status=status.HTTP_200_OK,
        )


class RegistroUsuarioPINAPIView(APIView):
    """
    Endpoint administrativo para registrar nuevos usuarios asignándoles un PIN de 6 dígitos.
    Requiere rol ADMINISTRADOR (o bootstrapping inicial si la tabla de usuarios está vacía).
    """
    serializer_class = RegistroUsuarioPINSerializer
    permission_classes = [PermisoRegistroUsuario]

    def post(self, request, *args, **kwargs):
        serializer = RegistroUsuarioPINSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.save()
            logger.info("Usuario registrado exitosamente con PIN: %s", usuario.email)
            return Response(
                {
                    "status": "success",
                    "mensaje": "Usuario creado exitosamente con autenticación por PIN.",
                    "usuario": UsuarioSerializer(usuario).data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RolesListCreateAPIView(APIView):
    """
    Permite consultar o crear roles del organigrama (ADMINISTRADOR, VETERINARIO, PARTERO, TERNERERO, LECHERO).
    """
    serializer_class = RolSerializer
    permission_classes = [PermisoRegistroUsuario]

    def get(self, request, *args, **kwargs):
        roles = Rol.objects.all().order_by('id')
        return Response(RolSerializer(roles, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = RolSerializer(data=request.data)
        if serializer.is_valid():
            rol = serializer.save()
            return Response(RolSerializer(rol).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RefreshTokenPINAPIView(APIView):
    """
    Rota y emite nuevos tokens JWT (`access` y `refresh`) para usuarios operativos (`Usuario`)
    preservando sus claims RBAC y verificando que el usuario siga activo.
    """
    serializer_class = RefreshTokenPINSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RefreshTokenPINSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        raw_refresh = serializer.validated_data['refresh']
        try:
            refresh_token = RefreshToken(raw_refresh)
        except TokenError:
            return Response(
                {"error": "Token refresh inválido o expirado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        usuario_id = refresh_token.get('usuario_id') or refresh_token.get('user_id')
        if not usuario_id:
            return Response(
                {"error": "El token no contiene identificador de usuario válido."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            usuario = Usuario.objects.select_related('rol').get(id=usuario_id, activo=True)
        except Usuario.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado o inactivo."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        tokens = generar_tokens_para_usuario(usuario)
        return Response(tokens, status=status.HTTP_200_OK)
