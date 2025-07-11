from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db.models import Sum, Q, F
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Location, InventoryStock, InventoryMovement
from .serializers import (
    LocationSerializer, InventoryStockSerializer, InventoryMovementSerializer,
    StockAlertSerializer, ExpiryAlertSerializer, StockSummarySerializer,
    CompositeBreakdownSerializer, BatchStockSerializer, BatchLocationStockSerializer,
    ProductBatchesStockSerializer, LocationBatchStockSerializer
)
from .filters import LocationFilter, InventoryStockFilter, InventoryMovementFilter
from catalogs.models import Product, ProductBatch


class LocationViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar ubicaciones (sedes y bodegas)."""
    
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LocationFilter
    search_fields = ['name', 'address']
    ordering_fields = ['name', 'type', 'created_at']
    ordering = ['type', 'name']

    @swagger_auto_schema(
        operation_description="Crear una nueva ubicación (sede o bodega)",
        request_body=LocationSerializer,
        responses={
            201: LocationSerializer,
            400: "Datos inválidos"
        }
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Obtener lista de ubicaciones con filtros y búsqueda",
        manual_parameters=[
            openapi.Parameter('type', openapi.IN_QUERY, description="Filtrar por tipo (sede/bodega)", type=openapi.TYPE_STRING),
            openapi.Parameter('search', openapi.IN_QUERY, description="Buscar por nombre o dirección", type=openapi.TYPE_STRING),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class InventoryStockViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar el stock de inventario."""
    
    queryset = InventoryStock.objects.select_related('product', 'location').all()
    serializer_class = InventoryStockSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = InventoryStockFilter
    search_fields = ['product__name', 'product__sku', 'location__name']
    ordering_fields = ['quantity', 'last_updated', 'product__name']
    ordering = ['product__name']

    @swagger_auto_schema(
        operation_description="Obtener lista de stock con filtros por ubicación y producto",
        manual_parameters=[
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de ubicación", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location_type', openapi.IN_QUERY, description="Tipo de ubicación (sede/bodega)", type=openapi.TYPE_STRING),
            openapi.Parameter('location_name', openapi.IN_QUERY, description="Buscar por nombre de ubicación", type=openapi.TYPE_STRING),
            openapi.Parameter('product', openapi.IN_QUERY, description="ID del producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('product_name', openapi.IN_QUERY, description="Buscar por nombre de producto", type=openapi.TYPE_STRING),
            openapi.Parameter('product_sku', openapi.IN_QUERY, description="Buscar por SKU del producto", type=openapi.TYPE_STRING),
            openapi.Parameter('product_category', openapi.IN_QUERY, description="ID de categoría del producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('product_category_name', openapi.IN_QUERY, description="Buscar por nombre de categoría", type=openapi.TYPE_STRING),
            openapi.Parameter('min_quantity', openapi.IN_QUERY, description="Cantidad mínima", type=openapi.TYPE_INTEGER),
            openapi.Parameter('max_quantity', openapi.IN_QUERY, description="Cantidad máxima", type=openapi.TYPE_INTEGER),
            openapi.Parameter('has_stock', openapi.IN_QUERY, description="Solo productos con stock (true) o sin stock (false)", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('batch', openapi.IN_QUERY, description="ID del lote específico", type=openapi.TYPE_INTEGER),
            openapi.Parameter('batch_number', openapi.IN_QUERY, description="Número de lote exacto", type=openapi.TYPE_STRING),
            openapi.Parameter('batch_number_contains', openapi.IN_QUERY, description="Buscar por número de lote", type=openapi.TYPE_STRING),
            openapi.Parameter('requires_batch_control', openapi.IN_QUERY, description="Solo productos que requieren control de lotes", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('has_batch', openapi.IN_QUERY, description="Filtrar por existencia de lote (true/false)", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('expiry_date', openapi.IN_QUERY, description="Fecha de vencimiento exacta (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('expiry_from', openapi.IN_QUERY, description="Vence después de esta fecha (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('expiry_to', openapi.IN_QUERY, description="Vence antes de esta fecha (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('expiry_days_ahead', openapi.IN_QUERY, description="Vence en los próximos N días", type=openapi.TYPE_INTEGER),
            openapi.Parameter('is_expired', openapi.IN_QUERY, description="Solo lotes vencidos (true/false)", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('search', openapi.IN_QUERY, description="Búsqueda general en producto y ubicación", type=openapi.TYPE_STRING),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        method='get',
        operation_description="Obtener resumen de stock por producto (suma de todas las ubicaciones)",
        responses={200: StockSummarySerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Endpoint para obtener resumen de stock por producto - CORREGIDO PARA N+1."""
        
        # UNA SOLA QUERY: Obtener todos los stocks con cantidad > 0
        all_stock = InventoryStock.objects.filter(
            quantity__gt=0
        ).select_related('product', 'location').values(
            'product__id', 'product__name', 'product__sku', 'product__unit', 
            'product__requires_batch_control', 'location__id', 'location__name', 
            'location__type', 'quantity'
        ).order_by('product__name', 'location__name')
        
        # Agrupar por producto en Python (más eficiente que N queries)
        products_dict = {}
        for stock in all_stock:
            product_id = stock['product__id']
            
            if product_id not in products_dict:
                products_dict[product_id] = {
                    'product_id': product_id,
                    'product_name': stock['product__name'],
                    'product_sku': stock['product__sku'],
                    'product_unit': stock['product__unit'],
                    'requires_batch_control': stock['product__requires_batch_control'],
                    'total_quantity': 0,
                    'locations': []
                }
            
            # Agregar ubicación y sumar cantidad
            products_dict[product_id]['locations'].append({
                'location__id': stock['location__id'],
                'location__name': stock['location__name'],
                'location__type': stock['location__type'],
                'quantity': stock['quantity']
            })
            products_dict[product_id]['total_quantity'] += stock['quantity']
        
        # Convertir a lista ordenada
        result = list(products_dict.values())
        result.sort(key=lambda x: x['product_name'])
        
        serializer = StockSummarySerializer(result, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Obtener todo el stock sin paginación",
        operation_description="Devuelve todo el stock de inventario sin paginación. Útil para cargar listas completas en el frontend.",
        manual_parameters=[
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de ubicación", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location_type', openapi.IN_QUERY, description="Tipo de ubicación (sede/bodega)", type=openapi.TYPE_STRING),
            openapi.Parameter('location_name', openapi.IN_QUERY, description="Buscar por nombre de ubicación", type=openapi.TYPE_STRING),
            openapi.Parameter('product', openapi.IN_QUERY, description="ID del producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('product_name', openapi.IN_QUERY, description="Buscar por nombre de producto", type=openapi.TYPE_STRING),
            openapi.Parameter('product_sku', openapi.IN_QUERY, description="Buscar por SKU del producto", type=openapi.TYPE_STRING),
            openapi.Parameter('product_category', openapi.IN_QUERY, description="ID de categoría del producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('product_category_name', openapi.IN_QUERY, description="Buscar por nombre de categoría", type=openapi.TYPE_STRING),
            openapi.Parameter('min_quantity', openapi.IN_QUERY, description="Cantidad mínima", type=openapi.TYPE_INTEGER),
            openapi.Parameter('max_quantity', openapi.IN_QUERY, description="Cantidad máxima", type=openapi.TYPE_INTEGER),
            openapi.Parameter('has_stock', openapi.IN_QUERY, description="Solo productos con stock (true) o sin stock (false)", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('search', openapi.IN_QUERY, description="Búsqueda general en producto y ubicación", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Lista completa de stock obtenida exitosamente",
                schema=InventoryStockSerializer(many=True)
            )
        }
    )
    @action(detail=False, methods=['get'])
    def all(self, request):
        """
        Endpoint que devuelve todo el stock sin paginación.
        
        Este endpoint aplica los mismos filtros que el endpoint list(),
        pero devuelve todos los resultados sin paginar.
        
        Filtros disponibles:
        - ?location=id_ubicacion (ID de la ubicación)
        - ?location_type=tipo (Tipo de ubicación: sede/bodega)
        - ?location_name=nombre (búsqueda por nombre de ubicación)
        - ?product=id_producto (ID del producto específico)
        - ?product_name=nombre (búsqueda por nombre de producto)
        - ?product_sku=sku (búsqueda por SKU del producto)
        - ?product_category=id (ID de categoría del producto)
        - ?product_category_name=nombre (búsqueda por nombre de categoría)
        - ?min_quantity=cantidad (cantidad mínima)
        - ?max_quantity=cantidad (cantidad máxima)
        - ?has_stock=true/false (solo productos con/sin stock)
        - ?search=texto (búsqueda general en producto y ubicación)
        """
        # Aplicar filtros usando el filterset configurado
        queryset = self.filter_queryset(self.get_queryset())
        
        # Serializar todo el stock sin paginación
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })

    @swagger_auto_schema(
        method='get',
        operation_summary="Obtener stock de un lote específico por ubicaciones",
        operation_description="Devuelve el stock de un lote específico de un producto distribuido por ubicaciones",
        manual_parameters=[
            openapi.Parameter('product', openapi.IN_QUERY, description="ID del producto (requerido)", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('batch', openapi.IN_QUERY, description="ID del lote específico (requerido)", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('location_type', openapi.IN_QUERY, description="Filtrar por tipo de ubicación (sede/bodega)", type=openapi.TYPE_STRING),
            openapi.Parameter('location_name', openapi.IN_QUERY, description="Buscar por nombre de ubicación", type=openapi.TYPE_STRING),
        ],
        responses={
            200: BatchLocationStockSerializer,
            400: "Parámetros requeridos faltantes"
        }
    )
    @action(detail=False, methods=['get'])
    def batch_stock_by_locations(self, request):
        """
        Obtiene el stock de un lote específico distribuido por ubicaciones.
        
        Parámetros requeridos:
        - product: ID del producto
        - batch: ID del lote específico
        
        Filtros opcionales:
        - location_type: sede/bodega
        - location_name: búsqueda por nombre
        """
        product_id = request.query_params.get('product')
        batch_id = request.query_params.get('batch')
        
        if not product_id or not batch_id:
            return Response(
                {'error': 'Los parámetros product y batch son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el producto y lote existen
        try:
            product = Product.objects.get(id=product_id)
            batch = ProductBatch.objects.get(id=batch_id, product=product)
        except (Product.DoesNotExist, ProductBatch.DoesNotExist):
            return Response(
                {'error': 'Producto o lote no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener stock del lote por ubicaciones
        stock_query = InventoryStock.objects.filter(
            product=product,
            batch=batch,
            quantity__gt=0
        ).select_related('location')
        
        # Aplicar filtros opcionales
        location_type = request.query_params.get('location_type')
        location_name = request.query_params.get('location_name')
        
        if location_type:
            stock_query = stock_query.filter(location__type=location_type)
        if location_name:
            stock_query = stock_query.filter(location__name__icontains=location_name)
        
        # Procesar datos
        locations_data = []
        total_quantity = 0
        
        for stock in stock_query:
            locations_data.append({
                'location_id': stock.location.id,
                'location_name': stock.location.name,
                'location_type': stock.location.type,
                'quantity': stock.quantity,
                'last_updated': stock.last_updated
            })
            total_quantity += stock.quantity
        
        result = {
            'product_id': product.id,
            'product_name': product.name,
            'product_sku': product.sku,
            'product_unit': product.unit,
            'requires_batch_control': product.requires_batch_control,
            'batch_id': batch.id,
            'batch_number': batch.batch_number,
            'expiry_date': batch.expiry_date,
            'days_to_expiry': batch.days_to_expiry,
            'is_expired': batch.is_expired,
            'locations': locations_data,
            'total_quantity': total_quantity
        }
        
        serializer = BatchLocationStockSerializer(result)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Obtener todos los lotes de un producto con stock por ubicaciones",
        operation_description="Devuelve todos los lotes de un producto específico con su stock distribuido por ubicaciones",
        manual_parameters=[
            openapi.Parameter('product', openapi.IN_QUERY, description="ID del producto (requerido)", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('location_type', openapi.IN_QUERY, description="Filtrar por tipo de ubicación (sede/bodega)", type=openapi.TYPE_STRING),
            openapi.Parameter('location_name', openapi.IN_QUERY, description="Buscar por nombre de ubicación", type=openapi.TYPE_STRING),
            openapi.Parameter('only_available', openapi.IN_QUERY, description="Solo lotes con stock disponible", type=openapi.TYPE_BOOLEAN, default=True),
            openapi.Parameter('include_expired', openapi.IN_QUERY, description="Incluir lotes vencidos", type=openapi.TYPE_BOOLEAN, default=False),
        ],
        responses={
            200: ProductBatchesStockSerializer,
            400: "Parámetro product requerido",
            404: "Producto no encontrado"
        }
    )
    @action(detail=False, methods=['get'])
    def product_batches_stock(self, request):
        """
        Obtiene todos los lotes de un producto con su stock por ubicaciones.
        
        Parámetros requeridos:
        - product: ID del producto
        
        Filtros opcionales:
        - location_type: sede/bodega
        - location_name: búsqueda por nombre
        - only_available: solo lotes con stock (default: true)
        - include_expired: incluir lotes vencidos (default: false)
        """
        product_id = request.query_params.get('product')
        
        if not product_id:
            return Response(
                {'error': 'El parámetro product es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el producto existe
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Parámetros de filtro
        location_type = request.query_params.get('location_type')
        location_name = request.query_params.get('location_name')
        only_available = request.query_params.get('only_available', 'true').lower() == 'true'
        include_expired = request.query_params.get('include_expired', 'false').lower() == 'true'
        
        # Construir query base
        stock_query = InventoryStock.objects.filter(product=product).select_related('batch', 'location')
        
        if only_available:
            stock_query = stock_query.filter(quantity__gt=0)
        
        if not include_expired:
            from django.utils import timezone
            stock_query = stock_query.filter(
                Q(batch__isnull=True) | Q(batch__expiry_date__gte=timezone.now().date())
            )
        
        # Aplicar filtros de ubicación
        if location_type:
            stock_query = stock_query.filter(location__type=location_type)
        if location_name:
            stock_query = stock_query.filter(location__name__icontains=location_name)
        
        # Agrupar por lotes
        batches_dict = {}
        total_stock = 0
        
        for stock in stock_query:
            batch_id = stock.batch.id if stock.batch else None
            
            if batch_id not in batches_dict:
                batch = stock.batch
                batches_dict[batch_id] = {
                    'batch_id': batch.id,
                    'batch_number': batch.batch_number,
                    'manufacturing_date': batch.manufacturing_date,
                    'expiry_date': batch.expiry_date,
                    'days_to_expiry': batch.days_to_expiry,
                    'is_expired': batch.is_expired,
                    'supplier_reference': batch.supplier_reference,
                    'notes': batch.notes,
                    'locations': [],
                    'total_quantity': 0
                }
            
            # Añadir ubicación
            batches_dict[batch_id]['locations'].append({
                'location_id': stock.location.id,
                'location_name': stock.location.name,
                'location_type': stock.location.type,
                'quantity': stock.quantity,
                'last_updated': stock.last_updated
            })
            batches_dict[batch_id]['total_quantity'] += stock.quantity
            total_stock += stock.quantity
        
        # Ordenar lotes por fecha de vencimiento (FIFO)
        batches_list = list(batches_dict.values())
        batches_list.sort(key=lambda x: x['expiry_date'] if x['expiry_date'] else timezone.now().date())
        
        result = {
            'product_id': product.id,
            'product_name': product.name,
            'product_sku': product.sku,
            'product_unit': product.unit,
            'requires_batch_control': product.requires_batch_control,
            'batches': batches_list,
            'total_stock': total_stock
        }
        
        serializer = ProductBatchesStockSerializer(result)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Obtener stock de lotes en una ubicación específica",
        operation_description="Devuelve todos los productos con lotes en una ubicación específica",
        manual_parameters=[
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de la ubicación (requerido)", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('product', openapi.IN_QUERY, description="Filtrar por ID del producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('product_name', openapi.IN_QUERY, description="Buscar por nombre de producto", type=openapi.TYPE_STRING),
            openapi.Parameter('batch_number', openapi.IN_QUERY, description="Buscar por número de lote", type=openapi.TYPE_STRING),
            openapi.Parameter('only_available', openapi.IN_QUERY, description="Solo stock disponible", type=openapi.TYPE_BOOLEAN, default=True),
            openapi.Parameter('include_expired', openapi.IN_QUERY, description="Incluir lotes vencidos", type=openapi.TYPE_BOOLEAN, default=False),
        ],
        responses={
            200: LocationBatchStockSerializer,
            400: "Parámetro location requerido",
            404: "Ubicación no encontrada"
        }
    )
    @action(detail=False, methods=['get'])
    def location_batch_stock(self, request):
        """
        Obtiene todos los productos con lotes en una ubicación específica.
        
        Parámetros requeridos:
        - location: ID de la ubicación
        
        Filtros opcionales:
        - product: ID del producto específico
        - product_name: búsqueda por nombre
        - batch_number: búsqueda por número de lote
        - only_available: solo stock disponible (default: true)
        - include_expired: incluir lotes vencidos (default: false)
        """
        location_id = request.query_params.get('location')
        
        if not location_id:
            return Response(
                {'error': 'El parámetro location es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que la ubicación existe
        try:
            location = Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            return Response(
                {'error': 'Ubicación no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Parámetros de filtro
        product_id = request.query_params.get('product')
        product_name = request.query_params.get('product_name')
        batch_number = request.query_params.get('batch_number')
        only_available = request.query_params.get('only_available', 'true').lower() == 'true'
        include_expired = request.query_params.get('include_expired', 'false').lower() == 'true'
        
        # Construir query base
        stock_query = InventoryStock.objects.filter(
            location=location,
            batch__isnull=False  # Solo productos con lotes
        ).select_related('product', 'batch')
        
        if only_available:
            stock_query = stock_query.filter(quantity__gt=0)
        
        if not include_expired:
            from django.utils import timezone
            stock_query = stock_query.filter(batch__expiry_date__gte=timezone.now().date())
        
        # Aplicar filtros
        if product_id:
            stock_query = stock_query.filter(product_id=product_id)
        if product_name:
            stock_query = stock_query.filter(product__name__icontains=product_name)
        if batch_number:
            stock_query = stock_query.filter(batch__batch_number__icontains=batch_number)
        
        # Agrupar por producto
        products_dict = {}
        
        for stock in stock_query:
            product_id = stock.product.id
            
            if product_id not in products_dict:
                products_dict[product_id] = {
                    'product_id': product_id,
                    'product_name': stock.product.name,
                    'product_sku': stock.product.sku,
                    'product_unit': stock.product.unit,
                    'requires_batch_control': stock.product.requires_batch_control,
                    'batches': [],
                    'total_quantity': 0
                }
            
            # Añadir lote
            products_dict[product_id]['batches'].append({
                'batch_id': stock.batch.id,
                'batch_number': stock.batch.batch_number,
                'manufacturing_date': stock.batch.manufacturing_date,
                'expiry_date': stock.batch.expiry_date,
                'days_to_expiry': stock.batch.days_to_expiry,
                'is_expired': stock.batch.is_expired,
                'quantity': stock.quantity,
                'last_updated': stock.last_updated
            })
            products_dict[product_id]['total_quantity'] += stock.quantity
        
        # Ordenar productos por nombre y lotes por fecha de vencimiento
        products_list = list(products_dict.values())
        products_list.sort(key=lambda x: x['product_name'])
        
        for product in products_list:
            product['batches'].sort(key=lambda x: x['expiry_date'] if x['expiry_date'] else timezone.now().date())
        
        result = {
            'location_id': location.id,
            'location_name': location.name,
            'location_type': location.type,
            'products': products_list
        }
        
        serializer = LocationBatchStockSerializer(result)
        return Response(serializer.data)


class InventoryMovementViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar movimientos de inventario."""
    
    queryset = InventoryMovement.objects.select_related(
        'product', 'location', 'user'
    ).all()
    serializer_class = InventoryMovementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = InventoryMovementFilter
    search_fields = ['product__name', 'product__sku', 'location__name', 'notes']
    ordering_fields = ['occurred_at', 'quantity']
    ordering = ['-occurred_at']

    @swagger_auto_schema(
        operation_description="Registrar un movimiento de inventario (entrada o salida)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['product', 'location', 'movement_type', 'quantity'],
            properties={
                'product': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del producto"),
                'location': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la ubicación de origen"),
                'destination_location': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la ubicación de destino (requerido para transferencias)"),
                'movement_type': openapi.Schema(type=openapi.TYPE_STRING, enum=['in', 'out'], description="Tipo de movimiento"),
                'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, description="Cantidad (positiva)"),
                'status': openapi.Schema(type=openapi.TYPE_STRING, enum=['pending', 'completed'], description="Estado inicial (opcional, por defecto 'completed')"),
                'is_internal_transfer': openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Marcar si es una transferencia interna (opcional)"),
                'expiry_date': openapi.Schema(type=openapi.TYPE_STRING, format='date', description="Fecha de vencimiento (opcional)"),
                'notes': openapi.Schema(type=openapi.TYPE_STRING, description="Notas adicionales (opcional)"),
            }
        ),
        responses={
            201: InventoryMovementSerializer,
            400: "Datos inválidos"
        }
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Obtener historial de movimientos con filtros",
        manual_parameters=[
            openapi.Parameter('movement_type', openapi.IN_QUERY, description="Tipo de movimiento (in/out)", type=openapi.TYPE_STRING),
            openapi.Parameter('status', openapi.IN_QUERY, description="Estado del movimiento (pending, completed, cancelled)", type=openapi.TYPE_STRING),
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de ubicación de origen", type=openapi.TYPE_INTEGER),
            openapi.Parameter('destination_location', openapi.IN_QUERY, description="ID de ubicación de destino", type=openapi.TYPE_INTEGER),
            openapi.Parameter('product', openapi.IN_QUERY, description="ID de producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('date_from', openapi.IN_QUERY, description="Fecha desde (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('date_to', openapi.IN_QUERY, description="Fecha hasta (YYYY-MM-DD)", type=openapi.TYPE_STRING),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """
        Sobrescribe el queryset para optimizar las consultas y aplicar filtros.
        - Usar `select_related` para reducir consultas a `product`, `location` y `user`.
        - Usar `prefetch_related` para el movimiento compuesto relacionado.
        - Aplicar filtros personalizados desde los query params.
        """
        queryset = super().get_queryset()
        
        # Optimización de consultas
        queryset = queryset.select_related(
            'product__category', 'location', 'user', 'batch'
        )
        
        # Optimizar la consulta para obtener el producto relacionado si es un movimiento compuesto
        queryset = queryset.prefetch_related('related_composite_movement__product')
        
        return queryset

    @swagger_auto_schema(
        method='post',
        operation_summary="Marcar un movimiento como 'Completado'",
        operation_description="Cambia el estado de un movimiento a 'completado', lo que afecta el stock.",
        responses={
            200: InventoryMovementSerializer,
            404: "Movimiento no encontrado"
        }
    )
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        movement = self.get_object()
        movement.status = 'completed'
        movement.save()
        serializer = self.get_serializer(movement)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='post',
        operation_summary="Marcar un movimiento como 'Cancelado'",
        operation_description="Cambia el estado de un movimiento a 'cancelado', revirtiendo el efecto en el stock si fue completado.",
        responses={
            200: InventoryMovementSerializer,
            404: "Movimiento no encontrado"
        }
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        movement = self.get_object()
        movement.status = 'cancelled'
        movement.save()
        serializer = self.get_serializer(movement)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_description="Obtener alertas de stock bajo o agotado",
        manual_parameters=[
            openapi.Parameter('min_stock', openapi.IN_QUERY, description="Umbral de stock mínimo (default: 10)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location', openapi.IN_QUERY, description="Filtrar por ubicación", type=openapi.TYPE_INTEGER),
        ],
        responses={200: StockAlertSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def stock_alerts(self, request):
        """Endpoint para obtener alertas de stock bajo."""
        
        min_stock = int(request.query_params.get('min_stock', 10))
        location_id = request.query_params.get('location')
        
        queryset = InventoryStock.objects.select_related('product', 'location')
        
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        
        # Productos con stock bajo o agotado
        low_stock = queryset.filter(quantity__lte=min_stock, quantity__gt=0)
        out_of_stock = queryset.filter(quantity=0)
        
        alerts = []
        
        # Alertas de stock bajo
        for stock in low_stock:
            alerts.append({
                'product_id': stock.product.id,
                'product_name': stock.product.name,
                'product_sku': stock.product.sku,
                'location_id': stock.location.id,
                'location_name': stock.location.name,
                'current_quantity': stock.quantity,
                'alert_type': 'low_stock'
            })
        
        # Alertas de productos agotados
        for stock in out_of_stock:
            alerts.append({
                'product_id': stock.product.id,
                'product_name': stock.product.name,
                'product_sku': stock.product.sku,
                'location_id': stock.location.id,
                'location_name': stock.location.name,
                'current_quantity': stock.quantity,
                'alert_type': 'out_of_stock'
            })
        
        serializer = StockAlertSerializer(alerts, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_description="Obtener alertas de productos próximos a vencer",
        manual_parameters=[
            openapi.Parameter('days_ahead', openapi.IN_QUERY, description="Días hacia adelante para alertas (default: 30)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location', openapi.IN_QUERY, description="Filtrar por ubicación", type=openapi.TYPE_INTEGER),
        ],
        responses={200: ExpiryAlertSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def expiry_alerts(self, request):
        """
        Obtiene alertas de productos próximos a vencer.
        """
        days_ahead = int(request.query_params.get('days_ahead', 30))
        location = request.query_params.get('location')
        
        from datetime import date, timedelta
        from django.utils import timezone
        
        expiry_threshold = timezone.now().date() + timedelta(days=days_ahead)
        
        # Obtener lotes próximos a vencer con stock disponible
        expiring_stock = InventoryStock.objects.filter(
            batch__expiry_date__lte=expiry_threshold,
            batch__expiry_date__gte=timezone.now().date(),
            quantity__gt=0
        ).select_related('product', 'location', 'batch')
        
        if location:
            expiring_stock = expiring_stock.filter(location_id=location)
        
        alerts = []
        for stock in expiring_stock:
            alerts.append({
                'product_id': stock.product.id,
                'product_name': stock.product.name,
                'product_sku': stock.product.sku,
                'location_id': stock.location.id,
                'location_name': stock.location.name,
                'batch_id': stock.batch.id,
                'batch_number': stock.batch.batch_number,
                'expiry_date': stock.batch.expiry_date,
                'days_to_expiry': stock.batch.days_to_expiry,
                'quantity': stock.quantity
            })
        
        serializer = ExpiryAlertSerializer(alerts, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='post',
        operation_description="Desarmar un producto compuesto en sus componentes",
        request_body=CompositeBreakdownSerializer,
        responses={200: "Desarmado exitoso", 400: "Error en la operación"}
    )
    @action(detail=False, methods=['post'])
    def breakdown_composite(self, request):
        """
        Desarma un producto compuesto en sus componentes individuales.
        
        Esto permite convertir cajas en unidades individuales, por ejemplo:
        1 caja de 10 blisters -> 10 blisters individuales
        """
        serializer = CompositeBreakdownSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            composite_product = Product.objects.get(id=serializer.validated_data['composite_product'])
            location = Location.objects.get(id=serializer.validated_data['location'])
            quantity = serializer.validated_data['quantity']
            notes = serializer.validated_data.get('notes', '')
            
            # Crear el movimiento de desarmado
            movement = InventoryMovement.create_composite_breakdown(
                composite_product=composite_product,
                location=location,
                quantity=quantity,
                user=request.user,
                notes=notes
            )
            
            return Response({
                'message': f'Se desarmaron {quantity} unidades de {composite_product.name}',
                'movement_id': movement.id,
                'components_affected': [
                    {
                        'product': comp.component_product.name,
                        'quantity_added': quantity * comp.quantity
                    }
                    for comp in composite_product.get_components()
                ]
            })
            
        except Product.DoesNotExist:
            return Response(
                {'error': 'Producto compuesto no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Location.DoesNotExist:
            return Response(
                {'error': 'Ubicación no encontrada'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        method='get',
        operation_description="Obtener stock de productos próximos a vencer por ubicación",
        manual_parameters=[
            openapi.Parameter('days_ahead', openapi.IN_QUERY, description="Días hacia adelante para alertas (default: 30)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location', openapi.IN_QUERY, description="Filtrar por ubicación", type=openapi.TYPE_INTEGER),
        ],
        responses={200: InventoryStockSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def expiring_stock(self, request):
        """
        Obtiene el stock de productos que están próximos a vencer.
        Útil para generar reportes de productos a sacar a la venta.
        """
        days_ahead = int(request.query_params.get('days_ahead', 30))
        location = request.query_params.get('location')
        
        from datetime import date, timedelta
        from django.utils import timezone
        
        expiry_threshold = timezone.now().date() + timedelta(days=days_ahead)
        
        # Obtener stock con lotes próximos a vencer
        queryset = self.get_queryset().filter(
            batch__expiry_date__lte=expiry_threshold,
            batch__expiry_date__gte=timezone.now().date(),
            quantity__gt=0
        ).order_by('batch__expiry_date')
        
        if location:
            queryset = queryset.filter(location_id=location)
        
        serializer = InventoryStockSerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_description="Obtener stock agrupado por lotes (FIFO)",
        manual_parameters=[
            openapi.Parameter('product', openapi.IN_QUERY, description="ID del producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de la ubicación", type=openapi.TYPE_INTEGER),
        ],
        responses={200: InventoryStockSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def by_batches(self, request):
        """
        Obtiene el stock organizado por lotes en orden FIFO.
        Útil para saber qué lotes usar primero en ventas.
        """
        product_id = request.query_params.get('product')
        location_id = request.query_params.get('location')
        
        queryset = self.get_queryset().filter(
            batch__isnull=False,
            quantity__gt=0
        ).order_by('batch__expiry_date')
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        
        serializer = InventoryStockSerializer(queryset, many=True)
        return Response(serializer.data)
