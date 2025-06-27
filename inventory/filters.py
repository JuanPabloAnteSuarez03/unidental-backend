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
    - Lotes específicos
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
    product_sku_exact = django_filters.CharFilter(field_name='product__sku', lookup_expr='iexact')
    product_category = django_filters.NumberFilter(field_name='product__category__id')
    product_category_name = django_filters.CharFilter(field_name='product__category__name', lookup_expr='icontains')
    
    # Filtros por cantidad
    min_quantity = django_filters.NumberFilter(field_name='quantity', lookup_expr='gte')
    max_quantity = django_filters.NumberFilter(field_name='quantity', lookup_expr='lte')
    
    # Filtro para stock disponible (cantidad > 0)
    has_stock = django_filters.BooleanFilter(method='filter_has_stock')
    
    # NUEVOS FILTROS PARA LOTES
    batch = django_filters.NumberFilter(field_name='batch__id', help_text='ID del lote específico')
    batch_number = django_filters.CharFilter(field_name='batch__batch_number', lookup_expr='iexact', help_text='Número de lote exacto')
    batch_number_contains = django_filters.CharFilter(field_name='batch__batch_number', lookup_expr='icontains', help_text='Buscar por número de lote')
    
    # Filtros para productos con control de lotes
    requires_batch_control = django_filters.BooleanFilter(field_name='product__requires_batch_control', help_text='Solo productos que requieren control de lotes')
    has_batch = django_filters.BooleanFilter(method='filter_has_batch', help_text='Filtrar por existencia de lote')
    
    # Filtros por fechas de vencimiento
    expiry_date = django_filters.DateFilter(field_name='batch__expiry_date', help_text='Fecha de vencimiento exacta')
    expiry_from = django_filters.DateFilter(field_name='batch__expiry_date', lookup_expr='gte', help_text='Vence después de esta fecha')
    expiry_to = django_filters.DateFilter(field_name='batch__expiry_date', lookup_expr='lte', help_text='Vence antes de esta fecha')
    expiry_days_ahead = django_filters.NumberFilter(method='filter_expiry_days_ahead', help_text='Vence en los próximos N días')
    
    # Filtro para lotes vencidos
    is_expired = django_filters.BooleanFilter(method='filter_is_expired', help_text='Solo lotes vencidos')
    
    class Meta:
        model = InventoryStock
        fields = [
            'location', 'location_type', 'location_name',
            'product', 'product_name', 'product_sku', 'product_sku_exact', 'product_category', 'product_category_name',
            'min_quantity', 'max_quantity', 'has_stock',
            'batch', 'batch_number', 'batch_number_contains', 'requires_batch_control', 'has_batch',
            'expiry_date', 'expiry_from', 'expiry_to', 'expiry_days_ahead', 'is_expired'
        ]
    
    def filter_has_stock(self, queryset, name, value):
        """
        Filtra por stock disponible o agotado.
        """
        if value:
            return queryset.filter(quantity__gt=0)
        else:
            return queryset.filter(quantity=0)
    
    def filter_has_batch(self, queryset, name, value):
        """
        Filtra por existencia de lote.
        """
        if value:
            return queryset.filter(batch__isnull=False)
        else:
            return queryset.filter(batch__isnull=True)
    
    def filter_expiry_days_ahead(self, queryset, name, value):
        """
        Filtra productos que vencen en los próximos N días.
        """
        from django.utils import timezone
        from datetime import timedelta

        if value and value > 0:
            target_date = timezone.now().date() + timedelta(days=int(value))
            return queryset.filter(
                batch__expiry_date__lte=target_date,
                batch__expiry_date__gte=timezone.now().date()
            )
        return queryset
    
    def filter_is_expired(self, queryset, name, value):
        """
        Filtra lotes vencidos.
        """
        from django.utils import timezone
        
        if value:
            return queryset.filter(batch__expiry_date__lt=timezone.now().date())
        else:
            return queryset.filter(batch__expiry_date__gte=timezone.now().date())


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
    expiry_from = django_filters.DateFilter(field_name='batch__expiry_date', lookup_expr='gte')
    expiry_to = django_filters.DateFilter(field_name='batch__expiry_date', lookup_expr='lte')
    has_expiry = django_filters.BooleanFilter(field_name='batch__expiry_date', lookup_expr='isnull', exclude=True)
    
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
    product_sku_exact = django_filters.CharFilter(field_name='product__sku', lookup_expr='iexact')
    product_category = django_filters.NumberFilter(field_name='product__category__id')
    
    # NUEVOS FILTROS PARA LOTES EN MOVIMIENTOS
    batch = django_filters.NumberFilter(field_name='batch__id', help_text='ID del lote específico')
    batch_number = django_filters.CharFilter(field_name='batch__batch_number', lookup_expr='iexact', help_text='Número de lote exacto')
    batch_number_contains = django_filters.CharFilter(field_name='batch__batch_number', lookup_expr='icontains', help_text='Buscar por número de lote')
    
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
            'product', 'product_name', 'product_sku', 'product_sku_exact', 'product_category',
            'batch', 'batch_number', 'batch_number_contains',
            'min_quantity', 'max_quantity',
            'user_username'
        ] 