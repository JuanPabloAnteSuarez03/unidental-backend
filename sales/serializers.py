from rest_framework import serializers
from .models import Customer, Sale, SaleItem
from catalogs.models import Product
from catalogs.serializers import ProductSerializer
from inventory.models import InventoryStock, InventoryMovement
from django.db import models


class CustomerSerializer(serializers.ModelSerializer):
    """Serializador para el modelo de Cliente."""
    
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'email', 'notes', 'created_at']
        read_only_fields = ['created_at']


class SaleItemSerializer(serializers.ModelSerializer):
    """Serializador para los items de venta."""
    
    product_details = ProductSerializer(source='product', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_details', 'quantity', 'unit_price', 'subtotal']

    def get_subtotal(self, obj):
        """Calcula el subtotal del item multiplicando cantidad por precio unitario."""
        return obj.quantity * obj.unit_price

    def validate(self, data):
        """Valida que haya suficiente stock disponible del producto."""
        product = data['product']
        quantity = data['quantity']
        
        # Obtener el stock total disponible del producto en todas las ubicaciones
        total_stock = InventoryStock.objects.filter(product=product).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        
        if total_stock < quantity:
            raise serializers.ValidationError({
                'quantity': f'Stock insuficiente. Disponible: {total_stock}'
            })
        
        return data


class SaleSerializer(serializers.ModelSerializer):
    """Serializador para las ventas con soporte para items anidados."""
    
    items = SaleItemSerializer(many=True)
    customer_details = CustomerSerializer(source='customer', read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'customer', 'customer_details', 'sale_date', 'sale_type',
            'should_invoice', 'total_gross', 'total_net', 'items'
        ]
        read_only_fields = ['sale_date', 'total_gross', 'total_net']

    def create(self, validated_data):
        """
        Crea una venta con sus items asociados.
        Actualiza automáticamente el stock de los productos.
        """
        items_data = validated_data.pop('items')
        sale = Sale.objects.create(**validated_data)

        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            
            # Crear movimiento de salida en inventario
            # Por simplicidad, usamos la primera ubicación con stock disponible
            stock_location = InventoryStock.objects.filter(
                product=product, 
                quantity__gte=quantity
            ).first()
            
            if stock_location:
                InventoryMovement.objects.create(
                    product=product,
                    location=stock_location.location,
                    movement_type='out',
                    quantity=quantity,
                    notes=f'Venta #{sale.id}'
                )
            
            SaleItem.objects.create(sale=sale, **item_data)

        return sale

    def validate_items(self, items):
        """Valida que la venta tenga al menos un item."""
        if not items:
            raise serializers.ValidationError("Se requiere al menos un item en la venta.")
        return items 