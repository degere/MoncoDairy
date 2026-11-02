from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import Sensor, LecturaSensor, Alerta, Animal, CollarRfid, Tratamiento
import logging
# Create your views here.

logger = logging.getLogger(__name__)

class IngestaIoTAPIView(APIView):

    def post(self, request, *args, **kwargs):
        data = request.data
        sensor_id = data.get('sensor_id')
        valor = data.get('valor')
        unidad = data.get('unidad') # '°C' o '%'

        if not sensor_id or valor is None or not unidad:
            return Response({"error": "Faltan parámetros obligatorios (sensor_id, valor, unidad)."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sensor = Sensor.objects.get(id=sensor_id)
        except Sensor.DoesNotExist:
            return Response({"error": "El sensor especificado no existe."}, status=status.HTTP_404_NOT_FOUND)

        val_float = float(valor)

        # 1. Filtro de Rango Físico
        if not self._validar_rango_fisico(unidad, val_float):
            logger.warning(f"Lectura anómala descartada del sensor {sensor_id}: {val_float} {unidad}")
            return Response({"error": "Lectura fuera de rango físico real. Dato descartado."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Guardar Lectura en BD Transaccional
        lectura = LecturaSensor.objects.create(
            sensor=sensor,
            valor=val_float,
            unidad=unidad,
            fecha_hora=timezone.now()
        )

        # 3. Motor de Alertas Sanitaria Enfocado en Terneros
        self._evaluar_riesgo_terneros(sensor, lectura, val_float, unidad)

        return Response({"status": "success", "mensaje": "Lectura de ternerera procesada correctamente."}, status=status.HTTP_201_CREATED)

    def _validar_rango_fisico(self, unidad, valor):
        u = unidad.upper()
        if 'C' in u and not (-20.0 <= valor <= 45.0):
            return False
        if '%' in u and not (0.0 <= valor <= 100.0):
            return False
        return True

    def _evaluar_riesgo_terneros(self, sensor, lectura, valor, unidad):

        u = unidad.upper()

        # A. Evaluación de Temperatura (Frío y Calor en Ternereras)
        if 'C' in u:
            if valor < 10.0:  # Estrés por frío / Hipotermia (< 10°C)
                Alerta.objects.create(
                    sensor=sensor,
                    lectura_sensor=lectura,
                    tipo_alerta="ESTRES_FRIO_TERNERO",
                    nivel="ROJO",
                    fecha_hora=timezone.now(),
                    mensaje=f"¡ALERTA DE FRÍO EN TERNERERA! Temperatura de {valor}°C. Riesgo de hipotermia y neumonía neonatal.",
                    estado_lectura="PENDIENTE"
                )
                logger.warning(f"Push enviado a parteros/ternereros: Frío crítico ({valor}°C) en {sensor.ubicacion}")

            elif valor > 25.0: # Estrés por calor (> 25°C)
                Alerta.objects.create(
                    sensor=sensor,
                    lectura_sensor=lectura,
                    tipo_alerta="ESTRES_CALOR_TERNERO",
                    nivel="AMARILLO",
                    fecha_hora=timezone.now(),
                    mensaje=f"Alerta de Calor en Ternerera: Temperatura de {valor}°C. Verificar ventilación e hidratación de terneros.",
                    estado_lectura="PENDIENTE"
                )

        # B. Evaluación de Humedad en Camas de Paja (>= 80%)
        elif '%' in u:
            if valor >= 80.0:
                Alerta.objects.create(
                    sensor=sensor,
                    lectura_sensor=lectura,
                    tipo_alerta="CAMAS_CALIENTES_HUMEDAD",
                    nivel="ROJO",
                    fecha_hora=timezone.now(),
                    mensaje=f"¡ALERTA DE CAMA HÚMEDA! Humedad de la paja al {valor}%. Realizar recambio de paja para prevenir neumonías y diarreas entéricas.",
                    estado_lectura="PENDIENTE"
                )
                logger.warning(f"Push enviado a ternereros: Recambio de paja requerido en {sensor.ubicacion}")


class VerificacionRFIDOrdeñaAPIView(APIView):
    """
    Integra la lectura de collares RFID en las 38 bajadas de la lechería
    y valida el bloqueo de leche por antibióticos.
    """
    def post(self, request, *args, **kwargs):
        codigo_rfid = request.data.get('codigo_rfid')
        bajada = request.data.get('bajada') # 1 al 38

        if not codigo_rfid:
            return Response({"error": "Código RFID de collar requerido."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            collar = CollarRfid.objects.get(codigo=codigo_rfid, activo=True)
            animal = Animal.objects.get(collar_rfid=collar)
        except (CollarRfid.DoesNotExist, Animal.DoesNotExist):
            return Response({"error": "Collar RFID no registrado o inactivo en el hato."}, status=status.HTTP_404_NOT_FOUND)

        # Verificar si tiene un tratamiento activo con bloqueo de leche
        tratamiento_activo = Tratamiento.objects.filter(
            evento_sanitario=animal.evento_sanitario,
            bloqueo_leche=True,
            fecha_fin__isnull=True
        ).exists() if animal.evento_sanitario else False

        if tratamiento_activo:
            return Response({
                "rfid": codigo_rfid,
                "animal_id": animal.id,
                "bajada": bajada,
                "bloquear_ordenia": True,
                "alerta_visual": "ALERTA CRÍTICA: Leche con Antibiótico – Aislar",
                "color": "ROJO"
            }, status=status.HTTP_200_OK)

        return Response({
            "rfid": codigo_rfid,
            "animal_id": animal.id,
            "bajada": bajada,
            "bloquear_ordenia": False,
            "alerta_visual": "Ordeña Habilitada",
            "color": "VERDE"
        }, status=status.HTTP_200_OK)