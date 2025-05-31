from django.contrib import admin
from .models import Supplier, PurchaseOption


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Supplier.
    """
    list_display = ['name', 'contact_name', 'phone', 'email', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'contact_name', 'email']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Información básica', {
            'fields': ('name', 'contact_name')
        }),
        ('Contacto', {
            'fields': ('phone', 'email')
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PurchaseOption)
class PurchaseOptionAdmin(admin.ModelAdmin):
    """
    Configuración del admin para PurchaseOption.
    """
    list_display = ['product', 'supplier', 'brand', 'purchase_price', 'valid_from', 'valid_to', 'is_currently_valid']
    list_filter = ['supplier', 'product__category', 'valid_from', 'valid_to', 'created_at']
    search_fields = ['product__name', 'supplier__name', 'brand']
    ordering = ['-valid_from', 'product__name']
    readonly_fields = ['created_at']
    raw_id_fields = ['product', 'supplier']
    
    fieldsets = (
        ('Relaciones', {
            'fields': ('product', 'supplier')
        }),
        ('Detalles del producto', {
            'fields': ('brand', 'purchase_price')
        }),
        ('Validez', {
            'fields': ('valid_from', 'valid_to')
        }),
        ('Metadatos', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def is_currently_valid(self, obj):
        """
        Muestra si la opción está actualmente válida.
        """
        return obj.is_currently_valid()
    
    is_currently_valid.boolean = True
    is_currently_valid.short_description = 'Válido actualmente'
