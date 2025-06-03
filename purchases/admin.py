from django.contrib import admin
from .models import PurchaseOrder, PurchaseOrderItem


class PurchaseOrderItemInline(admin.TabularInline):
    """Inline para mostrar items dentro de la orden de compra."""
    model = PurchaseOrderItem
    extra = 0
    readonly_fields = ['line_total', 'created_at']
    fields = [
        'purchase_option',
        'quantity_requested',
        'unit_price',
        'line_total',
        'created_at'
    ]

    def line_total(self, obj):
        """Muestra el total de la línea."""
        if obj.pk:
            return f"${obj.line_total:,.2f}"
        return "-"
    line_total.short_description = "Total línea"


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    """Administración de órdenes de compra."""
    
    list_display = [
        'id',
        'supplier',
        'destination',
        'order_date',
        'status',
        'total_amount_display',
        'total_items_display',
        'created_by',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'order_date',
        'supplier',
        'destination__type',
        'created_at'
    ]
    
    search_fields = [
        'supplier__name',
        'destination__name',
        'notes',
        'created_by__username'
    ]
    
    readonly_fields = [
        'total_amount_display',
        'total_items_display',
        'can_be_modified',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Información General', {
            'fields': (
                'supplier',
                'destination',
                'order_date',
                'status'
            )
        }),
        ('Detalles', {
            'fields': (
                'notes',
                'created_by'
            )
        }),
        ('Resumen', {
            'fields': (
                'total_amount_display',
                'total_items_display',
                'can_be_modified'
            ),
            'classes': ['collapse']
        }),
        ('Metadatos', {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ['collapse']
        })
    )
    
    inlines = [PurchaseOrderItemInline]
    
    ordering = ['-order_date', '-created_at']
    
    actions = ['mark_as_received', 'cancel_orders']

    def total_amount_display(self, obj):
        """Muestra el monto total formateado."""
        if obj.pk:
            return f"${obj.total_amount:,.2f}"
        return "-"
    total_amount_display.short_description = "Monto total"

    def total_items_display(self, obj):
        """Muestra el total de items."""
        if obj.pk:
            return obj.total_items
        return 0
    total_items_display.short_description = "Total items"

    def can_be_modified(self, obj):
        """Indica si la orden puede ser modificada."""
        if obj.pk:
            return "Sí" if obj.can_be_modified() else "No"
        return "N/A"
    can_be_modified.short_description = "¿Modificable?"

    def mark_as_received(self, request, queryset):
        """Acción para marcar órdenes como recibidas."""
        updated = 0
        for order in queryset.filter(status='pending'):
            if order.mark_as_received():
                updated += 1
        
        self.message_user(
            request,
            f'{updated} orden(es) marcada(s) como recibida(s).'
        )
    mark_as_received.short_description = "Marcar como recibidas"

    def cancel_orders(self, request, queryset):
        """Acción para cancelar órdenes."""
        updated = 0
        for order in queryset.filter(status='pending'):
            if order.cancel_order():
                updated += 1
        
        self.message_user(
            request,
            f'{updated} orden(es) cancelada(s).'
        )
    cancel_orders.short_description = "Cancelar órdenes"


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    """Administración de items de órdenes de compra."""
    
    list_display = [
        'id',
        'order',
        'product_name',
        'brand',
        'quantity_requested',
        'unit_price',
        'line_total_display',
        'order_status',
        'created_at'
    ]
    
    list_filter = [
        'order__status',
        'purchase_option__brand',
        'purchase_option__product__category',
        'order__supplier',
        'created_at'
    ]
    
    search_fields = [
        'purchase_option__product__name',
        'purchase_option__product__sku',
        'purchase_option__brand',
        'order__supplier__name'
    ]
    
    readonly_fields = [
        'line_total_display',
        'product_name',
        'product_sku',
        'brand',
        'order_status',
        'created_at'
    ]
    
    fieldsets = (
        ('Orden', {
            'fields': (
                'order',
                'order_status'
            )
        }),
        ('Producto', {
            'fields': (
                'purchase_option',
                'product_name',
                'product_sku',
                'brand'
            )
        }),
        ('Detalles', {
            'fields': (
                'quantity_requested',
                'unit_price',
                'line_total_display'
            )
        }),
        ('Metadatos', {
            'fields': (
                'created_at',
            ),
            'classes': ['collapse']
        })
    )
    
    ordering = ['-created_at']

    def product_name(self, obj):
        """Nombre del producto."""
        return obj.purchase_option.product.name
    product_name.short_description = "Producto"

    def product_sku(self, obj):
        """SKU del producto."""
        return obj.purchase_option.product.sku
    product_sku.short_description = "SKU"

    def brand(self, obj):
        """Marca del producto."""
        return obj.purchase_option.brand
    brand.short_description = "Marca"

    def order_status(self, obj):
        """Estado de la orden."""
        return obj.order.get_status_display()
    order_status.short_description = "Estado orden"

    def line_total_display(self, obj):
        """Muestra el total de la línea formateado."""
        return f"${obj.line_total:,.2f}"
    line_total_display.short_description = "Total línea"
