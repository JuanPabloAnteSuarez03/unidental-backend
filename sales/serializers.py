from rest_framework import serializers
from .models import Customer, Sale, SaleItem, Return, ReturnItem
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


class ReturnItemSerializer(serializers.ModelSerializer):
    """Serializador para los items de devolución."""
    
    product_details = ProductSerializer(source='product', read_only=True)
    sale_item_details = SaleItemSerializer(source='sale_item', read_only=True)
    
    class Meta:
        model = ReturnItem
        fields = [
            'id', 'return_obj', 'sale_item', 'sale_item_details', 
            'product', 'product_details', 'quantity_returned', 
            'unit_price', 'subtotal'
        ]
        read_only_fields = ['subtotal']
        extra_kwargs = {'return_obj': {'required': False}}
    
    def update(self, instance, validated_data):
        """
        Actualiza un item de devolución y ajusta el inventario.
        """
        original_quantity = instance.quantity_returned
        
        # Actualiza la instancia con la nueva cantidad
        instance.quantity_returned = validated_data.get('quantity_returned', original_quantity)
        instance.save()

        # Ajustar inventario para la diferencia
        quantity_diff = instance.quantity_returned - original_quantity
        if quantity_diff != 0:
            InventoryMovement.objects.create(
                product=instance.product,
                location=instance.return_obj.location,
                movement_type='in' if quantity_diff > 0 else 'out',
                quantity=abs(quantity_diff),
                notes=f'Ajuste por actualización de item de devolución #{instance.id}'
            )

        return instance

    def validate(self, data):
        """Validaciones del item de devolución."""
        # Durante una actualización, algunos campos no estarán en `data`
        sale_item = data.get('sale_item') or getattr(self.instance, 'sale_item', None)
        product = data.get('product') or getattr(self.instance, 'product', None)
        quantity_returned = data.get('quantity_returned')

        if not sale_item or not product or quantity_returned is None:
            raise serializers.ValidationError("Faltan campos requeridos (sale_item, product, quantity_returned).")

        # Validar que el producto corresponde al item de venta
        if 'product' in data and product != sale_item.product:
            raise serializers.ValidationError({
                'product': 'El producto debe corresponder al item de venta original.'
            })
        
        # Validar cantidad disponible para devolver
        already_returned_qs = ReturnItem.objects.filter(sale_item=sale_item)
        if self.instance:
            already_returned_qs = already_returned_qs.exclude(pk=self.instance.pk)
            
        already_returned = already_returned_qs.aggregate(
            total=models.Sum('quantity_returned')
        )['total'] or 0
        
        available_to_return = sale_item.quantity - already_returned
        
        if quantity_returned > available_to_return:
            raise serializers.ValidationError({
                'quantity_returned': f'No se puede devolver más cantidad de la disponible. '
                                   f'Disponible para devolver: {available_to_return}'
            })
        
        return data


class ReturnSerializer(serializers.ModelSerializer):
    """Serializador para las devoluciones con soporte para items anidados."""
    
    items = ReturnItemSerializer(many=True, required=False)
    customer_details = CustomerSerializer(source='customer', read_only=True)
    location_details = LocationSerializer(source='location', read_only=True)
    original_sale_details = SaleSerializer(source='original_sale', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = Return
        fields = [
            'id', 'original_sale', 'original_sale_details', 'customer', 
            'customer_details', 'location', 'location_details', 'return_date', 
            'reason', 'reason_display', 'notes', 'total_amount', 'items'
        ]
        read_only_fields = ['return_date', 'total_amount']
    
    def create(self, validated_data):
        """
        Crea una devolución con sus items asociados.
        La lógica de inventario se maneja por señales en el modelo ReturnItem.
        """
        items_data = validated_data.pop('items', [])
        return_obj = Return.objects.create(**validated_data)
        
        for item_data in items_data:
            ReturnItem.objects.create(return_obj=return_obj, **item_data)
        
        return return_obj
    
    def update(self, instance, validated_data):
        """
        Actualiza una devolución. No se permite cambiar la venta original ni los items.
        """
        validated_data.pop('items', None) # No se gestionan items aquí
        validated_data.pop('original_sale', None) # No se puede cambiar la venta original
        return super().update(instance, validated_data)

    def validate(self, data):
        """Validaciones de la devolución."""
        
        # En creación, la venta original es obligatoria
        if not self.instance and 'original_sale' not in data:
            raise serializers.ValidationError({'original_sale': 'Este campo es requerido.'})

        # Validar que el cliente de la devolución corresponde al de la venta
        original_sale = data.get('original_sale') or getattr(self.instance, 'original_sale', None)
        if data.get('customer') and original_sale and data['customer'] != original_sale.customer:
            raise serializers.ValidationError({
                'customer': 'El cliente de la devolución no coincide con el de la venta original.'
            })
            
        return data

    def validate_items(self, items):
        """Valida que la devolución tenga al menos un item."""
        if not items:
            raise serializers.ValidationError("Se requiere al menos un item en la devolución.")
        return items 