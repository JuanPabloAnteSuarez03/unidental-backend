from django.shortcuts import render
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes as perm_decorator, action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta
from .models import Category, Product, ProductComponent, ProductBatch, ProductConversion, SkuCategory, SkuSubCategory, SkuType
from .serializers import (
    CategorySerializer, 
    ProductSerializer, 
    ProductComponentSerializer, 
    ProductBatchSerializer,
    ProductConversionSerializer,
    ConversionExecutionSerializer,
    ConversionSuggestionSerializer,
    ProductSummarySerializer,
    SkuCategorySerializer,
    SkuSubCategorySerializer,
    SkuTypeSerializer
)
from .filters import CategoryFilter, ProductFilter
from .validators import SKUValidator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend


# --- ViewSets para la estructura del SKU ---

class SkuCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar Categorías de SKU.
    Permite crear, leer, actualizar y eliminar categorías de SKU.
    """
    queryset = SkuCategory.objects.all()
    serializer_class = SkuCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name']

class SkuSubCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar Subcategorías de SKU.
    Filtra por 'category' para obtener las subcategorías de una categoría específica.
    Ejemplo: /api/catalogs/sku-subcategories/?category=1
    """
    queryset = SkuSubCategory.objects.all()
    serializer_class = SkuSubCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name']

class SkuTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar Tipos de SKU.
    Filtra por 'subcategory' para obtener los tipos de una subcategoría específica.
    Ejemplo: /api/catalogs/sku-types/?subcategory=5
    """
    queryset = SkuType.objects.all()
    serializer_class = SkuTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subcategory']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name']


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

    **Umbrales de Alerta:**
    - `min_stock_threshold`: Define la cantidad mínima de stock aceptable para un producto
      en una ubicación específica. Si el stock cae por debajo de este umbral, se puede
      generar una alerta. Es un campo opcional.
    - `min_expiry_days_threshold`: Define el número mínimo de días antes de la fecha de
      vencimiento que un lote de producto debe tener para ser considerado "óptimo".
      Lotes con menos días hasta su vencimiento pueden ser marcados para venta prioritaria
      o para no ser aceptados en una compra. Es un campo opcional.
    """
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated] # Proteger por defecto
    filterset_class = ProductFilter

    @swagger_auto_schema(
        operation_summary="Crear un nuevo producto",
        operation_description="Crea un nuevo producto. Se requiere SKU, nombre, unidad y el ID de una categoría existente. El SKU debe seguir el formato optimizado basado en el inventario real de UNIDENTAL.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['sku', 'name', 'unit', 'category'],
            properties={
                'sku': openapi.Schema(type=openapi.TYPE_STRING, description="Código único del producto (SKU)", example="LAB-ART-BIO-001"),
                'barcode': openapi.Schema(type=openapi.TYPE_STRING, description="Código de barras del producto (opcional)", example="8412345678905"),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description="Nombre del producto", example="Articulador BIO-ART"),
                'description': openapi.Schema(type=openapi.TYPE_STRING, description="Descripción detallada (opcional)", example="Articulador semiajustable para laboratorio dental"),
                'unit': openapi.Schema(type=openapi.TYPE_STRING, description="Unidad de medida (ej: unidad, caja)", example="unidad"),
                'category': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la categoría a la que pertenece el producto", example=1)
            },
            example={
                "sku": "ANE-CAR-SEP-001",
                "barcode": "3182818282827",
                "name": "ANESTESIA SEPTODONT 1/100.000",
                "description": "Cartucho de anestesia con epinefrina 1:100.000 para procedimientos odontológicos.",
                "unit": "caja",
                "category": 2 
            }
        ),
        responses={201: ProductSerializer(), 400: "Bad Request"}
    )
    def create(self, request, *args, **kwargs):
        """Crea un nuevo producto. El SKU debe ser único y la categoría debe existir."""
        return super().create(request, *args, **kwargs)
    
    @swagger_auto_schema(operation_summary="Listar todos los productos (paginado)",
                         manual_parameters=[
                             openapi.Parameter('name', openapi.IN_QUERY, description="Filtrar productos por nombre (búsqueda parcial)", type=openapi.TYPE_STRING),
                             openapi.Parameter('sku', openapi.IN_QUERY, description="Filtrar productos por SKU (exacto)", type=openapi.TYPE_STRING),
                             openapi.Parameter('barcode', openapi.IN_QUERY, description="Filtrar productos por código de barras (exacto)", type=openapi.TYPE_STRING),
                             openapi.Parameter('category', openapi.IN_QUERY, description="Filtrar productos por ID de categoría", type=openapi.TYPE_INTEGER),
                             openapi.Parameter('category_name', openapi.IN_QUERY, description="Filtrar productos por nombre de categoría (búsqueda parcial)", type=openapi.TYPE_STRING),
                             openapi.Parameter('min_price', openapi.IN_QUERY, description="Precio de venta mínimo", type=openapi.TYPE_NUMBER, format='decimal'),
                             openapi.Parameter('max_price', openapi.IN_QUERY, description="Precio de venta máximo", type=openapi.TYPE_NUMBER, format='decimal'),
                         ])
    def list(self, request, *args, **kwargs):
        """Obtiene una lista paginada de productos - OPTIMIZADO.
        
        Usa ProductSummarySerializer liviano para evitar N+1 queries.
        Para detalles completos usa /api/catalogs/products/{id}/
        
        Filtros disponibles:
        - `?name=textobusqueda` (búsqueda parcial en nombre de producto)
        - `?sku=codigosku` (búsqueda exacta de SKU)
        - `?barcode=codigobarras` (búsqueda exacta de código de barras)
        - `?category=id_categoria` (ID exacto de la categoría)
        - `?category_name=nombrecategoria` (búsqueda parcial en nombre de categoría)
        - `?min_price=minprice` (precio de venta mínimo)
        - `?max_price=maxprice` (precio de venta máximo)
        """
        from .serializers import ProductSummarySerializer
        
        # Usar queryset optimizado
        queryset = self.filter_queryset(self.get_queryset())
        
        # Usar paginación estándar de DRF
        page = self.paginate_queryset(queryset)
        if page is not None:
            # USAR SERIALIZER LIVIANO para evitar N+1 queries
            serializer = ProductSummarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Si no hay paginación, usar serializer liviano también
        serializer = ProductSummarySerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(operation_summary="Obtener detalle de un producto")
    def retrieve(self, request, *args, **kwargs):
        """Obtiene los detalles de un producto específico por su ID."""
        return super().retrieve(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary="Actualizar un producto",
        operation_description="Actualiza completamente un producto existente por su ID. Incluye la posibilidad de establecer umbrales de stock y vencimiento.",
        request_body=ProductSerializer
    )
    def update(self, request, *args, **kwargs):
        """Actualiza completamente un producto existente por su ID."""
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Actualizar parcialmente un producto",
        operation_description="Actualiza parcialmente un producto existente por su ID. Ideal para modificar solo ciertos campos como los umbrales de stock y vencimiento.",
        request_body=ProductSerializer
    )
    def partial_update(self, request, *args, **kwargs):
        """Actualiza parcialmente un producto existente por su ID."""
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Eliminar un producto")
    def destroy(self, request, *args, **kwargs):
        """Elimina un producto existente por su ID."""
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        method='get',
        operation_summary="Listar productos por sede (ubicación)",
        operation_description="Devuelve productos que pertenecen a una sede específica, determinado por registros de inventario asociados a esa ubicación. Incluye paginación.",
        manual_parameters=[
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de la ubicación (sede)", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('has_stock', openapi.IN_QUERY, description="Solo productos con stock > 0 (default: true)", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('search', openapi.IN_QUERY, description="Búsqueda por nombre/SKU del producto", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Lista paginada de productos por sede",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                        'results': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT))
                    }
                )
            )
        }
    )
    @action(detail=False, methods=['get'], url_path='by-location')
    def by_location(self, request):
        """
        Lista productos que pertenecen a una sede/ubicación dada.
        Criterio: existencia de `InventoryStock` asociado a la `location` indicada
        (si `has_stock=true`, con `quantity__gt=0`).
        """
        from inventory.models import InventoryStock, Location

        location_id = request.query_params.get('location')
        if not location_id:
            return Response({'error': 'El parámetro location es requerido'}, status=status.HTTP_400_BAD_REQUEST)

        # Validar ubicación
        try:
            Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            return Response({'error': 'Ubicación no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        has_stock_param = request.query_params.get('has_stock', 'true').lower()
        has_stock = has_stock_param in ['true', '1', 'yes', 'y']

        # Base queryset
        queryset = self.get_queryset()

        # Filtrar por relación con InventoryStock y ubicación
        filter_kwargs = {
            'stock_locations__location_id': location_id,
        }
        if has_stock:
            filter_kwargs['stock_locations__quantity__gt'] = 0

        # Búsqueda opcional por nombre/SKU
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(sku__icontains=search) | Q(barcode__icontains=search)
            )

        queryset = queryset.filter(**filter_kwargs).distinct().order_by('name')

        # Paginación estándar DRF
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProductSummarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProductSummarySerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Obtener todos los productos sin paginación",
        operation_description="Devuelve todos los productos de la base de datos sin paginación. Útil para cargar listas completas en el frontend.",
        manual_parameters=[
            openapi.Parameter('name', openapi.IN_QUERY, description="Filtrar productos por nombre (búsqueda parcial)", type=openapi.TYPE_STRING),
            openapi.Parameter('sku', openapi.IN_QUERY, description="Filtrar productos por SKU (exacto)", type=openapi.TYPE_STRING),
            openapi.Parameter('barcode', openapi.IN_QUERY, description="Filtrar productos por código de barras (exacto)", type=openapi.TYPE_STRING),
            openapi.Parameter('category', openapi.IN_QUERY, description="Filtrar productos por ID de categoría", type=openapi.TYPE_INTEGER),
            openapi.Parameter('category_name', openapi.IN_QUERY, description="Filtrar productos por nombre de categoría (búsqueda parcial)", type=openapi.TYPE_STRING),
            openapi.Parameter('min_price', openapi.IN_QUERY, description="Precio de venta mínimo", type=openapi.TYPE_NUMBER, format='decimal'),
            openapi.Parameter('max_price', openapi.IN_QUERY, description="Precio de venta máximo", type=openapi.TYPE_NUMBER, format='decimal'),
        ],
        responses={
            200: openapi.Response(
                description="Lista completa de productos obtenida exitosamente",
                schema=ProductSerializer(many=True)
            )
        }
    )
    @action(detail=False, methods=['get'])
    def all(self, request):
        """
        Endpoint que devuelve TODOS los productos sin paginación - OPTIMIZADO.
        
        Usa ProductSummarySerializer liviano para evitar N+1 queries y poder cargar todos los productos.
        
        Filtros disponibles:
        - ?name=textobusqueda (búsqueda parcial en nombre de producto)
        - ?sku=codigosku (búsqueda exacta de SKU)
        - ?barcode=codigobarras (búsqueda exacta de código de barras)
        - ?category=id_categoria (ID exacto de la categoría)
        - ?category_name=nombrecategoria (búsqueda parcial en nombre de categoría)
        - ?min_price=minprice (precio de venta mínimo)
        - ?max_price=maxprice (precio de venta máximo)
        """
        from .serializers import ProductSummarySerializer
        
        # Aplicar filtros usando el filterset configurado
        queryset = self.filter_queryset(self.get_queryset())
        
        # USAR SERIALIZER LIVIANO que no carga componentes ni lotes
        # Esto permite cargar TODOS los productos sin timeout
        serializer = ProductSummarySerializer(queryset, many=True)
        
        return Response({
            'count': len(serializer.data),
            'results': serializer.data
        })

@swagger_auto_schema(
    method='get',
    operation_summary="Información del Sistema SKU",
    operation_description="Obtiene la documentación completa del sistema de SKU de Unidental, incluyendo categorías, subcategorías, tipos de materiales y reglas de formato desde la base de datos.",
    responses={
        200: openapi.Response(
            description="Información del sistema SKU",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'formato': openapi.Schema(type=openapi.TYPE_STRING, description="Formato del SKU"),
                    'ejemplo': openapi.Schema(type=openapi.TYPE_STRING, description="Ejemplo de SKU válido"),
                    'categorias': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        description="Categorías disponibles",
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                    'subcategorias': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        description="Subcategorías disponibles",
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                    'tipos': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        description="Tipos disponibles",
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                    'reglas': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        items=openapi.Schema(type=openapi.TYPE_STRING), 
                        description="Reglas del sistema SKU"
                    )
                }
            )
        )
    }
)
@api_view(['GET'])
@perm_decorator([permissions.IsAuthenticated])
def sku_info(request):
    """
    Endpoint para obtener información completa del sistema de SKU.
    Útil para que los empleados conozcan las reglas y categorías disponibles.
    """
    # Obtener todas las categorías con sus subcategorías y tipos
    categorias = []
    for categoria in SkuCategory.objects.all():
        cat_data = {
            'id': categoria.id,
            'code': categoria.code,
            'name': categoria.name,
            'subcategorias': []
        }
        
        for subcategoria in categoria.subcategories.all():
            sub_data = {
                'id': subcategoria.id,
                'code': subcategoria.code,
                'name': subcategoria.name,
                'tipos': []
            }
            
            for tipo in subcategoria.types.all():
                sub_data['tipos'].append({
                    'id': tipo.id,
                    'code': tipo.code,
                    'name': tipo.name
                })
            
            cat_data['subcategorias'].append(sub_data)
        
        categorias.append(cat_data)
    
    # Obtener todas las subcategorías
    subcategorias = []
    for subcategoria in SkuSubCategory.objects.select_related('category').all():
        subcategorias.append({
            'id': subcategoria.id,
            'code': subcategoria.code,
            'name': subcategoria.name,
            'category_id': subcategoria.category.id,
            'category_name': subcategoria.category.name
        })
    
    # Obtener todos los tipos
    tipos = []
    for tipo in SkuType.objects.select_related('subcategory__category').all():
        tipos.append({
            'id': tipo.id,
            'code': tipo.code,
            'name': tipo.name,
            'subcategory_id': tipo.subcategory.id,
            'subcategory_name': tipo.subcategory.name,
            'category_id': tipo.subcategory.category.id,
            'category_name': tipo.subcategory.category.name
        })
    
    return Response({
        'formato': 'CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL',
        'ejemplo': 'LAB-ART-BIO-001',
        'categorias': categorias,
        'subcategorias': subcategorias,
        'tipos': tipos,
        'reglas': [
            'El SKU debe seguir el formato: CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL',
            'Cada componente debe tener exactamente 3 caracteres',
            'El secuencial debe ser un número de 3 dígitos con ceros a la izquierda',
            'Todos los códigos deben estar en mayúsculas',
            'Los componentes deben existir en la base de datos'
        ]
    })


@swagger_auto_schema(
    method='get',
    operation_summary="Obtener estructura y componentes de SKU",
    operation_description="Devuelve la estructura de SKUs y los componentes existentes desde la base de datos para construir selectores en el frontend.",
    responses={
        200: openapi.Response(
            description="Estructura de SKU obtenida exitosamente",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'categorias': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        description="Categorías de SKU disponibles",
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                    'subcategorias': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        description="Subcategorías de SKU disponibles",
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                    'tipos': openapi.Schema(
                        type=openapi.TYPE_ARRAY, 
                        description="Tipos de SKU disponibles",
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    )
                }
            )
        )
    }
)
@api_view(['GET'])
@perm_decorator([permissions.IsAuthenticated])
def get_sku_structure(request):
    """
    Endpoint para obtener la estructura de SKU y los componentes existentes desde la base de datos.
    Útil para construir selectores en cascada en el frontend.
    """
    # Obtener categorías
    categorias = []
    for categoria in SkuCategory.objects.all():
        categorias.append({
            'id': categoria.id,
            'code': categoria.code,
            'name': categoria.name
        })
    
    # Obtener subcategorías
    subcategorias = []
    for subcategoria in SkuSubCategory.objects.select_related('category').all():
        subcategorias.append({
            'id': subcategoria.id,
            'code': subcategoria.code,
            'name': subcategoria.name,
            'category_id': subcategoria.category.id
        })
    
    # Obtener tipos
    tipos = []
    for tipo in SkuType.objects.select_related('subcategory').all():
        tipos.append({
            'id': tipo.id,
            'code': tipo.code,
            'name': tipo.name,
            'subcategory_id': tipo.subcategory.id
        })
    
    return Response({
        'categorias': categorias,
        'subcategorias': subcategorias,
        'tipos': tipos
    })


@swagger_auto_schema(
    method='post',
    operation_summary="Generar SKU automáticamente",
    operation_description="Genera automáticamente el siguiente SKU disponible basado en los componentes seleccionados de la base de datos.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['category_id', 'subcategory_id', 'type_id'],
        properties={
            'category_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la categoría de SKU", example=1),
            'subcategory_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la subcategoría de SKU", example=1),
            'type_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del tipo de SKU", example=1)
        },
        example={
            "category_id": 1,
            "subcategory_id": 1,
            "type_id": 1
        }
    ),
    responses={
        200: openapi.Response(
            description="SKU generado exitosamente",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'sku_sugerido': openapi.Schema(type=openapi.TYPE_STRING, description="SKU generado"),
                    'categoria_nombre': openapi.Schema(type=openapi.TYPE_STRING, description="Nombre de la categoría"),
                    'subcategoria_nombre': openapi.Schema(type=openapi.TYPE_STRING, description="Nombre de la subcategoría"),
                    'tipo_nombre': openapi.Schema(type=openapi.TYPE_STRING, description="Nombre del tipo")
                }
            )
        ),
        400: "Bad Request"
    }
)
@api_view(['POST'])
@perm_decorator([permissions.IsAuthenticated])
def generate_sku(request):
    """
    Endpoint para generar automáticamente el siguiente SKU disponible.
    Recibe IDs de categoría, subcategoría y tipo desde la base de datos.
    """
    category_id = request.data.get('category_id')
    subcategory_id = request.data.get('subcategory_id')
    type_id = request.data.get('type_id')
    
    if not all([category_id, subcategory_id, type_id]):
        return Response(
            {'error': 'Se requieren category_id, subcategory_id y type_id'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Obtener los objetos de la base de datos
        sku_category = SkuCategory.objects.get(id=category_id)
        sku_subcategory = SkuSubCategory.objects.get(id=subcategory_id, category=sku_category)
        sku_type = SkuType.objects.get(id=type_id, subcategory=sku_subcategory)
        
        # Construir la base del SKU con los códigos
        base_sku = f"{sku_category.code}-{sku_subcategory.code}-{sku_type.code}"
        
        # Obtener todos los SKUs existentes para buscar el siguiente disponible
        existing_skus = list(Product.objects.values_list('sku', flat=True))
        
        sku_sugerido = SKUValidator.generate_next_sku(
            base_sku=base_sku,
            existing_skus=existing_skus
        )
        
        return Response({
            'sku_sugerido': sku_sugerido,
            'categoria_nombre': sku_category.name,
            'subcategoria_nombre': sku_subcategory.name,
            'tipo_nombre': sku_type.name
        })
        
    except SkuCategory.DoesNotExist:
        return Response(
            {'error': f'La categoría con ID {category_id} no existe'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except SkuSubCategory.DoesNotExist:
        return Response(
            {'error': f'La subcategoría con ID {subcategory_id} no existe o no pertenece a la categoría especificada'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except SkuType.DoesNotExist:
        return Response(
            {'error': f'El tipo con ID {type_id} no existe o no pertenece a la subcategoría especificada'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@swagger_auto_schema(
    method='post',
    operation_summary="Validar SKU",
    operation_description="Valida si un SKU propuesto cumple con las reglas del sistema optimizado de UNIDENTAL sin guardarlo en la base de datos.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['sku'],
        properties={
            'sku': openapi.Schema(type=openapi.TYPE_STRING, description="SKU a validar", example="RES-ADH-M3M-001")
        },
        example={"sku": "LAB-ART-BIO-001"}
    ),
    responses={
        200: openapi.Response(
            description="SKU válido",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'valido': openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Si el SKU es válido"),
                    'mensaje': openapi.Schema(type=openapi.TYPE_STRING, description="Mensaje de confirmación o error"),
                    'disponible': openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Si el SKU está disponible (no existe)")
                }
            )
        )
    }
)
@api_view(['POST'])
@perm_decorator([permissions.IsAuthenticated])
def validate_sku(request):
    """
    Endpoint para validar un SKU propuesto sin guardarlo.
    Útil para verificar formato y disponibilidad antes de crear un producto.
    """
    sku = request.data.get('sku', '').upper()
    
    if not sku:
        return Response(
            {'error': 'Se requiere el campo sku'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Validar formato
        validator = SKUValidator()
        validator(sku)
        
        # Verificar disponibilidad
        existe = Product.objects.filter(sku=sku).exists()
        
        if existe:
            return Response({
                'valido': True,
                'mensaje': f'El SKU {sku} tiene formato válido pero ya existe en el sistema.',
                'disponible': False
            })
        else:
            return Response({
                'valido': True,
                'mensaje': f'El SKU {sku} es válido y está disponible.',
                'disponible': True
            })
        
    except Exception as e:
        return Response({
            'valido': False,
            'mensaje': str(e),
            'disponible': False
        })

class ProductComponentViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar componentes de productos compuestos.
    
    Permite crear, leer, actualizar y eliminar las relaciones entre 
    productos compuestos (kits/cajas) y sus componentes individuales.
    """
    queryset = ProductComponent.objects.select_related(
        'composite_product', 'component_product'
    ).all()
    serializer_class = ProductComponentSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Crear una relación producto-componente",
        operation_description="Establece que un producto compuesto contiene una cantidad específica de otro producto como componente.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['composite_product', 'component_product', 'quantity'],
            properties={
                'composite_product': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del producto compuesto (kit/caja)"),
                'component_product': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del producto componente (individual)"),
                'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, description="Cantidad del componente en una unidad del compuesto", minimum=1)
            },
            example={
                "composite_product": 1,
                "component_product": 2,
                "quantity": 10
            }
        ),
        responses={201: ProductComponentSerializer(), 400: "Bad Request"}
    )
    def create(self, request, *args, **kwargs):
        """Crea una nueva relación producto-componente."""
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def by_composite(self, request):
        """
        Obtiene todos los componentes de un producto compuesto específico.
        
        Parámetros:
        - composite_id: ID del producto compuesto
        """
        composite_id = request.query_params.get('composite_id')
        if not composite_id:
            return Response(
                {'error': 'Se requiere el parámetro composite_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        components = self.queryset.filter(composite_product_id=composite_id)
        serializer = self.get_serializer(components, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_component(self, request):
        """
        Obtiene todos los productos compuestos que contienen un componente específico.
        
        Parámetros:
        - component_id: ID del producto componente
        """
        component_id = request.query_params.get('component_id')
        if not component_id:
            return Response(
                {'error': 'Se requiere el parámetro component_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        composites = self.queryset.filter(component_product_id=component_id)
        serializer = self.get_serializer(composites, many=True)
        return Response(serializer.data)


class ProductBatchViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar lotes de productos.
    
    Permite crear, leer, actualizar y eliminar lotes de productos
    que requieren control de fechas de vencimiento.
    """
    queryset = ProductBatch.objects.select_related('product').all()
    serializer_class = ProductBatchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filtrar lotes por parámetros de consulta."""
        queryset = super().get_queryset()
        
        # Filtrar por producto
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Filtrar por estado de expiración
        expired = self.request.query_params.get('expired')
        if expired is not None:
            if expired.lower() == 'true':
                queryset = queryset.filter(expiry_date__lt=timezone.now().date())
            elif expired.lower() == 'false':
                queryset = queryset.filter(expiry_date__gte=timezone.now().date())
        
        return queryset

    @swagger_auto_schema(
        operation_summary="Crear un nuevo lote",
        operation_description="Crea un nuevo lote para un producto que requiere control de lotes.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['product', 'batch_number', 'expiry_date'],
            properties={
                'product': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del producto"),
                'batch_number': openapi.Schema(type=openapi.TYPE_STRING, description="Número de lote del fabricante"),
                'manufacturing_date': openapi.Schema(type=openapi.TYPE_STRING, format='date', description="Fecha de fabricación (opcional)"),
                'expiry_date': openapi.Schema(type=openapi.TYPE_STRING, format='date', description="Fecha de vencimiento"),
                'supplier_reference': openapi.Schema(type=openapi.TYPE_STRING, description="Referencia del proveedor (opcional)"),
                'notes': openapi.Schema(type=openapi.TYPE_STRING, description="Notas adicionales (opcional)")
            },
            example={
                "product": 1,
                "batch_number": "LOT2024001",
                "manufacturing_date": "2024-01-15",
                "expiry_date": "2026-01-15",
                "supplier_reference": "PROV-REF-001",
                "notes": "Lote en condiciones óptimas"
            }
        ),
        responses={201: ProductBatchSerializer(), 400: "Bad Request"}
    )
    def create(self, request, *args, **kwargs):
        """Crea un nuevo lote de producto."""
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        method='get',
        operation_summary="Obtener lotes próximos a vencer",
        operation_description="Retorna lotes que vencen en los próximos días especificados.",
        manual_parameters=[
            openapi.Parameter('days', openapi.IN_QUERY, description="Días hacia adelante para alertas (default: 30)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('product', openapi.IN_QUERY, description="Filtrar por producto específico", type=openapi.TYPE_INTEGER),
        ],
        responses={200: ProductBatchSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """
        Obtiene los lotes que están próximos a vencer.
        
        Parámetros:
        - days: Número de días hacia adelante (default: 30)
        - product: ID del producto para filtrar (opcional)
        """
        days_ahead = int(request.query_params.get('days', 30))
        product_id = request.query_params.get('product')
        
        expiry_threshold = timezone.now().date() + timedelta(days=days_ahead)
        
        queryset = self.get_queryset().filter(
            expiry_date__lte=expiry_threshold,
            expiry_date__gte=timezone.now().date()
        ).order_by('expiry_date')
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Obtener lotes expirados",
        operation_description="Retorna todos los lotes que ya han expirado.",
        manual_parameters=[
            openapi.Parameter('product', openapi.IN_QUERY, description="Filtrar por producto específico", type=openapi.TYPE_INTEGER),
        ],
        responses={200: ProductBatchSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """
        Obtiene todos los lotes que ya han expirado.
        
        Parámetros:
        - product: ID del producto para filtrar (opcional)
        """
        product_id = request.query_params.get('product')
        
        queryset = self.get_queryset().filter(
            expiry_date__lt=timezone.now().date()
        ).order_by('-expiry_date')
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ProductConversionViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar conversiones de productos.
    Permite crear, leer, actualizar y eliminar conversiones entre productos.
    """
    queryset = ProductConversion.objects.all()
    serializer_class = ProductConversionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['from_product', 'to_product', 'is_reversible']
    search_fields = ['from_product__name', 'to_product__name', 'from_product__sku', 'to_product__sku']
    ordering_fields = ['from_product__name', 'to_product__name', 'conversion_rate', 'created_at']

    @swagger_auto_schema(
        method='get',
        manual_parameters=[
            openapi.Parameter('product', openapi.IN_QUERY, description="ID del producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de la ubicación", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: ProductConversionSerializer(many=True),
            400: 'Parámetros inválidos'
        }
    )
    @action(detail=False, methods=['get'], url_path='possible-from')
    def possible_conversions_from(self, request):
        """
        Obtiene las conversiones posibles desde un producto específico.
        Opcionalmente filtra por disponibilidad en una ubicación.
        """
        product_id = request.query_params.get('product')
        location_id = request.query_params.get('location')
        
        if not product_id:
            return Response(
                {'error': 'Se requiere el parámetro product'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        location = None
        if location_id:
            try:
                from inventory.models import Location
                location = Location.objects.get(id=location_id)
            except Location.DoesNotExist:
                return Response(
                    {'error': 'Ubicación no encontrada'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        conversions = ProductConversion.get_possible_conversions(product, location)
        serializer = self.get_serializer(conversions, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        manual_parameters=[
            openapi.Parameter('product', openapi.IN_QUERY, description="ID del producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de la ubicación", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: ProductConversionSerializer(many=True),
            400: 'Parámetros inválidos'
        }
    )
    @action(detail=False, methods=['get'], url_path='possible-to')
    def possible_conversions_to(self, request):
        """
        Obtiene las conversiones que pueden generar el producto especificado.
        Útil para saber qué productos puedes "abrir" para conseguir más stock.
        """
        product_id = request.query_params.get('product')
        location_id = request.query_params.get('location')
        
        if not product_id:
            return Response(
                {'error': 'Se requiere el parámetro product'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        location = None
        if location_id:
            try:
                from inventory.models import Location
                location = Location.objects.get(id=location_id)
            except Location.DoesNotExist:
                return Response(
                    {'error': 'Ubicación no encontrada'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        conversions = ProductConversion.get_reverse_conversions(product, location)
        serializer = self.get_serializer(conversions, many=True)
        return Response(serializer.data)


@swagger_auto_schema(
    method='post',
    request_body=ConversionExecutionSerializer,
    responses={
        200: openapi.Response(
            description="Conversión ejecutada exitosamente",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'result': openapi.Schema(type=openapi.TYPE_OBJECT)
                }
            )
        ),
        400: 'Datos inválidos',
        404: 'Conversión no encontrada'
    }
)
@api_view(['POST'])
@perm_decorator([IsAuthenticated])
def execute_conversion(request):
    """
    Ejecuta una conversión manual de productos.
    
    Ejemplo de request:
    {
        "conversion_id": 1,
        "quantity_to_convert": 2,
        "location_id": 1,
        "batch_id": 5,  // opcional
        "notes": "Abriendo cajas para venta"  // opcional
    }
    """
    serializer = ConversionExecutionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        conversion = ProductConversion.objects.get(id=serializer.validated_data['conversion_id'])
        from inventory.models import Location, ProductBatch
        location = Location.objects.get(id=serializer.validated_data['location_id'])
        
        batch = None
        if serializer.validated_data.get('batch_id'):
            batch = ProductBatch.objects.get(id=serializer.validated_data['batch_id'])
        
        # Ejecutar la conversión
        result = conversion.execute_conversion(
            quantity_to_convert=serializer.validated_data['quantity_to_convert'],
            location=location,
            batch=batch,
            user=request.user
        )
        
        return Response({
            'success': True,
            'message': f'Conversión ejecutada: {result["converted_from"]["quantity"]} {result["converted_from"]["product"]} → {result["converted_to"]["quantity"]} {result["converted_to"]["product"]}',
            'result': result
        })
        
    except ProductConversion.DoesNotExist:
        return Response(
            {'error': 'Conversión no encontrada'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@swagger_auto_schema(
    method='post',
    request_body=ConversionSuggestionSerializer,
    responses={
        200: openapi.Response(
            description="Sugerencias de conversión",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'current_stock': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'required_quantity': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'deficit': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'suggestions': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'conversion': openapi.Schema(type=openapi.TYPE_OBJECT),
                                'available_stock': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'can_provide': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'units_needed': openapi.Schema(type=openapi.TYPE_INTEGER)
                            }
                        )
                    )
                }
            )
        ),
        400: 'Datos inválidos'
    }
)
@api_view(['POST'])
@perm_decorator([IsAuthenticated])
def suggest_conversions(request):
    """
    Sugiere conversiones disponibles cuando no hay suficiente stock de un producto.
    """
    serializer = ConversionSuggestionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        product = Product.objects.get(id=serializer.validated_data['product_id'])
        from inventory.models import Location, InventoryStock
        location = Location.objects.get(id=serializer.validated_data['location_id'])
        required_quantity = serializer.validated_data['required_quantity']
        # Obtener stock actual
        current_stock = InventoryStock.get_total_stock(product, location)
        deficit = max(0, required_quantity - current_stock)
        if deficit == 0:
            return Response({
                'current_stock': current_stock,
                'required_quantity': required_quantity,
                'deficit': 0,
                'suggestions': [],
                'message': 'Hay suficiente stock disponible'
            })
        # Buscar conversiones que puedan generar este producto (permitir no reversibles)
        reverse_conversions = ProductConversion.get_reverse_conversions(product, location, allow_non_reversible=True)
        suggestions = []
        for conversion in reverse_conversions:
            available_stock = InventoryStock.get_total_stock(conversion.from_product, location)
            if available_stock > 0:
                can_provide = available_stock * conversion.conversion_rate
                units_needed = max(1, (deficit + conversion.conversion_rate - 1) // conversion.conversion_rate)
                suggestions.append({
                    'conversion': ProductConversionSerializer(conversion).data,
                    'available_stock': available_stock,
                    'can_provide': can_provide,
                    'units_needed': units_needed,
                    'would_convert_to': min(units_needed * conversion.conversion_rate, deficit)
                })
        # Ordenar por cantidad que pueden proveer (descendente)
        suggestions.sort(key=lambda x: x['can_provide'], reverse=True)
        return Response({
            'current_stock': current_stock,
            'required_quantity': required_quantity,
            'deficit': deficit,
            'suggestions': suggestions
        })
    except (Product.DoesNotExist, Location.DoesNotExist) as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_404_NOT_FOUND
        )
