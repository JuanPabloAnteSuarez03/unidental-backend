from rest_framework import serializers
from .models import Category, Product

class CategorySerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo Category.
    Incluye todos los campos del modelo.
    """
    class Meta:
        model = Category
        fields = '__all__' # Incluye id, name, description, created_at, updated_at
        read_only_fields = ('created_at', 'updated_at')

class ProductSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo Product.
    Muestra el nombre de la categoría en lugar de solo su ID para facilitar la lectura.
    """
    # Para mostrar más info de la categoría, podríamos hacer esto:
    # category = CategorySerializer(read_only=True) # Para GET
    # category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True) # Para POST/PUT
    # O, más simple, usando slug_related_field para mostrar el nombre en GET y aceptar ID en POST/PUT:
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'sku',
            'name',
            'description',
            'unit',
            'category', # Para POST/PUT, se espera el ID de la categoría
            'category_name', # Para GET, mostrará el nombre de la categoría
            'created_at',
            'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'category_name')
        # Si quieres que category sea write_only (solo para input) y category_name solo para output,
        # puedes definirlo así, pero complica un poco la creación/actualización directa si solo pasas el ID.
        # extra_kwargs = {
        #     'category': {'write_only': True}
        # }

    # Si quieres permitir crear productos junto con una nueva categoría (o seleccionando una existente)
    # de forma más avanzada, podrías sobrescribir el método create().
    # Por ahora, asumimos que la categoría ya existe y se pasa su ID. 