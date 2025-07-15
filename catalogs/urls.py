from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, 
    ProductViewSet, 
    ProductComponentViewSet,
    ProductBatchViewSet,
    ProductConversionViewSet,
    execute_conversion,
    suggest_conversions,
    get_sku_structure,
    generate_sku,
    validate_sku,
    SkuCategoryViewSet,
    SkuSubCategoryViewSet,
    SkuTypeViewSet
)

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-components', ProductComponentViewSet)
router.register(r'product-batches', ProductBatchViewSet)
router.register(r'product-conversions', ProductConversionViewSet)

# SKU Structure Viewsets
router.register(r'sku-categories', SkuCategoryViewSet, basename='skucategory')
router.register(r'sku-subcategories', SkuSubCategoryViewSet, basename='skusubcategory')
router.register(r'sku-types', SkuTypeViewSet, basename='skutype')


# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
    # Endpoints informativos para el sistema SKU
    path('sku/info/', get_sku_structure, name='sku-info'),
    path('sku/generate/', generate_sku, name='sku-generate'),
    path('sku/validate/', validate_sku, name='sku-validate'),
    # Endpoints para conversiones de productos
    path('conversions/execute/', execute_conversion, name='execute-conversion'),
    path('conversions/suggest/', suggest_conversions, name='suggest-conversions'),
] 