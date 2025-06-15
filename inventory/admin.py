from django.contrib import admin
from .models import Location, InventoryStock, InventoryMovement
from catalogs.models import ProductBatch


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'address', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['name', 'address']
    ordering = ['type', 'name']


@admin.register(InventoryStock)
class InventoryStockAdmin(admin.ModelAdmin):
    list_display = ['product', 'location', 'batch', 'quantity', 'last_updated']
    list_filter = ['location', 'location__type', 'last_updated', 'product__requires_batch_control']
    search_fields = ['product__name', 'product__sku', 'location__name', 'batch__batch_number']
    ordering = ['product__name', 'batch__expiry_date']
    readonly_fields = ['last_updated']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'location', 'batch')

    def batch(self, obj):
        """Mostrar información del lote."""
        if obj.batch:
            return f"{obj.batch.batch_number} (Vence: {obj.batch.expiry_date})"
        return "Sin lote"
    batch.short_description = "Lote"


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'location', 'batch_info', 'movement_type', 'quantity', 'occurred_at', 'user']
    list_filter = ['movement_type', 'location', 'location__type', 'occurred_at', 'product__requires_batch_control']
    search_fields = ['product__name', 'product__sku', 'location__name', 'notes', 'batch__batch_number']
    ordering = ['-occurred_at']
    readonly_fields = ['occurred_at']
    date_hierarchy = 'occurred_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'location', 'user', 'batch')
    
    def batch_info(self, obj):
        """Mostrar información del lote."""
        if obj.batch:
            return f"{obj.batch.batch_number} (Vence: {obj.batch.expiry_date})"
        return "Sin lote"
    batch_info.short_description = "Lote"
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)
