from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, sku_info, generate_sku, validate_sku

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
    # Endpoints informativos para el sistema SKU
    path('sku/info/', sku_info, name='sku-info'),
    path('sku/generate/', generate_sku, name='sku-generate'),
    path('sku/validate/', validate_sku, name='sku-validate'),
] 