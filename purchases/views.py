from django.shortcuts import render
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from django.db.models import Q, F, Sum, Case, When
from django.db import transaction

from .models import PurchaseOrder, PurchaseOrderItem
from .serializers import (
    PurchaseOrderSerializer,
    PurchaseOrderDetailSerializer,
    PurchaseOrderCreateSerializer,
    PurchaseOrderItemSerializer,
    PurchaseOrderItemCreateSerializer,
    PurchaseOrderItemForOrderCreateSerializer,
    ProductAlternativesSerializer,
    AlternativeBrandSerializer
)
from .filters import PurchaseOrderFilter, PurchaseOrderItemFilter
from suppliers.models import PurchaseOption
from catalogs.models import Product


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar órdenes de compra.
    
    Permite operaciones CRUD completas sobre las órdenes de compra del sistema,
    incluyendo funcionalidades para cancelar y marcar como recibidas.
    """
    queryset = PurchaseOrder.objects.select_related(
        'supplier', 'destination', 'created_by'
    ).prefetch_related('items__purchase_option__product').all()
    
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = PurchaseOrderFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        'supplier__name', 
        'destination__name', 
        'notes', 
        'created_by__username'
    ]
    ordering_fields = [
        'order_date', 
        'status', 
        'created_at', 
        'updated_at',
        'supplier__name',
        'destination__name'
    ]
    ordering = ['-order_date', '-created_at']

    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción."""
        if self.action == 'create':
            return PurchaseOrderCreateSerializer
        elif self.action == 'retrieve':
            return PurchaseOrderDetailSerializer
        return PurchaseOrderSerializer

    @swagger_auto_schema(
        operation_summary="Listar órdenes de compra",
        operation_description="Obtiene una lista paginada de todas las órdenes de compra del sistema con filtros avanzados.",
        manual_parameters=[
            openapi.Parameter('status', openapi.IN_QUERY, description="Filtrar por estado (pending/received/canceled)", type=openapi.TYPE_STRING),
            openapi.Parameter('supplier', openapi.IN_QUERY, description="ID del proveedor", type=openapi.TYPE_INTEGER),
            openapi.Parameter('destination', openapi.IN_QUERY, description="ID del destino", type=openapi.TYPE_INTEGER),
            openapi.Parameter('order_date_from', openapi.IN_QUERY, description="Fecha desde (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('order_date_to', openapi.IN_QUERY, description="Fecha hasta (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('total_amount_min', openapi.IN_QUERY, description="Monto mínimo", type=openapi.TYPE_NUMBER),
            openapi.Parameter('total_amount_max', openapi.IN_QUERY, description="Monto máximo", type=openapi.TYPE_NUMBER),
            openapi.Parameter('search', openapi.IN_QUERY, description="Buscar en proveedor, destino, notas", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Lista de órdenes obtenida exitosamente",
                schema=PurchaseOrderSerializer(many=True)
            )
        }
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Crear orden de compra",
        operation_description="Crea una nueva orden de compra con sus items asociados.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['supplier', 'destination', 'items'],
            properties={
                'supplier': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del proveedor"),
                'destination': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del destino"),
                'order_date': openapi.Schema(type=openapi.TYPE_STRING, format='date', description="Fecha de la orden (opcional, por defecto hoy)"),
                'notes': openapi.Schema(type=openapi.TYPE_STRING, description="Notas adicionales (opcional)"),
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        required=['purchase_option', 'quantity_requested', 'unit_price'],
                        properties={
                            'purchase_option': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la opción de compra"),
                            'quantity_requested': openapi.Schema(type=openapi.TYPE_INTEGER, description="Cantidad solicitada"),
                            'unit_price': openapi.Schema(type=openapi.TYPE_NUMBER, description="Precio unitario"),
                        }
                    ),
                    min_items=1,
                    description="Lista de items de la orden"
                )
            },
            example={
                "supplier": 1,
                "destination": 2,
                "order_date": "2024-01-15",
                "notes": "Orden urgente para sede norte",
                "items": [
                    {
                        "purchase_option": 5,
                        "quantity_requested": 10,
                        "unit_price": 25000.00
                    },
                    {
                        "purchase_option": 8,
                        "quantity_requested": 5,
                        "unit_price": 45000.00
                    }
                ]
            }
        ),
        responses={
            201: openapi.Response(
                description="Orden creada exitosamente",
                schema=PurchaseOrderDetailSerializer
            ),
            400: openapi.Response(description="Datos inválidos")
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        # Devolver respuesta con el serializer detallado
        response_serializer = PurchaseOrderDetailSerializer(instance, context={'request': request})
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @swagger_auto_schema(
        operation_summary="Obtener orden de compra",
        operation_description="Obtiene los detalles completos de una orden de compra específica incluyendo todos sus items.",
        responses={
            200: openapi.Response(
                description="Detalles de la orden obtenidos exitosamente",
                schema=PurchaseOrderDetailSerializer
            ),
            404: openapi.Response(description="Orden no encontrada")
        }
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Actualizar orden de compra",
        operation_description="Actualiza una orden de compra. Solo se pueden actualizar órdenes en estado 'pending'.",
        request_body=PurchaseOrderSerializer,
        responses={
            200: openapi.Response(
                description="Orden actualizada exitosamente",
                schema=PurchaseOrderSerializer
            ),
            400: openapi.Response(description="Datos inválidos o orden no modificable"),
            404: openapi.Response(description="Orden no encontrada")
        }
    )
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.can_be_modified():
            return Response(
                {'detail': f'No se puede modificar una orden en estado {instance.get_status_display()}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Actualizar parcialmente orden de compra",
        operation_description="Actualiza parcialmente una orden de compra. Solo se pueden actualizar órdenes en estado 'pending'.",
        request_body=PurchaseOrderSerializer,
        responses={
            200: openapi.Response(
                description="Orden actualizada exitosamente",
                schema=PurchaseOrderSerializer
            ),
            400: openapi.Response(description="Datos inválidos o orden no modificable"),
            404: openapi.Response(description="Orden no encontrada")
        }
    )
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.can_be_modified():
            return Response(
                {'detail': f'No se puede modificar una orden en estado {instance.get_status_display()}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Eliminar orden de compra",
        operation_description="Elimina una orden de compra. Solo se pueden eliminar órdenes en estado 'pending'.",
        responses={
            204: openapi.Response(description="Orden eliminada exitosamente"),
            400: openapi.Response(description="Orden no puede ser eliminada"),
            404: openapi.Response(description="Orden no encontrada")
        }
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.can_be_modified():
            return Response(
                {'detail': f'No se puede eliminar una orden en estado {instance.get_status_display()}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        method='post',
        operation_summary="Cancelar orden de compra",
        operation_description="Cambia el estado de una orden de 'pending' a 'canceled'.",
        responses={
            200: openapi.Response(
                description="Orden cancelada exitosamente",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Orden cancelada exitosamente"),
                        'status': openapi.Schema(type=openapi.TYPE_STRING, example="canceled")
                    }
                )
            ),
            400: openapi.Response(description="La orden no puede ser cancelada")
        }
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancela una orden de compra."""
        purchase_order = self.get_object()
        
        if purchase_order.cancel_order():
            return Response({
                'detail': 'Orden cancelada exitosamente.',
                'status': purchase_order.status
            })
        else:
            return Response(
                {'detail': f'No se puede cancelar una orden en estado {purchase_order.get_status_display()}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        method='post',
        operation_summary="Marcar orden como recibida",
        operation_description="Cambia el estado de una orden de 'pending' a 'received'.",
        responses={
            200: openapi.Response(
                description="Orden marcada como recibida exitosamente",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Orden marcada como recibida exitosamente"),
                        'status': openapi.Schema(type=openapi.TYPE_STRING, example="received")
                    }
                )
            ),
            400: openapi.Response(description="La orden no puede ser marcada como recibida")
        }
    )
    @action(detail=True, methods=['post'])
    def mark_received(self, request, pk=None):
        """Marca una orden como recibida."""
        purchase_order = self.get_object()
        
        if purchase_order.mark_as_received():
            return Response({
                'detail': 'Orden marcada como recibida exitosamente.',
                'status': purchase_order.status
            })
        else:
            return Response(
                {'detail': f'No se puede marcar como recibida una orden en estado {purchase_order.get_status_display()}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        method='get',
        operation_summary="Estadísticas de órdenes",
        operation_description="Obtiene estadísticas generales de las órdenes de compra.",
        responses={
            200: openapi.Response(
                description="Estadísticas obtenidas exitosamente",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'total_orders': openapi.Schema(type=openapi.TYPE_INTEGER, description="Total de órdenes"),
                        'pending_orders': openapi.Schema(type=openapi.TYPE_INTEGER, description="Órdenes pendientes"),
                        'received_orders': openapi.Schema(type=openapi.TYPE_INTEGER, description="Órdenes recibidas"),
                        'canceled_orders': openapi.Schema(type=openapi.TYPE_INTEGER, description="Órdenes canceladas"),
                        'total_amount_pending': openapi.Schema(type=openapi.TYPE_NUMBER, description="Monto total pendiente"),
                        'total_amount_received': openapi.Schema(type=openapi.TYPE_NUMBER, description="Monto total recibido"),
                    }
                )
            )
        }
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Obtiene estadísticas de las órdenes de compra."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Estadísticas básicas
        total_orders = queryset.count()
        pending_orders = queryset.filter(status='pending').count()
        received_orders = queryset.filter(status='received').count()
        canceled_orders = queryset.filter(status='canceled').count()
        
        # Montos por estado
        pending_amount = sum(order.total_amount for order in queryset.filter(status='pending'))
        received_amount = sum(order.total_amount for order in queryset.filter(status='received'))
        
        return Response({
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'received_orders': received_orders,
            'canceled_orders': canceled_orders,
            'total_amount_pending': pending_amount,
            'total_amount_received': received_amount,
        })


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar items de órdenes de compra.
    
    Permite operaciones CRUD sobre los items individuales de las órdenes.
    """
    queryset = PurchaseOrderItem.objects.select_related(
        'order__supplier',
        'order__destination',
        'purchase_option__product__category',
        'purchase_option__supplier'
    ).all()
    
    serializer_class = PurchaseOrderItemSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = PurchaseOrderItemFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        'purchase_option__product__name',
        'purchase_option__product__sku',
        'purchase_option__brand',
        'order__supplier__name'
    ]
    ordering_fields = [
        'quantity_requested',
        'unit_price',
        'created_at',
        'purchase_option__product__name'
    ]
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción."""
        if self.action == 'create':
            return PurchaseOrderItemCreateSerializer
        return PurchaseOrderItemSerializer

    @swagger_auto_schema(
        operation_summary="Listar items de órdenes",
        operation_description="Obtiene una lista paginada de todos los items de órdenes de compra.",
        manual_parameters=[
            openapi.Parameter('order', openapi.IN_QUERY, description="ID de la orden", type=openapi.TYPE_INTEGER),
            openapi.Parameter('order_status', openapi.IN_QUERY, description="Estado de la orden (pending/received/canceled)", type=openapi.TYPE_STRING),
            openapi.Parameter('product_name', openapi.IN_QUERY, description="Buscar por nombre del producto", type=openapi.TYPE_STRING),
            openapi.Parameter('product_sku', openapi.IN_QUERY, description="Buscar por SKU del producto", type=openapi.TYPE_STRING),
            openapi.Parameter('brand', openapi.IN_QUERY, description="Buscar por marca", type=openapi.TYPE_STRING),
            openapi.Parameter('quantity_min', openapi.IN_QUERY, description="Cantidad mínima", type=openapi.TYPE_INTEGER),
            openapi.Parameter('quantity_max', openapi.IN_QUERY, description="Cantidad máxima", type=openapi.TYPE_INTEGER),
            openapi.Parameter('unit_price_min', openapi.IN_QUERY, description="Precio mínimo", type=openapi.TYPE_NUMBER),
            openapi.Parameter('unit_price_max', openapi.IN_QUERY, description="Precio máximo", type=openapi.TYPE_NUMBER),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Personaliza la creación del item."""
        # Validar que la orden pueda ser modificada
        order = serializer.validated_data['order']
        if not order.can_be_modified():
            raise serializers.ValidationError(
                f'No se pueden agregar items a una orden en estado {order.get_status_display()}.'
            )
        serializer.save()

    def perform_update(self, serializer):
        """Personaliza la actualización del item."""
        # Validar que la orden pueda ser modificada
        if not serializer.instance.order.can_be_modified():
            raise serializers.ValidationError(
                f'No se pueden modificar items de una orden en estado {serializer.instance.order.get_status_display()}.'
            )
        serializer.save()

    def perform_destroy(self, instance):
        """Personaliza la eliminación del item."""
        # Validar que la orden pueda ser modificada
        if not instance.order.can_be_modified():
            raise serializers.ValidationError(
                f'No se pueden eliminar items de una orden en estado {instance.order.get_status_display()}.'
            )
        instance.delete()

    @swagger_auto_schema(
        method='get',
        operation_summary="Sugerir marcas alternativas",
        operation_description="Obtiene marcas alternativas disponibles para los productos en las órdenes de compra.",
        manual_parameters=[
            openapi.Parameter('supplier', openapi.IN_QUERY, description="ID del proveedor (opcional)", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response(
                description="Marcas alternativas obtenidas exitosamente",
                schema=ProductAlternativesSerializer(many=True)
            )
        }
    )
    @action(detail=False, methods=['get'])
    def alternative_brands(self, request):
        """
        Sugiere marcas alternativas para productos.
        Útil para encontrar opciones similares cuando un producto no está disponible.
        """
        supplier_id = request.query_params.get('supplier')
        
        # Base queryset de opciones de compra vigentes
        purchase_options = PurchaseOption.objects.filter(
            valid_from__lte=timezone.localdate()
        ).select_related('product', 'supplier')
        
        if supplier_id:
            purchase_options = purchase_options.filter(supplier_id=supplier_id)
        
        # Agrupar por producto
        products_with_alternatives = {}
        
        for option in purchase_options:
            product_id = option.product.id
            if product_id not in products_with_alternatives:
                products_with_alternatives[product_id] = {
                    'product_id': product_id,
                    'product_name': option.product.name,
                    'product_sku': option.product.sku,
                    'alternatives': []
                }
            
            products_with_alternatives[product_id]['alternatives'].append({
                'purchase_option_id': option.id,
                'supplier_name': option.supplier.name,
                'brand': option.brand,
                'purchase_price': option.purchase_price,
                'valid_from': option.valid_from,
                'valid_to': option.valid_to,
                'is_currently_valid': option.is_currently_valid()
            })
        
        # Filtrar solo productos que tienen más de una alternativa
        result = [
            data for data in products_with_alternatives.values()
            if len(data['alternatives']) > 1
        ]
        
        serializer = ProductAlternativesSerializer(result, many=True)
        return Response(serializer.data)
