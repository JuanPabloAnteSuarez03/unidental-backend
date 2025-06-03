import django_filters
from django_filters import rest_framework as filters
from django.db.models import Q
from .models import Delivery
from sales.models import Sale
from inventory.models import Location


class DeliveryFilter(filters.FilterSet):
    """Filtros para entregas."""
    
    # Filtros por rango de fechas
    shipped_after = filters.DateTimeFilter(field_name='shipped_at', lookup_expr='gte')
    shipped_before = filters.DateTimeFilter(field_name='shipped_at', lookup_expr='lte')
    delivered_after = filters.DateTimeFilter(field_name='delivered_at', lookup_expr='gte')
    delivered_before = filters.DateTimeFilter(field_name='delivered_at', lookup_expr='lte')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # Filtros por ubicación
    origin_location = filters.ModelChoiceFilter(
        queryset=Location.objects.all(),
        field_name='origin_location'
    )
    dest_location = filters.ModelChoiceFilter(
        queryset=Location.objects.all(),
        field_name='dest_location'
    )
    
    # Filtros por múltiples ubicaciones
    origin_locations = filters.ModelMultipleChoiceFilter(
        queryset=Location.objects.all(),
        field_name='origin_location',
        to_field_name='id'
    )
    dest_locations = filters.ModelMultipleChoiceFilter(
        queryset=Location.objects.all(),
        field_name='dest_location',
        to_field_name='id'
    )
    
    # Filtros por estado
    status = filters.ChoiceFilter(choices=Delivery.STATUS_CHOICES)
    status_in = filters.MultipleChoiceFilter(
        field_name='status',
        choices=Delivery.STATUS_CHOICES
    )
    
    # Filtros por cliente
    customer_name = filters.CharFilter(
        field_name='sale__customer__name',
        lookup_expr='icontains'
    )
    customer_email = filters.CharFilter(
        field_name='sale__customer__email',
        lookup_expr='icontains'
    )
    customer_phone = filters.CharFilter(
        field_name='sale__customer__phone',
        lookup_expr='icontains'
    )
    
    # Filtros por venta
    sale_id = filters.NumberFilter(field_name='sale__id')
    sale_total_min = filters.NumberFilter(field_name='sale__total_gross', lookup_expr='gte')
    sale_total_max = filters.NumberFilter(field_name='sale__total_gross', lookup_expr='lte')
    
    # Filtros de tiempo de entrega
    delivery_time_min = filters.NumberFilter(method='filter_delivery_time_min')
    delivery_time_max = filters.NumberFilter(method='filter_delivery_time_max')
    
    # Filtros booleanos
    has_shipped = filters.BooleanFilter(method='filter_has_shipped')
    has_delivered = filters.BooleanFilter(method='filter_has_delivered')
    is_pending = filters.BooleanFilter(method='filter_is_pending')
    is_in_transit = filters.BooleanFilter(method='filter_is_in_transit')
    is_delivered = filters.BooleanFilter(method='filter_is_delivered')
    is_overdue = filters.BooleanFilter(method='filter_is_overdue')
    
    # Búsqueda general
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Delivery
        fields = [
            'status', 'origin_location', 'dest_location'
        ]
    
    def filter_delivery_time_min(self, queryset, name, value):
        """Filtrar por tiempo mínimo de entrega."""
        return queryset.extra(
            where=["""
                CASE 
                    WHEN shipped_at IS NOT NULL AND delivered_at IS NOT NULL 
                    THEN EXTRACT(EPOCH FROM (delivered_at - shipped_at))/86400 >= %s
                    ELSE FALSE 
                END
            """],
            params=[value]
        )
    
    def filter_delivery_time_max(self, queryset, name, value):
        """Filtrar por tiempo máximo de entrega."""
        return queryset.extra(
            where=["""
                CASE 
                    WHEN shipped_at IS NOT NULL AND delivered_at IS NOT NULL 
                    THEN EXTRACT(EPOCH FROM (delivered_at - shipped_at))/86400 <= %s
                    ELSE FALSE 
                END
            """],
            params=[value]
        )
    
    def filter_has_shipped(self, queryset, name, value):
        """Filtrar entregas que tienen fecha de envío."""
        if value:
            return queryset.filter(shipped_at__isnull=False)
        return queryset.filter(shipped_at__isnull=True)
    
    def filter_has_delivered(self, queryset, name, value):
        """Filtrar entregas que tienen fecha de entrega."""
        if value:
            return queryset.filter(delivered_at__isnull=False)
        return queryset.filter(delivered_at__isnull=True)
    
    def filter_is_pending(self, queryset, name, value):
        """Filtrar entregas pendientes."""
        if value:
            return queryset.filter(status='pending')
        return queryset.exclude(status='pending')
    
    def filter_is_in_transit(self, queryset, name, value):
        """Filtrar entregas en tránsito."""
        if value:
            return queryset.filter(status='in_transit')
        return queryset.exclude(status='in_transit')
    
    def filter_is_delivered(self, queryset, name, value):
        """Filtrar entregas entregadas."""
        if value:
            return queryset.filter(status='delivered')
        return queryset.exclude(status='delivered')
    
    def filter_is_overdue(self, queryset, name, value):
        """Filtrar entregas atrasadas (más de X días sin entregar)."""
        from django.utils import timezone
        from datetime import timedelta
        
        overdue_date = timezone.now() - timedelta(days=7)  # 7 días como ejemplo
        
        if value:
            return queryset.filter(
                Q(status__in=['pending', 'in_transit']) &
                Q(created_at__lt=overdue_date)
            )
        return queryset.exclude(
            Q(status__in=['pending', 'in_transit']) &
            Q(created_at__lt=overdue_date)
        )
    
    def filter_search(self, queryset, name, value):
        """Búsqueda general en múltiples campos."""
        if not value:
            return queryset
        
        return queryset.filter(
            Q(id__icontains=value) |
            Q(sale__id__icontains=value) |
            Q(sale__customer__name__icontains=value) |
            Q(sale__customer__email__icontains=value) |
            Q(sale__customer__phone__icontains=value) |
            Q(origin_location__name__icontains=value) |
            Q(dest_location__name__icontains=value) |
            Q(status__icontains=value)
        ) 