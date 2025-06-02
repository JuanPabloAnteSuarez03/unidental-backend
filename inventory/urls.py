from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import LocationViewSet, InventoryStockViewSet, InventoryMovementViewSet

router = DefaultRouter()
router.register(r'locations', LocationViewSet, basename='location')
router.register(r'stock', InventoryStockViewSet, basename='inventorystock')
router.register(r'movements', InventoryMovementViewSet, basename='inventorymovement')

urlpatterns = [
    path('', include(router.urls)),
] 