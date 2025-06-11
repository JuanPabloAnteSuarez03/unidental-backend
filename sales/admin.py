from django.contrib import admin
from .models import Customer, Sale, SaleItem


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'created_at']
    search_fields = ['name', 'phone', 'email']
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
