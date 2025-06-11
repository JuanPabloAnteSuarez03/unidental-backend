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
    StockAlertSerializer, ExpiryAlertSerializer, StockSummarySerializer
)
from catalogs.models import Product


class LocationViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar ubicaciones (sedes y bodegas)."""
    
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type']
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
    filterset_fields = ['location', 'location__type']
    search_fields = ['product__name', 'product__sku', 'location__name']
    ordering_fields = ['quantity', 'last_updated', 'product__name']
    ordering = ['product__name']

    @swagger_auto_schema(
        operation_description="Obtener lista de stock con filtros por ubicación y producto",
        manual_parameters=[
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de ubicación", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location__type', openapi.IN_QUERY, description="Tipo de ubicación (sede/bodega)", type=openapi.TYPE_STRING),
            openapi.Parameter('search', openapi.IN_QUERY, description="Buscar por producto o ubicación", type=openapi.TYPE_STRING),
            openapi.Parameter('min_quantity', openapi.IN_QUERY, description="Cantidad mínima", type=openapi.TYPE_INTEGER),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtro por cantidad mínima
        min_quantity = self.request.query_params.get('min_quantity')
        if min_quantity is not None:
            try:
                queryset = queryset.filter(quantity__gte=int(min_quantity))
            except ValueError:
                pass
        
        return queryset

    @swagger_auto_schema(
        method='get',
        operation_description="Obtener resumen de stock por producto (suma de todas las ubicaciones)",
        responses={200: StockSummarySerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Endpoint para obtener resumen de stock por producto."""
        
        # Agrupar por producto y sumar cantidades
        stock_data = InventoryStock.objects.select_related('product', 'location').values(
            'product__id', 'product__name', 'product__sku', 'product__unit'
        ).annotate(
            total_quantity=Sum('quantity')
        ).filter(total_quantity__gt=0).order_by('product__name')
        
        result = []
        for item in stock_data:
            # Obtener ubicaciones con stock para este producto
            locations_data = InventoryStock.objects.filter(
                product_id=item['product__id'],
                quantity__gt=0
            ).select_related('location').values(
                'location__id', 'location__name', 'location__type', 'quantity'
            )
            
            result.append({
                'product_id': item['product__id'],
                'product_name': item['product__name'],
                'product_sku': item['product__sku'],
                'product_unit': item['product__unit'],
                'total_quantity': item['total_quantity'],
                'locations': list(locations_data)
            })
        
        serializer = StockSummarySerializer(result, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Obtener todo el stock sin paginación",
        operation_description="Devuelve todo el stock de inventario sin paginación. Útil para cargar listas completas en el frontend.",
        manual_parameters=[
            openapi.Parameter('location', openapi.IN_QUERY, description="ID de ubicación", type=openapi.TYPE_INTEGER),
            openapi.Parameter('location__type', openapi.IN_QUERY, description="Tipo de ubicación (sede/bodega)", type=openapi.TYPE_STRING),
            openapi.Parameter('search', openapi.IN_QUERY, description="Buscar por producto o ubicación", type=openapi.TYPE_STRING),
            openapi.Parameter('min_quantity', openapi.IN_QUERY, description="Cantidad mínima", type=openapi.TYPE_INTEGER),
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
        - ?location__type=tipo (Tipo de ubicación: sede/bodega)
        - ?search=texto (búsqueda por producto o ubicación)
        - ?min_quantity=cantidad (cantidad mínima)
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
    filterset_fields = ['movement_type', 'location', 'product']
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
        """Endpoint para obtener alertas de productos próximos a vencer."""
        
        days_ahead = int(request.query_params.get('days_ahead', 30))
        location_id = request.query_params.get('location')
        
        alert_date = timezone.now().date() + timedelta(days=days_ahead)
        
        queryset = InventoryMovement.objects.filter(
            movement_type='in',
            expiry_date__isnull=False,
            expiry_date__lte=alert_date,
            expiry_date__gte=timezone.now().date()
        ).select_related('product', 'location')
        
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        
        alerts = []
        for movement in queryset:
            days_to_expiry = (movement.expiry_date - timezone.now().date()).days
            alerts.append({
                'product_id': movement.product.id,
                'product_name': movement.product.name,
                'product_sku': movement.product.sku,
                'location_id': movement.location.id,
                'location_name': movement.location.name,
                'expiry_date': movement.expiry_date,
                'days_to_expiry': days_to_expiry,
                'quantity': movement.quantity
            })
        
        # Ordenar por días hasta vencimiento
        alerts.sort(key=lambda x: x['days_to_expiry'])
        
        serializer = ExpiryAlertSerializer(alerts, many=True)
        return Response(serializer.data)
