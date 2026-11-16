from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    AlertaDetailAPIView,
    AlertasAPIView,
    CorralesEstadoAPIView,
    CorralHistorialAPIView,
    IngestaIoTAPIView,
    LoginPINAPIView,
    RegistroUsuarioPINAPIView,
    RolesListCreateAPIView,
    SensoresListCreateAPIView,
    SincronizarFirebaseAPIView,
    TelemetriaFirebaseAPIView,
    UltimaTelemetriaFirebaseAPIView,
    VerificacionRFIDOrdeñaAPIView,
)

urlpatterns = [
    # Endpoints de Telemetría y Sincronización con Firebase Realtime Database
    path('api/telemetria/', TelemetriaFirebaseAPIView.as_view(), name='telemetria-firebase'),
    path('api/telemetria/ultima/', UltimaTelemetriaFirebaseAPIView.as_view(), name='telemetria-ultima'),
    path('api/firebase/sincronizar/', SincronizarFirebaseAPIView.as_view(), name='firebase-sincronizar'),

    # Endpoints de Corrales, Sensores y Alertas Sanitarias
    path('api/corrales/', CorralesEstadoAPIView.as_view(), name='corrales-estado'),
    path('api/corrales/<int:corral_id>/historial/', CorralHistorialAPIView.as_view(), name='corral-historial'),
    path('api/sensores/', SensoresListCreateAPIView.as_view(), name='sensores-list-create'),
    path('api/alertas/', AlertasAPIView.as_view(), name='alertas-list'),
    path('api/alertas/<int:alerta_id>/', AlertaDetailAPIView.as_view(), name='alerta-detail'),

    # Endpoints IoT y RFID Ordeña
    path('api/iot/ingesta/', IngestaIoTAPIView.as_view(), name='ingesta-iot'),
    path('api/ordeña/rfid/', VerificacionRFIDOrdeñaAPIView.as_view(), name='verificacion-rfid-ordena'),
    path('api/ordena/rfid/', VerificacionRFIDOrdeñaAPIView.as_view(), name='verificacion-rfid-ordena-ascii'),

    # Endpoints Autenticación PIN + JWT y Roles RBAC
    path('api/auth/login-pin/', LoginPINAPIView.as_view(), name='login-pin'),
    path('api/auth/registro-pin/', RegistroUsuarioPINAPIView.as_view(), name='registro-pin'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('api/auth/roles/', RolesListCreateAPIView.as_view(), name='roles-list-create'),
]
