from django.shortcuts import render
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Customer, Sale, SaleItem
from .serializers import CustomerSerializer, SaleSerializer, SaleItemSerializer
from django.db.models import Sum, Count, F
from django.utils import timezone
from datetime import timedelta


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
    filterset_fields = ['sale_type', 'should_invoice', 'customer', 'location']
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
        today = timezone.now().date()
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
    """Vista para gestionar items de venta."""
    
    queryset = SaleItem.objects.all()
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
