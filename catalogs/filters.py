import django_filters
from .models import Category, Product

class CategoryFilter(django_filters.FilterSet):
    """
    Filtros para el modelo Category.
    Permite filtrar categorías por nombre (búsqueda parcial insensible a mayúsculas).
    """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    # Podrías añadir más filtros, por ejemplo, por descripción, etc.

    class Meta:
        model = Category
        fields = ['name'] # Campos por los que se puede filtrar directamente

class ProductFilter(django_filters.FilterSet):
    """
    Filtros para el modelo Product.
    Permite filtrar productos por:
    - Nombre (búsqueda parcial insensible a mayúsculas)
    - SKU (búsqueda exacta)
    - Código de Barras (búsqueda exacta)
    - ID de Categoría
    - Nombre de Categoría (búsqueda parcial insensible a mayúsculas en el nombre de la categoría relacionada)
    """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    sku = django_filters.CharFilter(field_name='sku', lookup_expr='exact')
    barcode = django_filters.CharFilter(field_name='barcode', lookup_expr='exact')
    category = django_filters.NumberFilter(field_name='category__id') # Filtra por el ID de la categoría
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='icontains')
    # Podrías añadir filtros por 'unit', etc.

    class Meta:
        model = Product
        fields = ['name', 'sku', 'barcode', 'category', 'category_name'] 