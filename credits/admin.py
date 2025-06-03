from django.contrib import admin
from .models import CreditAccount, CreditPayment


class CreditPaymentInline(admin.TabularInline):
    """Inline para mostrar pagos dentro de la cuenta de crédito."""
    model = CreditPayment
    extra = 0
    readonly_fields = ['created_at']
    fields = ['amount_paid', 'payment_date', 'notes', 'created_at']


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    """Administración de cuentas de crédito."""
    
    list_display = [
        'id', 'customer_name', 'original_amount', 'remaining_amount', 
        'start_date', 'due_date', 'is_fully_paid', 'is_overdue'
    ]
    list_filter = [
        'start_date', 'due_date', 'created_at'
    ]
    search_fields = [
        'sale__customer__name', 'sale__customer__email', 
        'sale__customer__phone', 'sale__id'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'is_fully_paid', 
        'is_overdue', 'total_paid'
    ]
    fieldsets = (
        ('Información de la Venta', {
            'fields': ('sale',)
        }),
        ('Información del Crédito', {
            'fields': ('original_amount', 'remaining_amount', 'start_date', 'due_date')
        }),
        ('Estado del Crédito', {
            'fields': ('is_fully_paid', 'is_overdue', 'total_paid'),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [CreditPaymentInline]
    
    def customer_name(self, obj):
        """Obtiene el nombre del cliente de la venta asociada."""
        return obj.sale.customer.name if obj.sale.customer else "Anónimo"
    customer_name.short_description = "Cliente"
    customer_name.admin_order_field = 'sale__customer__name'

    def has_add_permission(self, request):
        """Permite agregar nuevas cuentas de crédito."""
        return True

    def has_change_permission(self, request, obj=None):
        """Permite modificar cuentas de crédito."""
        return True

    def has_delete_permission(self, request, obj=None):
        """Restringe la eliminación de cuentas con pagos."""
        if obj and obj.payments.exists():
            return False
        return True


@admin.register(CreditPayment)
class CreditPaymentAdmin(admin.ModelAdmin):
    """Administración de pagos de crédito."""
    
    list_display = [
        'id', 'credit_account', 'customer_name', 'amount_paid', 
        'payment_date', 'created_at'
    ]
    list_filter = [
        'payment_date', 'created_at'
    ]
    search_fields = [
        'credit_account__sale__customer__name',
        'credit_account__sale__customer__email',
        'credit_account__id', 'notes'
    ]
    readonly_fields = ['created_at']
    fieldsets = (
        ('Información del Pago', {
            'fields': ('credit_account', 'amount_paid', 'payment_date', 'notes')
        }),
        ('Metadatos', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def customer_name(self, obj):
        """Obtiene el nombre del cliente de la cuenta de crédito."""
        return obj.credit_account.sale.customer.name if obj.credit_account.sale.customer else "Anónimo"
    customer_name.short_description = "Cliente"
    customer_name.admin_order_field = 'credit_account__sale__customer__name'

    def has_delete_permission(self, request, obj=None):
        """Permite eliminar pagos pero con cuidado."""
        return True
