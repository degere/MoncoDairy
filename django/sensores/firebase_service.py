"""
Servicio de integración segura con Firebase Realtime Database y Cloud Firestore
para el proyecto MoncoDairy (`appmoncopullisensores`).

Soporta autenticación de servidor mediante:
1. Firebase Admin SDK (`serviceAccountKey.json` o `GOOGLE_APPLICATION_CREDENTIALS`).
2. Token OAuth2 autenticado de Firebase CLI (`~/.config/configstore/firebase-tools.json`)
   para entornos locales donde el desarrollador inició sesión con `firebase login`.
"""

from datetime import datetime, timezone as dt_timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone
import firebase_admin
from firebase_admin import db as firebase_rtdb
import requests

logger = logging.getLogger(__name__)

NODO_TELEMETRIA = "telemetria"
NODO_ALERTAS = "alertas"
NODO_CORRALES = "corrales"

TEMP_MIN_SENSOR = -20.0
TEMP_MAX_SENSOR = 70.0
TEMP_MIN_FISICO_TERNERERA = -20.0
TEMP_MAX_FISICO_TERNERERA = 45.0
HUM_MIN_SENSOR = 0.0
HUM_MAX_SENSOR = 100.0

# Datos base de los 20 corrales cuando aún no tienen un sensor físico asignado
_HUMEDAD_BASE_CORRALES = [
    82, 65, 85, 70, 55, 78, 62, 90, 48, 73,
    80, 58, 88, 66, 52, 76, 83, 60, 68, 79,
]
_TEMP_BASE_CORRALES = [
    9, 12, 8, 11, 14, 10, 13, 7, 15, 11,
    9, 13, 8, 12, 14, 10, 9, 13, 12, 10,
]


def evaluar_riesgos_sanitarios(temperatura_c: Optional[float], humedad_pct: Optional[float], ubicacion: str = "Corral 1") -> list[dict[str, Any]]:
    """
    Evalúa los umbrales sanitarios de ternerera para temperatura y humedad de cama.
    Retorna la lista de alertas detectadas.
    """
    alertas: list[dict[str, Any]] = []
    ahora_iso = timezone.now().isoformat()

    if temperatura_c is not None:
        if temperatura_c < 10.0:
            alertas.append({
                "tipo_alerta": "ESTRES_FRIO_TERNERO",
                "nivel": "ROJO",
                "valor": round(float(temperatura_c), 2),
                "unidad": "°C",
                "fecha_hora": ahora_iso,
                "estado_lectura": "PENDIENTE",
                "mensaje": (
                    f"¡ALERTA DE FRÍO EN TERNERERA ({ubicacion})! "
                    f"Temperatura de {temperatura_c}°C. Riesgo de hipotermia y neumonía neonatal."
                ),
            })
        elif temperatura_c > 25.0:
            alertas.append({
                "tipo_alerta": "ESTRES_CALOR_TERNERO",
                "nivel": "AMARILLO",
                "valor": round(float(temperatura_c), 2),
                "unidad": "°C",
                "fecha_hora": ahora_iso,
                "estado_lectura": "PENDIENTE",
                "mensaje": (
                    f"Alerta de Calor en Ternerera ({ubicacion}): "
                    f"Temperatura de {temperatura_c}°C. Verificar ventilación e hidratación de terneros."
                ),
            })

    if humedad_pct is not None and humedad_pct >= 80.0:
        alertas.append({
            "tipo_alerta": "CAMAS_CALIENTES_HUMEDAD",
            "nivel": "ROJO",
            "valor": round(float(humedad_pct), 2),
            "unidad": "%",
            "fecha_hora": ahora_iso,
            "estado_lectura": "PENDIENTE",
            "mensaje": (
                f"¡ALERTA DE CAMA HÚMEDA ({ubicacion})! "
                f"Humedad de la paja al {humedad_pct}%. Realizar recambio de paja para prevenir neumonías y diarreas entéricas."
            ),
        })

    return alertas


def clasificar_nivel_humedad(humedad_pct: float) -> str:
    if humedad_pct >= 75.0:
        return "CRITICO"
    if humedad_pct > 60.0:
        return "ALERTA"
    return "OK"


def validar_registro_telemetria(registro_id: str, raw: Any) -> Optional[dict[str, Any]]:
    """
    Valida la estructura, tipos y rangos de un registro de `/telemetria/$registro_id`.
    Retorna un diccionario normalizado o `None` si el registro es inválido/corrupto.
    """
    if not isinstance(raw, dict):
        return None

    lecturas = raw.get("lecturas_crudas")
    if not isinstance(lecturas, dict):
        return None

    dispositivo = raw.get("dispositivo")
    temp_raw = lecturas.get("temperatura_celsius")
    hum_raw = lecturas.get("humedad_ambiente_pct")

    if not isinstance(dispositivo, str) or not (1 <= len(dispositivo.strip()) <= 64):
        return None
    if isinstance(temp_raw, bool) or not isinstance(temp_raw, (int, float)):
        return None
    if isinstance(hum_raw, bool) or not isinstance(hum_raw, (int, float)):
        return None

    temp = float(temp_raw)
    hum = float(hum_raw)

    if not (TEMP_MIN_SENSOR <= temp <= TEMP_MAX_SENSOR):
        return None
    if not (HUM_MIN_SENSOR <= hum <= HUM_MAX_SENSOR):
        return None

    corral_id_raw = raw.get("corral_id", 1)
    corral_id = int(corral_id_raw) if isinstance(corral_id_raw, (int, float)) and not isinstance(corral_id_raw, bool) else 1

    timestamp = raw.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.strip():
        timestamp = timezone.now().isoformat()

    fecha_local = raw.get("fecha_local")
    if not isinstance(fecha_local, str):
        fecha_local = ""

    ubicacion = f"Corral {corral_id} ({dispositivo.strip()})"
    alertas = evaluar_riesgos_sanitarios(temp, hum, ubicacion=ubicacion)

    return {
        "id": str(registro_id),
        "dispositivo": dispositivo.strip(),
        "corral_id": corral_id,
        "temperatura_celsius": round(temp, 2),
        "humedad_ambiente_pct": round(hum, 2),
        "timestamp": timestamp,
        "fecha_local": fecha_local,
        "nivel_humedad": clasificar_nivel_humedad(hum),
        "temperatura_baja": temp < 12.0,
        "rango_fisico_valido": (TEMP_MIN_FISICO_TERNERERA <= temp <= TEMP_MAX_FISICO_TERNERERA),
        "alertas_detectadas": alertas,
    }


class FirebaseService:
    """
    Cliente unificado para interactuar con Firebase Realtime Database (`appmoncopullisensores`).
    """

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = (
            database_url
            or getattr(settings, "FIREBASE_DATABASE_URL", "https://appmoncopullisensores-default-rtdb.firebaseio.com")
        ).rstrip("/")
        self._session = requests.Session()

    def _usar_admin_sdk(self) -> bool:
        return bool(firebase_admin._apps)

    def _obtener_token_cli(self) -> Optional[str]:
        """
        Obtiene el access_token OAuth2 activo desde la configuración local de Firebase CLI
        (`~/.config/configstore/firebase-tools.json`) si está disponible.
        """
        token_env = os.environ.get("FIREBASE_ACCESS_TOKEN")
        if token_env:
            return token_env.strip()

        config_path = Path.home() / ".config" / "configstore" / "firebase-tools.json"
        if not config_path.exists():
            return None

        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            tokens = data.get("tokens") or {}
            access_token = tokens.get("access_token")
            if isinstance(access_token, str) and access_token.strip():
                return access_token.strip()
        except Exception as exc:
            logger.debug("No se pudo leer el token de Firebase CLI: %s", exc)
        return None

    def _rest_get(self, path: str, params: Optional[dict[str, str]] = None) -> Any:
        clean_path = path.strip("/")
        url = f"{self.database_url}/{clean_path}.json"
        query_params = dict(params or {})
        headers: dict[str, str] = {}

        token = self._obtener_token_cli()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = self._session.get(url, params=query_params, headers=headers, timeout=10)
        if resp.status_code == 401 and "Authorization" in headers:
            resp = self._session.get(url, params=query_params, timeout=10)

        resp.raise_for_status()
        return resp.json()

    def _rest_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean_path = path.strip("/")
        url = f"{self.database_url}/{clean_path}.json"
        headers: dict[str, str] = {}

        token = self._obtener_token_cli()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = self._session.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json() or {}

    def _rest_put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean_path = path.strip("/")
        url = f"{self.database_url}/{clean_path}.json"
        headers: dict[str, str] = {}

        token = self._obtener_token_cli()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = self._session.put(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json() or {}

    def obtener_telemetria(self, limit: int = 50, dispositivo: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Recupera y valida los últimos registros del nodo `/telemetria` en Firebase Realtime Database.
        Devuelve los registros ordenados del más reciente al más antiguo.
        """
        limit = max(1, min(int(limit), 500))
        raw_data: Any = None

        try:
            if self._usar_admin_sdk():
                ref = firebase_rtdb.reference(NODO_TELEMETRIA)
                raw_data = ref.order_by_key().limit_to_last(limit).get()
            else:
                params = {
                    "orderBy": json.dumps("$key"),
                    "limitToLast": str(limit),
                }
                raw_data = self._rest_get(NODO_TELEMETRIA, params=params)
        except Exception as exc:
            logger.error("Error al consultar /telemetria en Firebase: %s", exc)
            raise

        if not isinstance(raw_data, dict):
            return []

        registros: list[dict[str, Any]] = []
        for reg_id in sorted(raw_data.keys(), reverse=True):
            validado = validar_registro_telemetria(reg_id, raw_data[reg_id])
            if validado is None:
                continue
            if dispositivo and validado["dispositivo"].lower() != dispositivo.strip().lower():
                continue
            registros.append(validado)

        return registros

    def obtener_ultima_lectura(self, dispositivo: Optional[str] = None) -> Optional[dict[str, Any]]:
        """
        Devuelve la lectura válida más reciente desde `/telemetria`.
        """
        limit = 20 if dispositivo else 5
        registros = self.obtener_telemetria(limit=limit, dispositivo=dispositivo)
        return registros[0] if registros else None

    def publicar_telemetria(
        self,
        dispositivo: str,
        temperatura_celsius: float,
        humedad_ambiente_pct: float,
        corral_id: int = 1,
    ) -> dict[str, Any]:
        """
        Valida y publica un nuevo registro en `/telemetria` de Firebase Realtime Database.
        """
        ahora = timezone.localtime(timezone.now())
        ahora_utc = timezone.now().astimezone(dt_timezone.utc)

        payload = {
            "dispositivo": str(dispositivo).strip()[:64],
            "corral_id": int(corral_id),
            "fecha_local": ahora.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": ahora_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lecturas_crudas": {
                "temperatura_celsius": round(float(temperatura_celsius), 2),
                "humedad_ambiente_pct": round(float(humedad_ambiente_pct), 2),
            },
        }

        validado = validar_registro_telemetria("pending", payload)
        if validado is None:
            raise ValueError("Los datos de telemetría no cumplen el esquema o rango permitido.")

        try:
            if self._usar_admin_sdk():
                ref = firebase_rtdb.reference(NODO_TELEMETRIA)
                new_ref = ref.push(payload)
                reg_id = new_ref.key or "generated"
            else:
                res = self._rest_post(NODO_TELEMETRIA, payload)
                reg_id = res.get("name", "generated")
        except Exception as exc:
            logger.error("Error al publicar en /telemetria de Firebase: %s", exc)
            raise

        validado["id"] = reg_id
        return validado

    def publicar_alerta(self, alerta_data: dict[str, Any]) -> Optional[str]:
        """
        Publica una alerta sanitaria en el nodo `/alertas` de Firebase Realtime Database.
        """
        payload = {
            "tipo_alerta": str(alerta_data.get("tipo_alerta", "ESTRES_FRIO_TERNERO")),
            "nivel": str(alerta_data.get("nivel", "ROJO")),
            "mensaje": str(alerta_data.get("mensaje", ""))[:500],
            "fecha_hora": str(alerta_data.get("fecha_hora") or timezone.now().isoformat()),
            "estado_lectura": str(alerta_data.get("estado_lectura", "PENDIENTE")),
        }
        if "sensor_id" in alerta_data and alerta_data["sensor_id"] is not None:
            payload["sensor_id"] = alerta_data["sensor_id"]
        if "dispositivo" in alerta_data and alerta_data["dispositivo"]:
            payload["dispositivo"] = str(alerta_data["dispositivo"])[:64]
        if "corral_id" in alerta_data and alerta_data["corral_id"] is not None:
            payload["corral_id"] = int(alerta_data["corral_id"])
        if "valor" in alerta_data and alerta_data["valor"] is not None:
            payload["valor"] = round(float(alerta_data["valor"]), 2)
        if "unidad" in alerta_data and alerta_data["unidad"]:
            payload["unidad"] = str(alerta_data["unidad"])[:10]

        try:
            if self._usar_admin_sdk():
                ref = firebase_rtdb.reference(NODO_ALERTAS)
                new_ref = ref.push(payload)
                return new_ref.key
            else:
                res = self._rest_post(NODO_ALERTAS, payload)
                return res.get("name")
        except Exception as exc:
            logger.warning("No se pudo publicar alerta en Firebase (/alertas): %s", exc)
            return None

    def obtener_estado_corrales(self) -> list[dict[str, Any]]:
        """
        Devuelve el estado de los 20 corrales integrando las lecturas en tiempo real
        de Firebase Realtime Database (`/telemetria`).
        """
        ultima = None
        try:
            ultima = self.obtener_ultima_lectura()
        except Exception as exc:
            logger.warning("Usando respaldo para corrales por fallo en lectura Firebase: %s", exc)

        corrales: list[dict[str, Any]] = []
        for idx in range(20):
            corral_id = idx + 1
            es_corral_en_vivo = ultima is not None and ultima.get("corral_id", 1) == corral_id

            if es_corral_en_vivo and ultima is not None:
                hum = ultima["humedad_ambiente_pct"]
                temp = ultima["temperatura_celsius"]
                en_vivo = True
                dispositivo = ultima["dispositivo"]
                timestamp = ultima["timestamp"]
            else:
                hum = float(_HUMEDAD_BASE_CORRALES[idx])
                temp = float(_TEMP_BASE_CORRALES[idx])
                en_vivo = False
                dispositivo = None
                timestamp = None

            corrales.append({
                "id": corral_id,
                "nombre": f"Corral {corral_id}",
                "descripcion": "Galpón de partos" if corral_id == 3 else f"Galpón {corral_id}",
                "humedad": round(hum, 2),
                "temperatura": round(temp, 2),
                "nivel_humedad": clasificar_nivel_humedad(hum),
                "temperatura_baja": temp < 12.0,
                "enVivo": en_vivo,
                "dispositivo": dispositivo,
                "timestamp": timestamp,
            })

        return corrales

    def obtener_historial_corral(self, corral_id: int = 1, limit: int = 25) -> dict[str, Any]:
        """
        Obtiene el historial de lecturas de humedad y temperatura desde Firebase `/telemetria`
        para el corral solicitado.
        """
        registros = self.obtener_telemetria(limit=max(25, limit))
        filtrados = [r for r in registros if r.get("corral_id", 1) == corral_id]
        filtrados_cronologicos = list(reversed(filtrados[:limit]))

        return {
            "corral_id": corral_id,
            "total_registros": len(filtrados_cronologicos),
            "humedad_serie": [r["humedad_ambiente_pct"] for r in filtrados_cronologicos],
            "temperatura_serie": [r["temperatura_celsius"] for r in filtrados_cronologicos],
            "registros": filtrados_cronologicos,
        }

    def sincronizar_telemetria_con_bd(self, limit: int = 20) -> dict[str, Any]:
        """
        Sincroniza las lecturas recientes de `/telemetria` en Firebase Realtime Database
        con los modelos transaccionales de Django (`Sensor`, `LecturaSensor`, `Alerta`).
        """
        from .models import Alerta, LecturaSensor, Sensor

        registros = self.obtener_telemetria(limit=limit)
        lecturas_creadas = 0
        alertas_creadas = 0

        for reg in reversed(registros):
            dispositivo = reg["dispositivo"]
            corral_id = reg.get("corral_id", 1)
            ubicacion = f"Corral {corral_id} - {dispositivo}"

            sensor_temp, _ = Sensor.objects.get_or_create(
                ubicacion=ubicacion,
                tipo="TEMPERATURA",
                defaults={"estado": "ACTIVO"},
            )
            sensor_hum, _ = Sensor.objects.get_or_create(
                ubicacion=ubicacion,
                tipo="HUMEDAD",
                defaults={"estado": "ACTIVO"},
            )

            try:
                fecha_dt = datetime.fromisoformat(reg["timestamp"].replace("Z", "+00:00"))
            except ValueError:
                fecha_dt = timezone.now()

            # Evitar duplicar lecturas con el mismo sensor y timestamp exacto
            if not LecturaSensor.objects.filter(sensor=sensor_temp, fecha_hora=fecha_dt).exists():
                lectura_t = LecturaSensor.objects.create(
                    sensor=sensor_temp,
                    valor=reg["temperatura_celsius"],
                    unidad="°C",
                    fecha_hora=fecha_dt,
                )
                lecturas_creadas += 1

                for alerta_info in evaluar_riesgos_sanitarios(reg["temperatura_celsius"], None, ubicacion=ubicacion):
                    Alerta.objects.create(
                        sensor=sensor_temp,
                        lectura_sensor=lectura_t,
                        tipo_alerta=alerta_info["tipo_alerta"],
                        nivel=alerta_info["nivel"],
                        fecha_hora=fecha_dt,
                        mensaje=alerta_info["mensaje"],
                        estado_lectura="PENDIENTE",
                    )
                    alertas_creadas += 1

            if not LecturaSensor.objects.filter(sensor=sensor_hum, fecha_hora=fecha_dt).exists():
                lectura_h = LecturaSensor.objects.create(
                    sensor=sensor_hum,
                    valor=reg["humedad_ambiente_pct"],
                    unidad="%",
                    fecha_hora=fecha_dt,
                )
                lecturas_creadas += 1

                for alerta_info in evaluar_riesgos_sanitarios(None, reg["humedad_ambiente_pct"], ubicacion=ubicacion):
                    Alerta.objects.create(
                        sensor=sensor_hum,
                        lectura_sensor=lectura_h,
                        tipo_alerta=alerta_info["tipo_alerta"],
                        nivel=alerta_info["nivel"],
                        fecha_hora=fecha_dt,
                        mensaje=alerta_info["mensaje"],
                        estado_lectura="PENDIENTE",
                    )
                    alertas_creadas += 1

        return {
            "registros_firebase_procesados": len(registros),
            "lecturas_locales_creadas": lecturas_creadas,
            "alertas_generadas": alertas_creadas,
        }
