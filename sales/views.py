from django.shortcuts import render
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
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
    
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['sale_type', 'should_invoice', 'customer']
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
        top_products = SaleItem.objects.filter(
            sale__sale_date__gte=start_date
        ).values(
            'product__name',
            'product__id'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('unit_price'))
        ).order_by('-total_quantity')[:limit]

        return Response(top_products)
