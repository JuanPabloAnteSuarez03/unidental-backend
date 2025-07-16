import django_filters
from django_filters import rest_framework as filters
from django.utils import timezone
from datetime import date, timedelta
from .models import Sale


class SaleFilter(filters.FilterSet):
    """
    Filtros para el modelo Sale.
    Permite filtrar por fechas, tipo de venta, cliente, ubicación, etc.
    """
    
    # Filtros de fecha
    sale_date_from = filters.DateFilter(
        field_name='sale_date',
        lookup_expr='gte',
        help_text='Fecha de venta desde (YYYY-MM-DD)'
    )
    sale_date_to = filters.DateFilter(
        field_name='sale_date',
        lookup_expr='lte',
        help_text='Fecha de venta hasta (YYYY-MM-DD)'
    )
    
    # Filtros de fecha predefinidos
    date_range = filters.ChoiceFilter(
        choices=[
            ('today', 'Hoy'),
            ('yesterday', 'Ayer'),
            ('this_week', 'Esta semana'),
            ('last_week', 'Semana pasada'),
            ('this_month', 'Este mes'),
            ('last_month', 'Mes pasado'),
            ('last_7_days', 'Últimos 7 días'),
            ('last_30_days', 'Últimos 30 días'),
            ('last_90_days', 'Últimos 90 días'),
        ],
        method='filter_date_range',
        help_text='Rangos de fecha predefinidos'
    )
    
    # Filtros de monto
    total_min = filters.NumberFilter(
        field_name='total_net',
        lookup_expr='gte',
        help_text='Total mínimo de la venta'
    )
    total_max = filters.NumberFilter(
        field_name='total_net',
        lookup_expr='lte',
        help_text='Total máximo de la venta'
    )
    
    # Filtros de texto
    customer_name = filters.CharFilter(
        field_name='customer__name',
        lookup_expr='icontains',
        help_text='Nombre del cliente (búsqueda parcial)'
    )
    location_name = filters.CharFilter(
        field_name='location__name',
        lookup_expr='icontains',
        help_text='Nombre de la ubicación (búsqueda parcial)'
    )
    
    class Meta:
        model = Sale
        fields = {
            'sale_type': ['exact'],
            'should_invoice': ['exact'],
            'customer': ['exact'],
            'location': ['exact'],
        }
    
    def filter_date_range(self, queryset, name, value):
        """
        Filtra por rangos de fecha predefinidos.
        """
        # Usar timezone.localdate() para obtener la fecha en la zona horaria local
        today = timezone.localdate()
        
        if value == 'today':
            return queryset.filter(sale_date__date=today)
        elif value == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(sale_date__date=yesterday)
        elif value == 'this_week':
            # Semana actual (lunes a domingo)
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(sale_date__date__range=[start_of_week, end_of_week])
        elif value == 'last_week':
            # Semana pasada
            start_of_week = today - timedelta(days=today.weekday() + 7)
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(sale_date__date__range=[start_of_week, end_of_week])
        elif value == 'this_month':
            # Mes actual
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            return queryset.filter(sale_date__date__range=[start_of_month, end_of_month])
        elif value == 'last_month':
            # Mes pasado
            if today.month == 1:
                start_of_month = today.replace(year=today.year - 1, month=12, day=1)
            else:
                start_of_month = today.replace(month=today.month - 1, day=1)
            end_of_month = today.replace(day=1) - timedelta(days=1)
            return queryset.filter(sale_date__date__range=[start_of_month, end_of_month])
        elif value == 'last_7_days':
            start_date = today - timedelta(days=7)
            return queryset.filter(sale_date__date__gte=start_date)
        elif value == 'last_30_days':
            start_date = today - timedelta(days=30)
            return queryset.filter(sale_date__date__gte=start_date)
        elif value == 'last_90_days':
            start_date = today - timedelta(days=90)
            return queryset.filter(sale_date__date__gte=start_date)
        
        return queryset 