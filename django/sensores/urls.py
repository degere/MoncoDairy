from django.urls import path
from .views import (
    IngestaIoTAPIView, 
    VerificacionRFIDOrdeñaAPIView,
    LoginPINAPIView,
    RegistroUsuarioPINAPIView
)

urlpatterns = [
    # Endpoints IoT y RFID
    path('api/iot/ingesta/', IngestaIoTAPIView.as_view(), name='ingesta-iot'),
    path('api/ordeña/rfid/', VerificacionRFIDOrdeñaAPIView.as_view(), name='verificacion-rfid-ordena'),
    
    # Endpoints Autenticación PIN 
    path('api/auth/login-pin/', LoginPINAPIView.as_view(), name='login-pin'),
    path('api/auth/registro-pin/', RegistroUsuarioPINAPIView.as_view(), name='registro-pin'),
]