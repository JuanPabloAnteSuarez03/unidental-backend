from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import time

# Create your views here.

@api_view(['GET'])
@permission_classes([AllowAny])  # Permitir acceso sin autenticación
def health_check(request):
    """
    Endpoint público para verificar el estado de la aplicación.
    No requiere autenticación - para uso de Railway healthcheck.
    """
    start_time = time.time()
    
    try:
        # Verificar conexión a la base de datos
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    response_time = (time.time() - start_time) * 1000
    
    health_data = {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "database": db_status,
        "response_time_ms": round(response_time, 2),
        "timestamp": time.time()
    }
    
    status_code = 200 if db_status == "healthy" else 503
    
    return JsonResponse(health_data, status=status_code)
