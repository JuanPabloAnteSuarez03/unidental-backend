from django.shortcuts import render
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Customer, Sale, SaleItem, Return, ReturnItem
from inventory.models import InventoryMovement
from .serializers import CustomerSerializer, SaleSerializer, SaleItemSerializer, ReturnSerializer, ReturnItemSerializer
from django.db.models import Sum, Count, F
from django.utils import timezone
from datetime import timedelta
from rest_framework.permissions import IsAuthenticated
from .filters import SaleFilter


class CustomerViewSet(viewsets.ModelViewSet):
    """Vista para gestionar clientes."""
    
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['name', 'email']
    search_fields = ['name', 'email', 'phone', 'notes']
    ordering_fields = ['name', 'created_at']

    @action(detail=True)
    def sales_history(self, request, pk=None):
        """Retorna el historial de ventas de un cliente específico."""
        customer = self.get_object()
        sales = customer.sales.all()
        serializer = SaleSerializer(sales, many=True)
        return Response(serializer.data)


class SaleViewSet(viewsets.ModelViewSet):
    """Vista para gestionar ventas."""
    
    queryset = Sale.objects.select_related('customer', 'location').prefetch_related('items__product').all()
    serializer_class = SaleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SaleFilter
    search_fields = ['customer__name', 'location__name']
    ordering_fields = ['sale_date', 'total_gross', 'total_net']

    @action(detail=False)
    def statistics(self, request):
        """
        Retorna estadísticas de ventas para un período específico.
        
        Parámetros de consulta:
        - days: Número de días hacia atrás para calcular estadísticas (default: 30)
        """
        # Obtener parámetros de rango de fechas
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        # Filtrar ventas dentro del rango de fechas
        sales = Sale.objects.filter(sale_date__gte=start_date)

        # Calcular estadísticas
        stats = {
            'total_sales': sales.count(),
            'total_revenue': sales.aggregate(Sum('total_net'))['total_net__sum'] or 0,
            'sales_by_type': sales.values('sale_type').annotate(
                count=Count('id'),
                revenue=Sum('total_net')
            ),
            'average_sale_value': (
                sales.aggregate(Sum('total_net'))['total_net__sum'] or 0
            ) / (sales.count() or 1)
        }

        return Response(stats)

    @action(detail=False)
    def today(self, request):
        """Retorna todas las ventas realizadas en el día actual."""
        today = timezone.localdate()
        sales = Sale.objects.filter(
            sale_date__date=today
        ).order_by('-sale_date')
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Estadísticas de ventas por sede",
        operation_description="Obtiene estadísticas de ventas agrupadas por sede/ubicación.",
        manual_parameters=[
            openapi.Parameter(
                'days', openapi.IN_QUERY,
                description="Número de días hacia atrás para calcular estadísticas",
                type=openapi.TYPE_INTEGER,
                default=30
            ),
        ],
        responses={
            200: openapi.Response(
                description="Estadísticas por sede obtenidas exitosamente",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'location__id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'location__name': openapi.Schema(type=openapi.TYPE_STRING),
                            'location__type': openapi.Schema(type=openapi.TYPE_STRING),
                            'total_sales': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'total_revenue': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'average_sale': openapi.Schema(type=openapi.TYPE_NUMBER),
                        }
                    )
                )
            )
        }
    )
    @action(detail=False)
    def by_location(self, request):
        """
        Retorna estadísticas de ventas agrupadas por sede.
        
        Parámetros de consulta:
        - days: Número de días hacia atrás para calcular estadísticas (default: 30)
        """
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        # Estadísticas por sede
        location_stats = Sale.objects.filter(
            sale_date__gte=start_date
        ).values(
            'location__id',
            'location__name',
            'location__type'
        ).annotate(
            total_sales=Count('id'),
            total_revenue=Sum('total_net'),
            average_sale=Sum('total_net') / Count('id')
        ).order_by('-total_revenue')

        # Renombrar campos para que coincidan con los tests
        formatted_stats = []
        for stat in location_stats:
            formatted_stats.append({
                'location_id': stat['location__id'],
                'location_name': stat['location__name'],
                'location_type': stat['location__type'],
                'total_sales': stat['total_sales'],
                'total_revenue': stat['total_revenue'] or 0,
                'average_sale': stat['average_sale'] or 0
            })

        return Response(formatted_stats)


class SaleItemViewSet(viewsets.ModelViewSet):
    """Vista para gestionar items de venta - OPTIMIZADO."""
    
    # 🚀 OPTIMIZACIÓN: Solo relaciones esenciales para listados rápidos
    queryset = SaleItem.objects.select_related(
        'sale',
        'product'
    ).all()
    serializer_class = SaleItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['sale', 'product']
    ordering_fields = ['quantity', 'unit_price']

    @action(detail=False)
    def top_products(self, request):
        """
        Retorna los productos más vendidos en un período específico.
        
        Parámetros de consulta:
        - days: Número de días hacia atrás para calcular estadísticas (default: 30)
        - limit: Número máximo de productos a retornar (default: 10)
        """
        # Obtener parámetros de consulta
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        start_date = timezone.now() - timedelta(days=days)

        # Obtener productos más vendidos
        top_products_data = SaleItem.objects.filter(
            sale__sale_date__gte=start_date
        ).values(
            'product__name',
            'product__id'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('unit_price'))
        ).order_by('-total_quantity')[:limit]

        # Reformatear datos para que coincidan con los tests
        formatted_products = []
        for product_data in top_products_data:
            formatted_products.append({
                'product': product_data['product__id'],
                'product_name': product_data['product__name'],
                'total_quantity': product_data['total_quantity'],
                'total_revenue': product_data['total_revenue'] or 0
            })

        return Response(formatted_products)


class ReturnViewSet(viewsets.ModelViewSet):
    """Vista para gestionar devoluciones - OPTIMIZADO."""
    
    # 🚀 OPTIMIZACIÓN: Solo relaciones esenciales para el listado
    queryset = Return.objects.select_related(
        'customer', 
        'location', 
        'original_sale'
    ).all()
    serializer_class = ReturnSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['reason', 'original_sale', 'customer', 'location']
    search_fields = ['customer__name', 'original_sale__id', 'notes']
    ordering_fields = ['return_date', 'total_amount']
    ordering = ['-return_date']

    def get_serializer_class(self):
        """Usar serializer liviano para listados, completo para detalles."""
        if self.action == 'list':
            from .serializers import ReturnSummarySerializer
            return ReturnSummarySerializer
        return self.serializer_class

    @swagger_auto_schema(
        operation_summary="Crear una nueva devolución",
        operation_description="Crea una nueva devolución con sus items. Actualiza automáticamente el inventario.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['original_sale', 'location', 'reason', 'items'],
            properties={
                'original_sale': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la venta original"),
                'customer': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del cliente (opcional, se toma de la venta)"),
                'location': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID de la ubicación donde se procesa la devolución"),
                'reason': openapi.Schema(type=openapi.TYPE_STRING, description="Motivo de la devolución", enum=['defective', 'wrong_item', 'customer_change', 'damaged', 'expired', 'other']),
                'notes': openapi.Schema(type=openapi.TYPE_STRING, description="Notas adicionales (opcional)"),
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'sale_item': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del item de venta original"),
                            'product': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID del producto"),
                            'quantity_returned': openapi.Schema(type=openapi.TYPE_INTEGER, description="Cantidad a devolver"),
                            'unit_price': openapi.Schema(type=openapi.TYPE_NUMBER, description="Precio unitario")
                        }
                    )
                )
            }
        ),
        responses={201: ReturnSerializer(), 400: "Bad Request"}
    )
    def create(self, request, *args, **kwargs):
        """Crea una nueva devolución."""
        return super().create(request, *args, **kwargs)

    @action(detail=False)
    def statistics(self, request):
        """
        Retorna estadísticas de devoluciones para un período específico.
        
        Parámetros de consulta:
        - days: Número de días hacia atrás para calcular estadísticas (default: 30)
        """
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        # Filtrar devoluciones dentro del rango de fechas
        returns = Return.objects.filter(return_date__gte=start_date)

        # Calcular estadísticas
        stats = {
            'total_returns': returns.count(),
            'total_amount_returned': returns.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'returns_by_reason': returns.values('reason').annotate(
                count=Count('id'),
                amount=Sum('total_amount')
            ),
            'average_return_value': (
                returns.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            ) / (returns.count() or 1)
        }

        return Response(stats)

    @action(detail=False)
    def today(self, request):
        """Retorna todas las devoluciones realizadas en el día actual."""
        today = timezone.now().date()
        returns = Return.objects.filter(
            return_date__date=today
        ).order_by('-return_date')
        serializer = self.get_serializer(returns, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Productos ya devueltos de una venta",
        operation_description="Obtiene información detallada sobre los productos ya devueltos de una venta específica.",
        manual_parameters=[
            openapi.Parameter(
                'sale_id', openapi.IN_QUERY,
                description="ID de la venta para consultar productos devueltos",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        responses={
            200: openapi.Response(
                description="Información de productos devueltos obtenida exitosamente",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'sale_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'sale_date': openapi.Schema(type=openapi.TYPE_STRING),
                        'customer_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'total_returned_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'returned_items': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'sale_item_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'product_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'product_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'product_sku': openapi.Schema(type=openapi.TYPE_STRING),
                                    'original_quantity': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'total_returned': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'remaining_quantity': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'returns_detail': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                'return_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                                'return_date': openapi.Schema(type=openapi.TYPE_STRING),
                                                'quantity_returned': openapi.Schema(type=openapi.TYPE_INTEGER),
                                                'reason': openapi.Schema(type=openapi.TYPE_STRING),
                                                'notes': openapi.Schema(type=openapi.TYPE_STRING),
                                            }
                                        )
                                    )
                                }
                            )
                        )
                    }
                )
            ),
            404: "Venta no encontrada"
        }
    )
    @action(detail=False, methods=['get'])
    def returned_items_by_sale(self, request):
        """
        Obtiene información detallada sobre los productos ya devueltos de una venta específica.
        
        Parámetros de consulta:
        - sale_id: ID de la venta para consultar productos devueltos
        """
        sale_id = request.query_params.get('sale_id')
        if not sale_id:
            return Response(
                {'error': 'El parámetro sale_id es requerido'}, 
                status=400
            )
        
        try:
            sale = Sale.objects.get(id=sale_id)
        except Sale.DoesNotExist:
            return Response(
                {'error': f'Venta con ID {sale_id} no encontrada'}, 
                status=404
            )
        
        # Obtener todos los items de la venta con información de devoluciones
        sale_items = SaleItem.objects.filter(sale=sale).select_related('product')
        
        returned_items_data = []
        total_returned_amount = 0
        
        for sale_item in sale_items:
            # Obtener todas las devoluciones de este item
            return_items = ReturnItem.objects.filter(
                sale_item=sale_item
            ).select_related('return_obj').order_by('return_obj__return_date')
            
            total_returned = sum(item.quantity_returned for item in return_items)
            remaining_quantity = sale_item.quantity - total_returned
            
            # Detalles de cada devolución
            returns_detail = []
            for return_item in return_items:
                returns_detail.append({
                    'return_id': return_item.return_obj.id,
                    'return_date': return_item.return_obj.return_date.isoformat(),
                    'quantity_returned': return_item.quantity_returned,
                    'reason': return_item.return_obj.reason,
                    'notes': return_item.return_obj.notes or '',
                })
            
            if total_returned > 0:  # Solo incluir items que han sido devueltos
                item_data = {
                    'sale_item_id': sale_item.id,
                    'product_id': sale_item.product.id,
                    'product_name': sale_item.product.name,
                    'product_sku': sale_item.product.sku,
                    'original_quantity': sale_item.quantity,
                    'total_returned': total_returned,
                    'remaining_quantity': remaining_quantity,
                    'returns_detail': returns_detail,
                }
                returned_items_data.append(item_data)
                total_returned_amount += total_returned * sale_item.unit_price
        
        response_data = {
            'sale_id': sale.id,
            'sale_date': sale.sale_date.isoformat(),
            'customer_name': sale.customer.name if sale.customer else 'N/A',
            'total_returned_amount': total_returned_amount,
            'returned_items': returned_items_data,
        }
        
        return Response(response_data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Resumen de productos devueltos",
        operation_description="Obtiene un resumen de todos los productos devueltos en un período específico.",
        manual_parameters=[
            openapi.Parameter(
                'days', openapi.IN_QUERY,
                description="Número de días hacia atrás para calcular estadísticas",
                type=openapi.TYPE_INTEGER,
                default=30
            ),
            openapi.Parameter(
                'limit', openapi.IN_QUERY,
                description="Número máximo de productos a retornar",
                type=openapi.TYPE_INTEGER,
                default=20
            ),
        ],
        responses={
            200: openapi.Response(
                description="Resumen de productos devueltos obtenido exitosamente",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'period_days': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_returns': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_returned_quantity': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total_returned_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'top_returned_products': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'product_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'product_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'product_sku': openapi.Schema(type=openapi.TYPE_STRING),
                                    'total_returned_quantity': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'total_returned_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                                    'return_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                                }
                            )
                        )
                    }
                )
            )
        }
    )
    @action(detail=False, methods=['get'])
    def returned_products_summary(self, request):
        """
        Obtiene un resumen de todos los productos devueltos en un período específico.
        
        Parámetros de consulta:
        - days: Número de días hacia atrás para calcular estadísticas (default: 30)
        - limit: Número máximo de productos a retornar (default: 20)
        """
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 20))
        start_date = timezone.now() - timedelta(days=days)
        
        # Obtener todas las devoluciones en el período
        returns = Return.objects.filter(return_date__gte=start_date)
        
        # Calcular estadísticas generales
        total_returns = returns.count()
        total_returned_amount = returns.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Obtener productos más devueltos
        top_returned_products = ReturnItem.objects.filter(
            return_obj__return_date__gte=start_date
        ).values(
            'product__id',
            'product__name',
            'product__sku'
        ).annotate(
            total_returned_quantity=Sum('quantity_returned'),
            total_returned_amount=Sum(F('quantity_returned') * F('unit_price')),
            return_count=Count('return_obj', distinct=True)
        ).order_by('-total_returned_quantity')[:limit]
        
        # Reformatear datos
        formatted_products = []
        total_returned_quantity = 0
        
        for product_data in top_returned_products:
            formatted_products.append({
                'product_id': product_data['product__id'],
                'product_name': product_data['product__name'],
                'product_sku': product_data['product__sku'],
                'total_returned_quantity': product_data['total_returned_quantity'],
                'total_returned_amount': product_data['total_returned_amount'] or 0,
                'return_count': product_data['return_count'],
            })
            total_returned_quantity += product_data['total_returned_quantity']
        
        response_data = {
            'period_days': days,
            'total_returns': total_returns,
            'total_returned_quantity': total_returned_quantity,
            'total_returned_amount': total_returned_amount,
            'top_returned_products': formatted_products,
        }
        
        return Response(response_data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Estadísticas de devoluciones por sede",
        operation_description="Obtiene estadísticas de devoluciones agrupadas por sede/ubicación.",
        manual_parameters=[
            openapi.Parameter(
                'days', openapi.IN_QUERY,
                description="Número de días hacia atrás para calcular estadísticas",
                type=openapi.TYPE_INTEGER,
                default=30
            ),
        ],
        responses={
            200: openapi.Response(
                description="Estadísticas por sede obtenidas exitosamente",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'location_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'location_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'location_type': openapi.Schema(type=openapi.TYPE_STRING),
                            'total_returns': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'total_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'average_return': openapi.Schema(type=openapi.TYPE_NUMBER),
                        }
                    )
                )
            )
        }
    )
    @action(detail=False, methods=['get'])
    def by_location(self, request):
        """Devuelve estadísticas de devoluciones agrupadas por ubicación."""
        stats = Return.objects.values(
            'location__name'
        ).annotate(
            total_returns=Count('id'),
            total_returned_amount=Sum('items__subtotal')
        ).order_by('-total_returned_amount')
        
        return Response(stats)


class ReturnItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar los items de una devolución - OPTIMIZADO.
    Permite ver, crear, editar y eliminar items de devolución.
    """
    # 🚀 OPTIMIZACIÓN: Precargar todas las relaciones necesarias para evitar N+1
    queryset = ReturnItem.objects.select_related(
        'return_obj',
        'product__category',  # Precargar categoría del producto
        'sale_item__sale'     # Precargar venta del item original
    ).all()
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['return_obj', 'product']

    def get_serializer_class(self):
        """Usar serializer liviano para listados."""
        if self.action == 'list':
            from .serializers import ReturnItemSummarySerializer
            return ReturnItemSummarySerializer
        return ReturnItemSerializer

    @action(detail=False, methods=['get'])
    def top_returned_products(self, request):
        """
        Devuelve un ranking de los productos más devueltos.
        
        Parámetros de consulta:
        - days: Número de días hacia atrás para calcular estadísticas (default: 30)
        - limit: Número máximo de productos a retornar (default: 10)
        """
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        start_date = timezone.now() - timedelta(days=days)

        # Obtener productos más devueltos
        top_returned = ReturnItem.objects.filter(
            return_obj__return_date__gte=start_date
        ).values(
            'product__name',
            'product__id'
        ).annotate(
            total_quantity_returned=Sum('quantity_returned'),
            total_amount_returned=Sum(F('quantity_returned') * F('unit_price'))
        ).order_by('-total_quantity_returned')[:limit]

        # Formatear datos
        formatted_products = []
        for product_data in top_returned:
            formatted_products.append({
                'product': product_data['product__id'],
                'product_name': product_data['product__name'],
                'total_quantity_returned': product_data['total_quantity_returned'],
                'total_amount_returned': product_data['total_amount_returned'] or 0
            })

        return Response(formatted_products)
