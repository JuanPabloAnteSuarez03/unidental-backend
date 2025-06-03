import django_filters
from django.db import models
from .models import PurchaseOrder, PurchaseOrderItem


class PurchaseOrderFilter(django_filters.FilterSet):
    """
    Filtros para órdenes de compra.
    """
    
    # Filtros por fechas
    order_date_from = django_filters.DateFilter(
        field_name='order_date',
        lookup_expr='gte',
        help_text="Filtrar órdenes desde esta fecha (YYYY-MM-DD)"
    )
    order_date_to = django_filters.DateFilter(
        field_name='order_date',
        lookup_expr='lte',
        help_text="Filtrar órdenes hasta esta fecha (YYYY-MM-DD)"
    )
    
    # Filtros por fechas de creación
    created_from = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text="Filtrar órdenes creadas desde esta fecha y hora"
    )
    created_to = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text="Filtrar órdenes creadas hasta esta fecha y hora"
    )
    
    # Filtro por rango de montos
    total_amount_min = django_filters.NumberFilter(
        method='filter_total_amount_min',
        help_text="Monto mínimo total de la orden"
    )
    total_amount_max = django_filters.NumberFilter(
        method='filter_total_amount_max',
        help_text="Monto máximo total de la orden"
    )
    
    # Filtro por nombre de proveedor
    supplier_name = django_filters.CharFilter(
        field_name='supplier__name',
        lookup_expr='icontains',
        help_text="Buscar por nombre del proveedor"
    )
    
    # Filtro por nombre de ubicación destino
    destination_name = django_filters.CharFilter(
        field_name='destination__name',
        lookup_expr='icontains',
        help_text="Buscar por nombre de la ubicación destino"
    )
    
    # Filtro por tipo de ubicación destino
    destination_type = django_filters.ChoiceFilter(
        field_name='destination__type',
        choices=[('sede', 'Sede'), ('bodega', 'Bodega')],
        help_text="Filtrar por tipo de ubicación destino"
    )
    
    # Filtro por usuario creador
    created_by_username = django_filters.CharFilter(
        field_name='created_by__username',
        lookup_expr='icontains',
        help_text="Buscar por username del usuario que creó la orden"
    )

    class Meta:
        model = PurchaseOrder
        fields = {
            'supplier': ['exact'],
            'destination': ['exact'],
            'status': ['exact', 'in'],
            'created_by': ['exact'],
        }

    def filter_total_amount_min(self, queryset, name, value):
        """Filtrar por monto mínimo total."""
        if value is not None:
            # Anotar con el total calculado y filtrar
            from django.db.models import Sum, Case, When, F
            return queryset.annotate(
                calculated_total=Sum(
                    Case(
                        When(items__isnull=False, then=F('items__quantity_requested') * F('items__unit_price')),
                        default=0
                    )
                )
            ).filter(calculated_total__gte=value)
        return queryset

    def filter_total_amount_max(self, queryset, name, value):
        """Filtrar por monto máximo total."""
        if value is not None:
            from django.db.models import Sum, Case, When, F
            return queryset.annotate(
                calculated_total=Sum(
                    Case(
                        When(items__isnull=False, then=F('items__quantity_requested') * F('items__unit_price')),
                        default=0
                    )
                )
            ).filter(calculated_total__lte=value)
        return queryset


class PurchaseOrderItemFilter(django_filters.FilterSet):
    """
    Filtros para items de órdenes de compra.
    """
    
    # Filtros por orden
    order_status = django_filters.ChoiceFilter(
        field_name='order__status',
        choices=PurchaseOrder.STATUS_CHOICES,
        help_text="Filtrar por estado de la orden"
    )
    order_supplier = django_filters.NumberFilter(
        field_name='order__supplier',
        help_text="Filtrar por ID del proveedor de la orden"
    )
    
    # Filtros por producto
    product_name = django_filters.CharFilter(
        field_name='purchase_option__product__name',
        lookup_expr='icontains',
        help_text="Buscar por nombre del producto"
    )
    product_sku = django_filters.CharFilter(
        field_name='purchase_option__product__sku',
        lookup_expr='icontains',
        help_text="Buscar por SKU del producto"
    )
    product_category = django_filters.NumberFilter(
        field_name='purchase_option__product__category',
        help_text="Filtrar por ID de la categoría del producto"
    )
    
    # Filtros por marca
    brand = django_filters.CharFilter(
        field_name='purchase_option__brand',
        lookup_expr='icontains',
        help_text="Buscar por marca del producto"
    )
    
    # Filtros por cantidad
    quantity_min = django_filters.NumberFilter(
        field_name='quantity_requested',
        lookup_expr='gte',
        help_text="Cantidad mínima solicitada"
    )
    quantity_max = django_filters.NumberFilter(
        field_name='quantity_requested',
        lookup_expr='lte',
        help_text="Cantidad máxima solicitada"
    )
    
    # Filtros por precio
    unit_price_min = django_filters.NumberFilter(
        field_name='unit_price',
        lookup_expr='gte',
        help_text="Precio unitario mínimo"
    )
    unit_price_max = django_filters.NumberFilter(
        field_name='unit_price',
        lookup_expr='lte',
        help_text="Precio unitario máximo"
    )
    
    # Filtro por total de línea
    line_total_min = django_filters.NumberFilter(
        method='filter_line_total_min',
        help_text="Total mínimo de la línea (cantidad × precio)"
    )
    line_total_max = django_filters.NumberFilter(
        method='filter_line_total_max',
        help_text="Total máximo de la línea (cantidad × precio)"
    )

    class Meta:
        model = PurchaseOrderItem
        fields = {
            'order': ['exact'],
            'purchase_option': ['exact'],
        }

    def filter_line_total_min(self, queryset, name, value):
        """Filtrar por total mínimo de línea."""
        if value is not None:
            from django.db.models import F
            return queryset.annotate(
                calculated_line_total=F('quantity_requested') * F('unit_price')
            ).filter(calculated_line_total__gte=value)
        return queryset

    def filter_line_total_max(self, queryset, name, value):
        """Filtrar por total máximo de línea."""
        if value is not None:
            from django.db.models import F
            return queryset.annotate(
                calculated_line_total=F('quantity_requested') * F('unit_price')
            ).filter(calculated_line_total__lte=value)
        return queryset 