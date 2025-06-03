"""
Configuración de URLs para la aplicación de ventas.

Este módulo define las rutas para acceder a los diferentes endpoints
relacionados con la gestión de ventas, clientes y detalles de venta.
"""

from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import CustomerViewSet, SaleViewSet, SaleItemViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'sales', SaleViewSet)
router.register(r'sale-items', SaleItemViewSet)

app_name = 'sales'

urlpatterns = [
    path('', include(router.urls)),
] 