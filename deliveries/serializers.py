from rest_framework import serializers
from .models import Delivery
from sales.serializers import SaleSerializer
from inventory.serializers import LocationSerializer


class DeliveryListSerializer(serializers.ModelSerializer):
    """Serializer optimizado para lista de entregas."""
    
    # OPTIMIZACIÓN: Usar 'source' para acceder a datos precargados y evitar N+1 queries
    customer_name = serializers.CharField(source='sale.customer.name', read_only=True)
    sale_total = serializers.DecimalField(source='sale.total_net', max_digits=10, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # OPTIMIZACIÓN: Campos básicos que no requieren queries adicionales
    origin_location_name = serializers.CharField(source='origin_location.name', read_only=True)
    dest_location_name = serializers.CharField(source='dest_location.name', read_only=True)
    
    class Meta:
        model = Delivery
        fields = [
            'id', 'sale', 'customer_name', 'sale_total',
            'origin_location_name', 'dest_location_name',
            'shipped_at', 'delivered_at', 'status', 'status_display',
            'created_at'
        ]


class DeliveryDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para una entrega específica."""
    
    customer_name = serializers.ReadOnlyField()
    sale_total = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    delivery_time = serializers.ReadOnlyField()
    
    # Campos de estado para facilitar frontend
    is_pending = serializers.ReadOnlyField()
    is_in_transit = serializers.ReadOnlyField()
    is_delivered = serializers.ReadOnlyField()
    can_be_modified = serializers.ReadOnlyField()
    
    # Relaciones anidadas completas
    sale = SaleSerializer(read_only=True)
    origin_location = LocationSerializer(read_only=True)
    dest_location = LocationSerializer(read_only=True)
    
    class Meta:
        model = Delivery
        fields = [
            'id', 'sale', 'customer_name', 'sale_total',
            'origin_location', 'dest_location',
            'shipped_at', 'delivered_at', 'status', 'status_display',
            'delivery_time', 'is_pending', 'is_in_transit', 'is_delivered',
            'can_be_modified', 'created_at', 'updated_at'
        ]


class DeliveryCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear entregas."""
    
    class Meta:
        model = Delivery
        fields = [
            'sale', 'origin_location', 'dest_location', 'status'
        ]
    
    def validate_sale(self, value):
        """Validar que la venta no tenga ya una entrega."""
        if hasattr(value, 'delivery'):
            raise serializers.ValidationError("Esta venta ya tiene una entrega asignada.")
        return value
    
    def validate(self, attrs):
        """Validaciones a nivel de serializer."""
        # Validar que las ubicaciones sean diferentes
        if attrs['origin_location'] == attrs['dest_location']:
            raise serializers.ValidationError({
                'dest_location': 'La ubicación de destino debe ser diferente a la de origen.'
            })
        
        return attrs


class DeliveryUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar entregas."""
    
    class Meta:
        model = Delivery
        fields = [
            'origin_location', 'dest_location', 'shipped_at', 
            'delivered_at', 'status'
        ]
    
    def validate(self, attrs):
        """Validaciones específicas para actualización."""
        instance = self.instance
        
        # No permitir modificar si ya fue entregado
        if instance.status == 'delivered' and 'status' in attrs:
            if attrs['status'] != 'delivered':
                raise serializers.ValidationError({
                    'status': 'No se puede cambiar el estado de una entrega ya entregada.'
                })
        
        # Validar ubicaciones diferentes si se envían
        origin = attrs.get('origin_location', instance.origin_location)
        dest = attrs.get('dest_location', instance.dest_location)
        
        if origin == dest:
            raise serializers.ValidationError({
                'dest_location': 'La ubicación de destino debe ser diferente a la de origen.'
            })
        
        return attrs


class DeliveryStatusUpdateSerializer(serializers.Serializer):
    """Serializer para actualizar solo el estado de la entrega."""
    
    status = serializers.ChoiceField(choices=Delivery.STATUS_CHOICES)
    
    def validate_status(self, value):
        """Validar transiciones de estado."""
        instance = self.instance
        
        if instance.status == 'delivered':
            raise serializers.ValidationError("No se puede cambiar el estado de una entrega ya entregada.")
        
        # Validar transiciones válidas
        valid_transitions = {
            'pending': ['in_transit', 'delivered'],
            'in_transit': ['delivered'],
        }
        
        if value not in valid_transitions.get(instance.status, []):
            raise serializers.ValidationError(f"Transición de estado inválida: {instance.status} -> {value}")
        
        return value


class DeliveryStatsSerializer(serializers.Serializer):
    """Serializer para estadísticas de entregas."""
    
    total_deliveries = serializers.IntegerField()
    pending_deliveries = serializers.IntegerField()
    in_transit_deliveries = serializers.IntegerField()
    delivered_deliveries = serializers.IntegerField()
    average_delivery_time = serializers.FloatField()
    
    # Estadísticas por ubicación
    deliveries_by_origin = serializers.DictField()
    deliveries_by_destination = serializers.DictField()
    
    # Tendencias temporales
    deliveries_this_month = serializers.IntegerField()
    deliveries_last_month = serializers.IntegerField()
    growth_rate = serializers.FloatField()


class LocationDeliverySummarySerializer(serializers.Serializer):
    """Serializer para resumen de entregas por ubicación."""
    
    location_id = serializers.IntegerField()
    location_name = serializers.CharField()
    total_outgoing = serializers.IntegerField()
    total_incoming = serializers.IntegerField()
    pending_outgoing = serializers.IntegerField()
    pending_incoming = serializers.IntegerField() 