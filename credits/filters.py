import django_filters
from django_filters import rest_framework as filters
from django.utils import timezone
from datetime import date, timedelta
from .models import CreditAccount, CreditPayment


class CreditAccountFilter(filters.FilterSet):
    """
    Filtros para el modelo CreditAccount.
    Permite filtrar por fechas, estado de pago, cliente, etc.
    """
    
    # Filtros de fecha
    created_at_from = filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text='Fecha de creación desde (YYYY-MM-DD)'
    )
    created_at_to = filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text='Fecha de creación hasta (YYYY-MM-DD)'
    )
    due_date_from = filters.DateFilter(
        field_name='due_date',
        lookup_expr='gte',
        help_text='Fecha de vencimiento desde (YYYY-MM-DD)'
    )
    due_date_to = filters.DateFilter(
        field_name='due_date',
        lookup_expr='lte',
        help_text='Fecha de vencimiento hasta (YYYY-MM-DD)'
    )
    next_payment_date_from = filters.DateFilter(
        field_name='next_payment_date',
        lookup_expr='gte',
        help_text='Próxima fecha de pago desde (YYYY-MM-DD)'
    )
    next_payment_date_to = filters.DateFilter(
        field_name='next_payment_date',
        lookup_expr='lte',
        help_text='Próxima fecha de pago hasta (YYYY-MM-DD)'
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
        help_text='Rangos de fecha predefinidos (basado en fecha de creación)'
    )
    
    # Filtros de monto
    original_amount_min = filters.NumberFilter(
        field_name='original_amount',
        lookup_expr='gte',
        help_text='Monto original mínimo'
    )
    original_amount_max = filters.NumberFilter(
        field_name='original_amount',
        lookup_expr='lte',
        help_text='Monto original máximo'
    )
    remaining_amount_min = filters.NumberFilter(
        field_name='remaining_amount',
        lookup_expr='gte',
        help_text='Monto pendiente mínimo'
    )
    remaining_amount_max = filters.NumberFilter(
        field_name='remaining_amount',
        lookup_expr='lte',
        help_text='Monto pendiente máximo'
    )
    
    # Filtros de texto
    customer_name = filters.CharFilter(
        field_name='sale__customer__name',
        lookup_expr='icontains',
        help_text='Nombre del cliente (búsqueda parcial)'
    )
    customer_email = filters.CharFilter(
        field_name='sale__customer__email',
        lookup_expr='icontains',
        help_text='Email del cliente (búsqueda parcial)'
    )
    
    # Filtros de estado
    payment_frequency = filters.ChoiceFilter(
        choices=CreditAccount._meta.get_field('payment_frequency').choices,
        help_text='Frecuencia de pago'
    )
    
    class Meta:
        model = CreditAccount
        fields = {
            'sale__customer': ['exact'],
            'payment_frequency': ['exact'],
        }
    
    def filter_date_range(self, queryset, name, value):
        """
        Filtra por rangos de fecha predefinidos basado en fecha de creación.
        """
        # Usar timezone.localdate() para obtener la fecha en la zona horaria local
        today = timezone.localdate()
        
        if value == 'today':
            return queryset.filter(created_at__date=today)
        elif value == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif value == 'this_week':
            # Semana actual (lunes a domingo)
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(created_at__date__range=[start_of_week, end_of_week])
        elif value == 'last_week':
            # Semana pasada
            start_of_week = today - timedelta(days=today.weekday() + 7)
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(created_at__date__range=[start_of_week, end_of_week])
        elif value == 'this_month':
            # Mes actual
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            return queryset.filter(created_at__date__range=[start_of_month, end_of_month])
        elif value == 'last_month':
            # Mes pasado
            if today.month == 1:
                start_of_month = today.replace(year=today.year - 1, month=12, day=1)
            else:
                start_of_month = today.replace(month=today.month - 1, day=1)
            end_of_month = today.replace(day=1) - timedelta(days=1)
            return queryset.filter(created_at__date__range=[start_of_month, end_of_month])
        elif value == 'last_7_days':
            start_date = today - timedelta(days=7)
            return queryset.filter(created_at__date__gte=start_date)
        elif value == 'last_30_days':
            start_date = today - timedelta(days=30)
            return queryset.filter(created_at__date__gte=start_date)
        elif value == 'last_90_days':
            start_date = today - timedelta(days=90)
            return queryset.filter(created_at__date__gte=start_date)
        
        return queryset


class CreditPaymentFilter(filters.FilterSet):
    """
    Filtros para el modelo CreditPayment.
    Permite filtrar por fechas de pago, montos, etc.
    """
    
    # Filtros de fecha
    payment_date_from = filters.DateFilter(
        field_name='payment_date',
        lookup_expr='gte',
        help_text='Fecha de pago desde (YYYY-MM-DD)'
    )
    payment_date_to = filters.DateFilter(
        field_name='payment_date',
        lookup_expr='lte',
        help_text='Fecha de pago hasta (YYYY-MM-DD)'
    )
    created_at_from = filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text='Fecha de registro desde (YYYY-MM-DD)'
    )
    created_at_to = filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text='Fecha de registro hasta (YYYY-MM-DD)'
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
        help_text='Rangos de fecha predefinidos (basado en fecha de pago)'
    )
    
    # Filtros de monto
    amount_min = filters.NumberFilter(
        field_name='amount_paid',
        lookup_expr='gte',
        help_text='Monto pagado mínimo'
    )
    amount_max = filters.NumberFilter(
        field_name='amount_paid',
        lookup_expr='lte',
        help_text='Monto pagado máximo'
    )
    
    # Filtros de texto
    customer_name = filters.CharFilter(
        field_name='credit_account__sale__customer__name',
        lookup_expr='icontains',
        help_text='Nombre del cliente (búsqueda parcial)'
    )
    
    class Meta:
        model = CreditPayment
        fields = {
            'credit_account': ['exact'],
            'payment_date': ['exact'],
        }
    
    def filter_date_range(self, queryset, name, value):
        """
        Filtra por rangos de fecha predefinidos basado en fecha de pago.
        """
        # Usar timezone.localdate() para obtener la fecha en la zona horaria local
        today = timezone.localdate()
        
        if value == 'today':
            return queryset.filter(payment_date=today)
        elif value == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(payment_date=yesterday)
        elif value == 'this_week':
            # Semana actual (lunes a domingo)
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(payment_date__range=[start_of_week, end_of_week])
        elif value == 'last_week':
            # Semana pasada
            start_of_week = today - timedelta(days=today.weekday() + 7)
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(payment_date__range=[start_of_week, end_of_week])
        elif value == 'this_month':
            # Mes actual
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            return queryset.filter(payment_date__range=[start_of_month, end_of_month])
        elif value == 'last_month':
            # Mes pasado
            if today.month == 1:
                start_of_month = today.replace(year=today.year - 1, month=12, day=1)
            else:
                start_of_month = today.replace(month=today.month - 1, day=1)
            end_of_month = today.replace(day=1) - timedelta(days=1)
            return queryset.filter(payment_date__range=[start_of_month, end_of_month])
        elif value == 'last_7_days':
            start_date = today - timedelta(days=7)
            return queryset.filter(payment_date__gte=start_date)
        elif value == 'last_30_days':
            start_date = today - timedelta(days=30)
            return queryset.filter(payment_date__gte=start_date)
        elif value == 'last_90_days':
            start_date = today - timedelta(days=90)
            return queryset.filter(payment_date__gte=start_date)
        
        return queryset 