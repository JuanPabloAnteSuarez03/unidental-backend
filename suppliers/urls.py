from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SupplierViewSet, PurchaseOptionViewSet

router = DefaultRouter()
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'purchase-options', PurchaseOptionViewSet, basename='purchaseoption')

urlpatterns = [
    path('', include(router.urls)),
] 