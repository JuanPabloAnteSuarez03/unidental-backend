from django.contrib import admin
from .models import Category, Product, ProductComponent, ProductBatch


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'description']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'product_type', 'requires_batch_control', 'unit', 'created_at']
    list_filter = ['category', 'product_type', 'requires_batch_control', 'unit', 'created_at']
    search_fields = ['name', 'sku', 'barcode', 'description']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('sku', 'barcode', 'name', 'description', 'unit', 'category')
        }),
        ('Configuración de Producto', {
            'fields': ('product_type', 'requires_batch_control')
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductComponent)
class ProductComponentAdmin(admin.ModelAdmin):
    list_display = ['composite_product', 'component_product', 'quantity', 'created_at']
    list_filter = ['created_at', 'composite_product__category', 'component_product__category']
    search_fields = ['composite_product__name', 'component_product__name', 'composite_product__sku', 'component_product__sku']
    ordering = ['composite_product__name', 'component_product__name']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('composite_product', 'component_product')


@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):
    list_display = ['product', 'batch_number', 'expiry_date', 'days_to_expiry_display', 'is_expired', 'created_at']
    list_filter = ['expiry_date', 'manufacturing_date', 'created_at', 'product__category']
    search_fields = ['product__name', 'product__sku', 'batch_number', 'supplier_reference']
    ordering = ['expiry_date', 'batch_number']
    readonly_fields = ['created_at', 'updated_at', 'is_expired', 'days_to_expiry']
    
    fieldsets = (
        ('Información del Lote', {
            'fields': ('product', 'batch_number', 'supplier_reference')
        }),
        ('Fechas', {
            'fields': ('manufacturing_date', 'expiry_date')
        }),
        ('Estado', {
            'fields': ('is_expired', 'days_to_expiry'),
            'classes': ('collapse',)
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')
    
    def days_to_expiry_display(self, obj):
        """Mostrar días hasta el vencimiento con colores."""
        days = obj.days_to_expiry
        if days < 0:
            return f"Expirado hace {abs(days)} días"
        elif days <= 30:
            return f"{days} días (¡URGENTE!)"
        elif days <= 90:
            return f"{days} días (Próximo)"
        else:
            return f"{days} días"
    days_to_expiry_display.short_description = "Días hasta vencimiento"
