from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import connection, DatabaseError
from django.core.cache import cache


@api_view(['GET', 'HEAD'])
@permission_classes([AllowAny])
def health_check_view(request):
    """
    Endpoint de Health Check para verificar el estado de los servicios críticos.
    
    Verifica:
    - Conexión a la base de datos.
    - Funcionamiento del sistema de caché.
    
    Devuelve un estado 200 OK si todos los servicios están operativos,
    o un 503 Service Unavailable si alguno de los servicios críticos falla.
    
    Soporta métodos GET y HEAD:
    - GET: Devuelve el estado completo de los servicios
    - HEAD: Devuelve solo el código de estado HTTP sin cuerpo de respuesta
    """
    services_status = {
        'database': 'ok',
        'cache': 'ok'
    }
    overall_status = status.HTTP_200_OK

    # 1. Verificar la conexión a la base de datos
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        services_status['database'] = 'error'
        overall_status = status.HTTP_503_SERVICE_UNAVAILABLE

    # 2. Verificar la caché
    try:
        cache.set('health_check_test', 'ok', timeout=10)
        cached_value = cache.get('health_check_test')
        if cached_value != 'ok':
            raise Exception("Valor de caché no coincide")
        cache.delete('health_check_test')
    except Exception:
        services_status['cache'] = 'error'
        overall_status = status.HTTP_503_SERVICE_UNAVAILABLE

    # Para HEAD requests, devolver solo el código de estado sin cuerpo
    if request.method == 'HEAD':
        return Response(status=overall_status)
    
    # Para GET requests, devolver el estado completo
    return Response(services_status, status=overall_status)
