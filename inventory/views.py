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
    CompositeBreakdownSerializer
)
from .filters import LocationFilter, InventoryStockFilter, InventoryMovementFilter
from catalogs.models import Product


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
                'location': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la ubicación"),
                'movement_type': openapi.Schema(type=openapi.TYPE_STRING, enum=['in', 'out'], description="Tipo de movimiento"),
                'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, description="Cantidad (positiva)"),
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
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de ubicación", type=openapi.TYPE_INTEGER),
            openapi.Parameter('product', openapi.IN_QUERY, description="ID de producto", type=openapi.TYPE_INTEGER),
            openapi.Parameter('date_from', openapi.IN_QUERY, description="Fecha desde (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('date_to', openapi.IN_QUERY, description="Fecha hasta (YYYY-MM-DD)", type=openapi.TYPE_STRING),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros por fecha
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(occurred_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(occurred_at__date__lte=date_to)
        
        return queryset

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
