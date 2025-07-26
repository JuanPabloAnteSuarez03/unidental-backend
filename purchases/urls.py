from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PurchaseOrderViewSet,
    PurchaseOrderItemViewSet,
    PurchaseOrderPaymentViewSet,
)

# Crear el router
router = DefaultRouter()
router.register(r'orders', PurchaseOrderViewSet, basename='purchaseorder')
router.register(r'items', PurchaseOrderItemViewSet, basename='purchaseorderitem')
router.register(r'payments', PurchaseOrderPaymentViewSet)

# URLs de la aplicación
urlpatterns = [
    path('', include(router.urls)),
] 