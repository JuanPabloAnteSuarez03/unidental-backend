from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes as perm_decorator
from rest_framework.response import Response
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer
from .filters import CategoryFilter, ProductFilter
from .validators import SKUValidator
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
    
    @swagger_auto_schema(operation_summary="Listar todos los productos",
                         manual_parameters=[
                             openapi.Parameter('name', openapi.IN_QUERY, description="Filtrar productos por nombre (búsqueda parcial)", type=openapi.TYPE_STRING),
                             openapi.Parameter('sku', openapi.IN_QUERY, description="Filtrar productos por SKU (exacto)", type=openapi.TYPE_STRING),
                             openapi.Parameter('barcode', openapi.IN_QUERY, description="Filtrar productos por código de barras (exacto)", type=openapi.TYPE_STRING),
                             openapi.Parameter('category', openapi.IN_QUERY, description="Filtrar productos por ID de categoría", type=openapi.TYPE_INTEGER),
                             openapi.Parameter('category_name', openapi.IN_QUERY, description="Filtrar productos por nombre de categoría (búsqueda parcial)", type=openapi.TYPE_STRING),
                         ])
    def list(self, request, *args, **kwargs):
        """Obtiene una lista de todos los productos.
        
        Filtros disponibles:
        - `?name=textobusqueda` (búsqueda parcial en nombre de producto)
        - `?sku=codigosku` (búsqueda exacta de SKU)
        - `?barcode=codigobarras` (búsqueda exacta de código de barras)
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

@swagger_auto_schema(
    method='get',
    operation_summary="Información del Sistema SKU",
    operation_description="Obtiene la documentación completa del sistema de SKU de Unidental, incluyendo categorías, subcategorías, tipos de materiales y reglas de formato.",
    responses={
        200: openapi.Response(
            description="Información del sistema SKU",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'formato': openapi.Schema(type=openapi.TYPE_STRING, description="Formato del SKU"),
                    'ejemplo': openapi.Schema(type=openapi.TYPE_STRING, description="Ejemplo de SKU válido"),
                    'categorias': openapi.Schema(type=openapi.TYPE_OBJECT, description="Categorías disponibles"),
                    'subcategorias': openapi.Schema(type=openapi.TYPE_OBJECT, description="Subcategorías por categoría"),
                    'tipos_materiales': openapi.Schema(type=openapi.TYPE_OBJECT, description="Tipos y materiales disponibles"),
                    'reglas': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING), description="Reglas del sistema SKU")
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
    return Response(SKUValidator.get_sku_structure_info())


@swagger_auto_schema(
    method='post',
    operation_summary="Generar Siguiente SKU",
    operation_description="Genera automáticamente el siguiente SKU disponible para una combinación de categoría, subcategoría y tipo/material dada. Utiliza el sistema optimizado basado en el inventario real de UNIDENTAL.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['categoria', 'subcategoria', 'tipo'],
        properties={
            'categoria': openapi.Schema(type=openapi.TYPE_STRING, description="Código de categoría (3 letras)", example="LAB"),
            'subcategoria': openapi.Schema(type=openapi.TYPE_STRING, description="Código de subcategoría (3 letras)", example="ART"),
            'tipo': openapi.Schema(type=openapi.TYPE_STRING, description="Código de tipo/material (3 letras)", example="BIO")
        },
        example={
            "categoria": "ANE",
            "subcategoria": "CAR", 
            "tipo": "SEP"
        }
    ),
    responses={
        200: openapi.Response(
            description="SKU generado exitosamente",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'sku_sugerido': openapi.Schema(type=openapi.TYPE_STRING, description="El siguiente SKU disponible", example="ANE-CAR-SEP-002"),
                    'categoria_nombre': openapi.Schema(type=openapi.TYPE_STRING, description="Nombre de la categoría"),
                    'subcategoria_nombre': openapi.Schema(type=openapi.TYPE_STRING, description="Nombre de la subcategoría"),
                    'tipo_nombre': openapi.Schema(type=openapi.TYPE_STRING, description="Nombre del tipo/material")
                }
            )
        ),
        400: "Bad Request - Categoría o subcategoría inválida"
    }
)
@api_view(['POST'])
@perm_decorator([permissions.IsAuthenticated])
def generate_sku(request):
    """
    Endpoint para generar automáticamente el siguiente SKU disponible.
    Recibe categoría, subcategoría y tipo, y devuelve el siguiente número secuencial.
    """
    categoria = request.data.get('categoria', '').upper()
    subcategoria = request.data.get('subcategoria', '').upper()
    tipo = request.data.get('tipo', '').upper()
    
    if not all([categoria, subcategoria, tipo]):
        return Response(
            {'error': 'Se requieren categoria, subcategoria y tipo'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Obtener todos los SKUs existentes para buscar el siguiente disponible
        existing_skus = list(Product.objects.values_list('sku', flat=True))
        
        sku_sugerido = SKUValidator.generate_next_sku(
            categoria=categoria,
            subcategoria=subcategoria, 
            tipo=tipo,
            existing_skus=existing_skus
        )
        
        return Response({
            'sku_sugerido': sku_sugerido,
            'categoria_nombre': SKUValidator.CATEGORIAS.get(categoria, categoria),
            'subcategoria_nombre': SKUValidator.SUBCATEGORIAS.get(categoria, {}).get(subcategoria, subcategoria),
            'tipo_nombre': SKUValidator.TIPOS_MATERIALES.get(tipo, tipo)
        })
        
    except ValueError as e:
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
