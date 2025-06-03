from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Delivery


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    """Administración de entregas."""
    
    list_display = [
        'id', 'sale_link', 'customer_name', 'origin_location', 'dest_location',
        'status_badge', 'shipped_at', 'delivered_at', 'delivery_time_display', 'created_at'
    ]
    list_filter = [
        'status', 'origin_location', 'dest_location', 'created_at', 
        'shipped_at', 'delivered_at'
    ]
    search_fields = [
        'id', 'sale__id', 'sale__customer__name', 'sale__customer__email',
        'origin_location__name', 'dest_location__name'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'delivery_time_display', 'customer_name', 'sale_total'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Información de la Entrega', {
            'fields': ('sale', 'status')
        }),
        ('Ubicaciones', {
            'fields': ('origin_location', 'dest_location')
        }),
        ('Fechas de Seguimiento', {
            'fields': ('shipped_at', 'delivered_at')
        }),
        ('Información de Solo Lectura', {
            'fields': ('customer_name', 'sale_total', 'delivery_time_display', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_shipped', 'mark_as_delivered', 'mark_as_pending']
    
    def sale_link(self, obj):
        """Enlace a la venta asociada."""
        url = reverse('admin:sales_sale_change', args=[obj.sale.id])
        return format_html('<a href="{}">Venta #{}</a>', url, obj.sale.id)
    sale_link.short_description = "Venta"
    sale_link.admin_order_field = 'sale__id'
    
    def status_badge(self, obj):
        """Mostrar el estado como badge con colores."""
        colors = {
            'pending': '#ffc107',     # amarillo
            'in_transit': '#17a2b8',  # azul
            'delivered': '#28a745'    # verde
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Estado"
    status_badge.admin_order_field = 'status'
    
    def delivery_time_display(self, obj):
        """Mostrar tiempo de entrega."""
        if obj.delivery_time is not None:
            if obj.delivery_time == 0:
                return "Mismo día"
            elif obj.delivery_time == 1:
                return "1 día"
            else:
                return f"{obj.delivery_time} días"
        return "N/A"
    delivery_time_display.short_description = "Tiempo de Entrega"
    
    def customer_name(self, obj):
        """Nombre del cliente."""
        return obj.customer_name
    customer_name.short_description = "Cliente"
    customer_name.admin_order_field = 'sale__customer__name'
    
    def sale_total(self, obj):
        """Total de la venta."""
        return f"${obj.sale_total:,.2f}"
    sale_total.short_description = "Total Venta"
    sale_total.admin_order_field = 'sale__total_amount'
    
    # Acciones personalizadas
    def mark_as_shipped(self, request, queryset):
        """Marcar entregas como enviadas."""
        updated = 0
        for delivery in queryset:
            try:
                if delivery.status == 'pending':
                    delivery.mark_as_shipped()
                    updated += 1
            except Exception:
                pass
        
        self.message_user(
            request, f"{updated} entrega(s) marcada(s) como enviada(s)."
        )
    mark_as_shipped.short_description = "Marcar como enviado"
    
    def mark_as_delivered(self, request, queryset):
        """Marcar entregas como entregadas."""
        updated = 0
        for delivery in queryset:
            try:
                if delivery.status in ['pending', 'in_transit']:
                    delivery.mark_as_delivered()
                    updated += 1
            except Exception:
                pass
        
        self.message_user(
            request, f"{updated} entrega(s) marcada(s) como entregada(s)."
        )
    mark_as_delivered.short_description = "Marcar como entregado"
    
    def mark_as_pending(self, request, queryset):
        """Marcar entregas como pendientes (solo si no han sido entregadas)."""
        updated = queryset.filter(status__in=['in_transit']).update(
            status='pending', 
            shipped_at=None
        )
        
        self.message_user(
            request, f"{updated} entrega(s) marcada(s) como pendiente(s)."
        )
    mark_as_pending.short_description = "Marcar como pendiente"
    
    def get_queryset(self, request):
        """Optimizar consultas."""
        return super().get_queryset(request).select_related(
            'sale', 'sale__customer', 'origin_location', 'dest_location'
        )
    
    def has_delete_permission(self, request, obj=None):
        """Permitir eliminar solo entregas pendientes."""
        if obj is None:
            return True
        return obj.status == 'pending'
