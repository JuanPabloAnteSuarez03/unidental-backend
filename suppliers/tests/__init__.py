"""
Tests para el módulo suppliers.

Este módulo contiene todos los tests para:
- Modelos (Supplier, PurchaseOption)
- Serializers (SupplierSerializer, PurchaseOptionSerializer, etc.)
- API endpoints (ViewSets y acciones personalizadas)  
- Filtros (SupplierFilter, PurchaseOptionFilter)

Todos los tests están implementados usando pytest en lugar de Django TestCase
para mejor integración con sistemas de CI/CD.

Estructura de tests:
- test_models.py: Tests de modelos y validaciones
- test_serializers.py: Tests de serialización/deserialización
- test_api.py: Tests de endpoints y API
- test_filters.py: Tests de filtros y búsquedas
- conftest.py: Fixtures compartidas para todos los tests
"""

# Importar todos los módulos de tests para que pytest los descubra automáticamente
from .test_models import *
from .test_serializers import *
from .test_api import *
from .test_filters import *

__all__ = [
    'test_models',
    'test_serializers', 
    'test_api',
    'test_filters'
] 