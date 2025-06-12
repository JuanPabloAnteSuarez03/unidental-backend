from django.contrib import admin
from .models import Customer, Sale, SaleItem, Return, ReturnItem


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'created_at']
    search_fields = ['name', 'email', 'phone']
    list_filter = ['created_at']


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'location', 'sale_date', 'sale_type', 'total_gross', 'total_net']
    list_filter = ['sale_type', 'sale_date', 'should_invoice', 'location']
    search_fields = ['customer__name', 'location__name']
    inlines = [SaleItemInline]
    date_hierarchy = 'sale_date'


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price']
    list_filter = ['sale__sale_type']
    search_fields = ['product__name', 'sale__customer__name']


class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 1
    fields = ['sale_item', 'product', 'quantity_returned', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal']


@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'original_sale', 'location', 'return_date', 'reason', 'total_amount']
    list_filter = ['reason', 'return_date', 'location']
    search_fields = ['customer__name', 'original_sale__id', 'notes']
    inlines = [ReturnItemInline]
    date_hierarchy = 'return_date'
    readonly_fields = ['total_amount']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'original_sale', 'location')


@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    list_display = ['return_obj', 'product', 'quantity_returned', 'unit_price', 'subtotal']
    list_filter = ['return_obj__reason', 'return_obj__return_date']
    search_fields = ['product__name', 'return_obj__customer__name']
    readonly_fields = ['subtotal']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('return_obj', 'product', 'sale_item')
