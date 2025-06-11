import django_filters
from .models import Location, InventoryStock, InventoryMovement


class LocationFilter(django_filters.FilterSet):
    """
    Filtros para el modelo Location.
    Permite filtrar ubicaciones por nombre, tipo y dirección.
    """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    address = django_filters.CharFilter(field_name='address', lookup_expr='icontains')
    
    class Meta:
        model = Location
        fields = ['type', 'name', 'address']


class InventoryStockFilter(django_filters.FilterSet):
    """
    Filtros para el modelo InventoryStock.
    Permite filtrar stock por:
    - Ubicación (ID y tipo)
    - Producto (nombre y SKU)
    - Cantidad mínima
    """
    # Filtros por ubicación
    location = django_filters.NumberFilter(field_name='location__id')
    location_type = django_filters.ChoiceFilter(
        field_name='location__type',
        choices=Location.TYPE_CHOICES
    )
    location_name = django_filters.CharFilter(field_name='location__name', lookup_expr='icontains')
    
    # Filtros por producto
    product = django_filters.NumberFilter(field_name='product__id')
    product_name = django_filters.CharFilter(field_name='product__name', lookup_expr='icontains')
    product_sku = django_filters.CharFilter(field_name='product__sku', lookup_expr='icontains')
    product_category = django_filters.NumberFilter(field_name='product__category__id')
    product_category_name = django_filters.CharFilter(field_name='product__category__name', lookup_expr='icontains')
    
    # Filtros por cantidad
    min_quantity = django_filters.NumberFilter(field_name='quantity', lookup_expr='gte')
    max_quantity = django_filters.NumberFilter(field_name='quantity', lookup_expr='lte')
    
    # Filtro para stock disponible (cantidad > 0)
    has_stock = django_filters.BooleanFilter(method='filter_has_stock')
    
    class Meta:
        model = InventoryStock
        fields = [
            'location', 'location_type', 'location_name',
            'product', 'product_name', 'product_sku', 'product_category', 'product_category_name',
            'min_quantity', 'max_quantity', 'has_stock'
        ]
    
    def filter_has_stock(self, queryset, name, value):
        """
        Filtra por stock disponible o agotado.
        """
        if value:
            return queryset.filter(quantity__gt=0)
        else:
            return queryset.filter(quantity=0)


class InventoryMovementFilter(django_filters.FilterSet):
    """
    Filtros para el modelo InventoryMovement.
    Permite filtrar movimientos por fecha, tipo, ubicación y producto.
    """
    # Filtros por fecha
    occurred_from = django_filters.DateTimeFilter(field_name='occurred_at', lookup_expr='gte')
    occurred_to = django_filters.DateTimeFilter(field_name='occurred_at', lookup_expr='lte')
    occurred_date = django_filters.DateFilter(field_name='occurred_at__date')
    
    # Filtros por vencimiento
    expiry_from = django_filters.DateFilter(field_name='expiry_date', lookup_expr='gte')
    expiry_to = django_filters.DateFilter(field_name='expiry_date', lookup_expr='lte')
    has_expiry = django_filters.BooleanFilter(field_name='expiry_date', lookup_expr='isnull', exclude=True)
    
    # Filtros por ubicación
    location_type = django_filters.ChoiceFilter(
        field_name='location__type',
        choices=Location.TYPE_CHOICES
    )
    location_name = django_filters.CharFilter(field_name='location__name', lookup_expr='icontains')
    
    # Filtros por producto
    product = django_filters.NumberFilter(field_name='product__id')
    product_name = django_filters.CharFilter(field_name='product__name', lookup_expr='icontains')
    product_sku = django_filters.CharFilter(field_name='product__sku', lookup_expr='icontains')
    product_category = django_filters.NumberFilter(field_name='product__category__id')
    
    # Filtros por cantidad
    min_quantity = django_filters.NumberFilter(field_name='quantity', lookup_expr='gte')
    max_quantity = django_filters.NumberFilter(field_name='quantity', lookup_expr='lte')
    
    # Filtros por usuario
    user_username = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    
    class Meta:
        model = InventoryMovement
        fields = [
            'movement_type', 'location', 'product',
            'occurred_from', 'occurred_to', 'occurred_date',
            'expiry_from', 'expiry_to', 'has_expiry',
            'location_type', 'location_name',
            'product', 'product_name', 'product_sku', 'product_category',
            'min_quantity', 'max_quantity',
            'user_username'
        ] 