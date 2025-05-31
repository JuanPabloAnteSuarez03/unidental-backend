import django_filters
from .models import Supplier, PurchaseOption
from django.utils import timezone
from django.db import models


class SupplierFilter(django_filters.FilterSet):
    """
    Filtros para el modelo Supplier.
    Permite filtrar proveedores por nombre, email, teléfono.
    """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    contact_name = django_filters.CharFilter(field_name='contact_name', lookup_expr='icontains')
    email = django_filters.CharFilter(field_name='email', lookup_expr='icontains')
    phone = django_filters.CharFilter(field_name='phone', lookup_expr='icontains')
    
    class Meta:
        model = Supplier
        fields = ['name', 'contact_name', 'email', 'phone']


class PurchaseOptionFilter(django_filters.FilterSet):
    """
    Filtros para el modelo PurchaseOption.
    Permite filtrar por producto, proveedor, marca, precio, fechas de validez.
    """
    product = django_filters.NumberFilter(field_name='product__id')
    product_name = django_filters.CharFilter(field_name='product__name', lookup_expr='icontains')
    supplier = django_filters.NumberFilter(field_name='supplier__id')
    supplier_name = django_filters.CharFilter(field_name='supplier__name', lookup_expr='icontains')
    brand = django_filters.CharFilter(field_name='brand', lookup_expr='icontains')
    category = django_filters.NumberFilter(field_name='product__category__id')
    category_name = django_filters.CharFilter(field_name='product__category__name', lookup_expr='icontains')
    
    # Filtros de precio
    min_price = django_filters.NumberFilter(field_name='purchase_price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='purchase_price', lookup_expr='lte')
    
    # Filtros de fecha
    valid_from_start = django_filters.DateFilter(field_name='valid_from', lookup_expr='gte')
    valid_from_end = django_filters.DateFilter(field_name='valid_from', lookup_expr='lte')
    valid_to_start = django_filters.DateFilter(field_name='valid_to', lookup_expr='gte')
    valid_to_end = django_filters.DateFilter(field_name='valid_to', lookup_expr='lte')
    
    # Filtro para opciones actualmente válidas
    is_currently_valid = django_filters.BooleanFilter(method='filter_currently_valid')
    
    class Meta:
        model = PurchaseOption
        fields = [
            'product', 'product_name', 'supplier', 'supplier_name', 
            'brand', 'category', 'category_name',
            'min_price', 'max_price',
            'valid_from_start', 'valid_from_end',
            'valid_to_start', 'valid_to_end',
            'is_currently_valid'
        ]
    
    def filter_currently_valid(self, queryset, name, value):
        """
        Filtra opciones de compra que están actualmente válidas.
        """
        today = timezone.localdate()
        
        if value:
            # Opciones válidas: valid_from <= today AND (valid_to IS NULL OR valid_to >= today)
            return queryset.filter(
                valid_from__lte=today
            ).filter(
                models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=today)
            )
        else:
            # Opciones no válidas: valid_from > today OR valid_to < today
            return queryset.filter(
                models.Q(valid_from__gt=today) | 
                models.Q(valid_to__lt=today, valid_to__isnull=False)
            ) 