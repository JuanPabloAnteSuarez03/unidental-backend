from django.contrib import admin
from .models import (CreditAccount, CreditPayment, 
                     CreditPurchaseAccount, CreditPurchasePayment, CreditPurchaseReminder)


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


# ======================================================
# ADMINISTRACIÓN PARA COMPRAS A CRÉDITO
# ======================================================


class CreditPurchasePaymentInline(admin.TabularInline):
    """Inline para mostrar abonos en la cuenta de crédito de compra."""
    model = CreditPurchasePayment
    extra = 0
    readonly_fields = ['created_at']
    fields = ['amount_paid', 'payment_date', 'payment_method', 'reference_number', 'notes', 'created_at']


@admin.register(CreditPurchaseAccount)
class CreditPurchaseAccountAdmin(admin.ModelAdmin):
    """Administración de cuentas de crédito de compra."""
    list_display = [
        'id', 'supplier_name', 'original_amount', 'remaining_amount',
        'start_date', 'payment_frequency', 'next_payment_date', 'is_fully_paid', 'is_overdue'
    ]
    list_filter = ['payment_frequency', 'start_date', 'next_payment_date', 'created_at']
    search_fields = ['purchase_order__supplier__name', 'purchase_order__id']
    readonly_fields = ['created_at', 'updated_at', 'is_fully_paid', 'is_overdue', 'total_paid']
    fieldsets = (
        ('Información de la Orden de Compra', {
            'fields': ('purchase_order',)
        }),
        ('Información del Crédito', {
            'fields': (
                'original_amount', 'remaining_amount', 'payment_frequency', 'payment_amount',
                'start_date', 'next_payment_date', 'grace_days', 'is_active', 'notes'
            )
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
    inlines = [CreditPurchasePaymentInline]

    def supplier_name(self, obj):
        return obj.supplier.name
    supplier_name.short_description = "Proveedor"
    supplier_name.admin_order_field = 'purchase_order__supplier__name'


@admin.register(CreditPurchasePayment)
class CreditPurchasePaymentAdmin(admin.ModelAdmin):
    """Administración de abonos de crédito de compra."""
    list_display = [
        'id', 'credit_account', 'supplier_name', 'amount_paid', 'payment_date', 'payment_method', 'created_at'
    ]
    list_filter = ['payment_date', 'payment_method', 'created_at']
    search_fields = ['credit_account__purchase_order__supplier__name', 'credit_account__id', 'reference_number', 'notes']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Información del Pago', {
            'fields': (
                'credit_account', 'amount_paid', 'payment_date', 'payment_method', 'reference_number', 'notes'
            )
        }),
        ('Metadatos', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def supplier_name(self, obj):
        return obj.credit_account.supplier.name
    supplier_name.short_description = "Proveedor"
    supplier_name.admin_order_field = 'credit_account__purchase_order__supplier__name'


@admin.register(CreditPurchaseReminder)
class CreditPurchaseReminderAdmin(admin.ModelAdmin):
    """Administración de recordatorios de crédito de compra."""
    list_display = [
        'id', 'credit_account', 'reminder_type', 'status', 'scheduled_date', 'sent_date', 'retry_count'
    ]
    list_filter = ['reminder_type', 'status', 'scheduled_date', 'created_at']
    search_fields = ['credit_account__purchase_order__supplier__name', 'message_content', 'error_message']
    readonly_fields = ['sent_date', 'whatsapp_message_id', 'error_message', 'retry_count', 'created_at']
