"""
Configuración de URLs para la aplicación de créditos.

Este módulo define las rutas para acceder a los diferentes endpoints
relacionados con la gestión de créditos y cobranzas.
"""

from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    CreditAccountViewSet, CreditPaymentViewSet,
    CreditPurchaseAccountViewSet, CreditPurchasePaymentViewSet,
    overdue_debts_page
)

router = DefaultRouter()
router.register(r'accounts', CreditAccountViewSet)
router.register(r'payments', CreditPaymentViewSet)
router.register(r'purchase-accounts', CreditPurchaseAccountViewSet)
router.register(r'purchase-payments', CreditPurchasePaymentViewSet)

app_name = 'credits'

urlpatterns = [
    path('', include(router.urls)),
    path('overdue-debts/', overdue_debts_page, name='overdue_debts_page'),
] 