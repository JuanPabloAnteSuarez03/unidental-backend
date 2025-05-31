from rest_framework import serializers
from .models import Supplier, PurchaseOption
from catalogs.serializers import ProductSerializer


class SupplierSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo Supplier.
    """
    
    class Meta:
        model = Supplier
        fields = [
            'id',
            'name',
            'contact_name',
            'phone',
            'email',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PurchaseOptionSerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo PurchaseOption.
    """
    product_name = serializers.CharField(source='product.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    category_name = serializers.CharField(source='product.category.name', read_only=True)
    is_currently_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseOption
        fields = [
            'id',
            'product',
            'product_name',
            'supplier',
            'supplier_name',
            'category_name',
            'brand',
            'purchase_price',
            'valid_from',
            'valid_to',
            'is_currently_valid',
            'created_at'
        ]
        read_only_fields = [
            'id', 
            'created_at', 
            'product_name', 
            'supplier_name', 
            'category_name',
            'is_currently_valid'
        ]
    
    def get_is_currently_valid(self, obj):
        """
        Retorna si la opción de compra está actualmente válida.
        """
        return obj.is_currently_valid()


class PurchaseOptionDetailSerializer(PurchaseOptionSerializer):
    """
    Serializer detallado para PurchaseOption que incluye información completa del producto.
    """
    product = ProductSerializer(read_only=True)
    supplier = SupplierSerializer(read_only=True)


class SupplierDetailSerializer(SupplierSerializer):
    """
    Serializer detallado para Supplier que incluye sus opciones de compra.
    """
    purchase_options = PurchaseOptionSerializer(many=True, read_only=True)
    
    class Meta(SupplierSerializer.Meta):
        fields = SupplierSerializer.Meta.fields + ['purchase_options'] 