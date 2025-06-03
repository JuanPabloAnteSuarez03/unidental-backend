"""
Configuración de URLs para la aplicación de créditos.

Este módulo define las rutas para acceder a los diferentes endpoints
relacionados con la gestión de créditos y cobranzas.
"""

from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import CreditAccountViewSet, CreditPaymentViewSet

router = DefaultRouter()
router.register(r'accounts', CreditAccountViewSet)
router.register(r'payments', CreditPaymentViewSet)

app_name = 'credits'

urlpatterns = [
    path('', include(router.urls)),
] 