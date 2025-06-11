from rest_framework import serializers
from .models import Customer, Sale, SaleItem
from catalogs.models import Product
from catalogs.serializers import ProductSerializer
from inventory.models import InventoryStock, InventoryMovement, Location
from inventory.serializers import LocationSerializer
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
        """Validaciones básicas del item de venta."""
        quantity = data['quantity']
        
        if quantity <= 0:
            raise serializers.ValidationError({
                'quantity': 'La cantidad debe ser mayor a cero'
            })
        
        return data


class SaleSerializer(serializers.ModelSerializer):
    """Serializador para las ventas con soporte para items anidados."""
    
    items = SaleItemSerializer(many=True)
    customer_details = CustomerSerializer(source='customer', read_only=True)
    location_details = LocationSerializer(source='location', read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'customer', 'customer_details', 'location', 'location_details',
            'sale_date', 'sale_type', 'should_invoice', 'total_gross', 'total_net', 'items'
        ]
        read_only_fields = ['sale_date', 'total_gross', 'total_net']

    def create(self, validated_data):
        """
        Crea una venta con sus items asociados.
        Actualiza automáticamente el stock de los productos usando la sede especificada.
        """
        items_data = validated_data.pop('items')
        sale = Sale.objects.create(**validated_data)
        sale_location = sale.location

        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            
            # Verificar stock en la sede de la venta
            try:
                stock_location = InventoryStock.objects.get(
                    product=product, 
                    location=sale_location
                )
                
                if stock_location.quantity < quantity:
                    raise serializers.ValidationError({
                        'items': f'Stock insuficiente del producto {product.name} en {sale_location.name}. '
                                f'Disponible: {stock_location.quantity}, Solicitado: {quantity}'
                    })
                
                # Crear movimiento de salida en inventario
                InventoryMovement.objects.create(
                    product=product,
                    location=sale_location,
                    movement_type='out',
                    quantity=quantity,
                    notes=f'Venta #{sale.id}'
                )
                
            except InventoryStock.DoesNotExist:
                raise serializers.ValidationError({
                    'items': f'No hay stock del producto {product.name} en {sale_location.name}'
                })
            
            SaleItem.objects.create(sale=sale, **item_data)

        return sale

    def validate_items(self, items):
        """Valida que la venta tenga al menos un item."""
        if not items:
            raise serializers.ValidationError("Se requiere al menos un item en la venta.")
        return items 