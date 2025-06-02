from django.contrib import admin
from .models import Location, InventoryStock, InventoryMovement


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'address', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['name', 'address']
    ordering = ['type', 'name']


@admin.register(InventoryStock)
class InventoryStockAdmin(admin.ModelAdmin):
    list_display = ['product', 'location', 'quantity', 'last_updated']
    list_filter = ['location', 'location__type', 'last_updated']
    search_fields = ['product__name', 'product__sku', 'location__name']
    ordering = ['product__name']
    readonly_fields = ['last_updated']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'location')


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'location', 'movement_type', 'quantity', 'occurred_at', 'user']
    list_filter = ['movement_type', 'location', 'location__type', 'occurred_at', 'expiry_date']
    search_fields = ['product__name', 'product__sku', 'location__name', 'notes']
    ordering = ['-occurred_at']
    readonly_fields = ['occurred_at']
    date_hierarchy = 'occurred_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'location', 'user')
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)
