from django.shortcuts import render
from rest_framework import viewsets, permissions
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer
from .filters import CategoryFilter, ProductFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Create your views here.

class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar Categorías de productos.

    Permite crear, leer, actualizar y eliminar categorías.
    Las categorías se utilizan para agrupar productos.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated] # Proteger por defecto, ajustar según necesidad
    filterset_class = CategoryFilter

    @swagger_auto_schema(
        operation_summary="Crear una nueva categoría",
        operation_description="Crea una nueva categoría de productos. El nombre debe ser único.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['name'],
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING, description="Nombre de la categoría", example="Insumos Quirúrgicos"),
                'description': openapi.Schema(type=openapi.TYPE_STRING, description="Descripción detallada (opcional)", example="Materiales utilizados en procedimientos quirúrgicos.")
            },
            example={
                "name": "Equipamiento de Oficina",
                "description": "Sillas, escritorios, y otros muebles para oficina."
            }
        ),
        responses={201: CategorySerializer(), 400: "Bad Request"}
    )
    def create(self, request, *args, **kwargs):
        """Crea una nueva categoría de productos."""
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Listar todas las categorías", 
                         manual_parameters=[
                             openapi.Parameter('name', openapi.IN_QUERY, description="Filtrar categorías por nombre (búsqueda parcial)", type=openapi.TYPE_STRING),
                         ])
    def list(self, request, *args, **kwargs):
        """Obtiene una lista de todas las categorías de productos disponibles.
        
        Puedes filtrar por nombre usando el parámetro `?name=textobusqueda`.
        """
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Obtener detalle de una categoría")
    def retrieve(self, request, *args, **kwargs):
        """Obtiene los detalles de una categoría específica por su ID."""
        return super().retrieve(request, *args, **kwargs)
    
    @swagger_auto_schema(operation_summary="Actualizar una categoría")
    def update(self, request, *args, **kwargs):
        """Actualiza completamente una categoría existente por su ID."""
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Actualizar parcialmente una categoría")
    def partial_update(self, request, *args, **kwargs):
        """Actualiza parcialmente una categoría existente por su ID."""
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Eliminar una categoría")
    def destroy(self, request, *args, **kwargs):
        """Elimina una categoría existente por su ID."""
        return super().destroy(request, *args, **kwargs)

class ProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar Productos.

    Permite CRUD de productos. Cada producto debe estar asociado a una categoría.
    El SKU (Stock Keeping Unit) debe ser único para cada producto.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated] # Proteger por defecto
    filterset_class = ProductFilter

    @swagger_auto_schema(
        operation_summary="Crear un nuevo producto",
        operation_description="Crea un nuevo producto. Se requiere SKU, nombre, unidad y el ID de una categoría existente.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['sku', 'name', 'unit', 'category'],
            properties={
                'sku': openapi.Schema(type=openapi.TYPE_STRING, description="Código único del producto (SKU)", example="DENT-00123"),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description="Nombre del producto", example="Resina Compuesta Universal A2"),
                'description': openapi.Schema(type=openapi.TYPE_STRING, description="Descripción detallada (opcional)", example="Resina nanohíbrida para restauraciones anteriores y posteriores."),
                'unit': openapi.Schema(type=openapi.TYPE_STRING, description="Unidad de medida (ej: unidad, caja)", example="unidad"),
                'category': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la categoría a la que pertenece el producto", example=1)
            },
            example={
                "sku": "INSTR-HAND-001",
                "name": "Espejo Dental #5",
                "description": "Espejo de exploración con mango, número 5.",
                "unit": "unidad",
                "category": 2 
            }
        ),
        responses={201: ProductSerializer(), 400: "Bad Request"}
    )
    def create(self, request, *args, **kwargs):
        """Crea un nuevo producto. El SKU debe ser único y la categoría debe existir."""
        return super().create(request, *args, **kwargs)
    
    @swagger_auto_schema(operation_summary="Listar todos los productos",
                         manual_parameters=[
                             openapi.Parameter('name', openapi.IN_QUERY, description="Filtrar productos por nombre (búsqueda parcial)", type=openapi.TYPE_STRING),
                             openapi.Parameter('sku', openapi.IN_QUERY, description="Filtrar productos por SKU (exacto)", type=openapi.TYPE_STRING),
                             openapi.Parameter('category', openapi.IN_QUERY, description="Filtrar productos por ID de categoría", type=openapi.TYPE_INTEGER),
                             openapi.Parameter('category_name', openapi.IN_QUERY, description="Filtrar productos por nombre de categoría (búsqueda parcial)", type=openapi.TYPE_STRING),
                         ])
    def list(self, request, *args, **kwargs):
        """Obtiene una lista de todos los productos.
        
        Filtros disponibles:
        - `?name=textobusqueda` (búsqueda parcial en nombre de producto)
        - `?sku=codigosku` (búsqueda exacta de SKU)
        - `?category=id_categoria` (ID exacto de la categoría)
        - `?category_name=nombrecategoria` (búsqueda parcial en nombre de categoría)
        """
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Obtener detalle de un producto")
    def retrieve(self, request, *args, **kwargs):
        """Obtiene los detalles de un producto específico por su ID."""
        return super().retrieve(request, *args, **kwargs)
    
    @swagger_auto_schema(operation_summary="Actualizar un producto")
    def update(self, request, *args, **kwargs):
        """Actualiza completamente un producto existente por su ID."""
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Actualizar parcialmente un producto")
    def partial_update(self, request, *args, **kwargs):
        """Actualiza parcialmente un producto existente por su ID."""
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Eliminar un producto")
    def destroy(self, request, *args, **kwargs):
        """Elimina un producto existente por su ID."""
        return super().destroy(request, *args, **kwargs)
