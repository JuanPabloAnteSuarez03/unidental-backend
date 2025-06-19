from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Delivery
from .serializers import (
    DeliveryListSerializer, DeliveryDetailSerializer, DeliveryCreateSerializer,
    DeliveryUpdateSerializer, DeliveryStatusUpdateSerializer, DeliveryStatsSerializer,
    LocationDeliverySummarySerializer
)
from .filters import DeliveryFilter
from inventory.models import Location


class DeliveryViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar entregas y domicilios - OPTIMIZADO.
    
    Proporciona operaciones CRUD completas para entregas, así como acciones personalizadas
    para actualizar estados, obtener estadísticas y gestionar el seguimiento de envíos.
    """
    
    # 🚀 OPTIMIZACIÓN: Agregar más relaciones y prefetch para items de venta
    queryset = Delivery.objects.select_related(
        'sale__customer', 
        'sale__location',  # Agregar location de la venta
        'origin_location', 
        'dest_location'
    ).prefetch_related(
        'sale__items__product'  # Prefetch items de la venta con sus productos
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DeliveryFilter
    search_fields = [
        'sale__customer__name', 'sale__customer__email', 
        'origin_location__name', 'dest_location__name'
    ]
    ordering_fields = [
        'id', 'created_at', 'shipped_at', 'delivered_at', 
        'status', 'sale__total_amount'
    ]
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Seleccionar serializer según la acción."""
        if self.action == 'list':
            return DeliveryListSerializer
        elif self.action == 'create':
            return DeliveryCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DeliveryUpdateSerializer
        elif self.action == 'update_status':
            return DeliveryStatusUpdateSerializer
        return DeliveryDetailSerializer
    
    @swagger_auto_schema(
        method='patch',
        request_body=DeliveryStatusUpdateSerializer,
        responses={
            200: DeliveryDetailSerializer,
            400: 'Error de validación',
            404: 'Entrega no encontrada'
        },
        operation_description="Actualizar solo el estado de una entrega específica"
    )
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Actualizar solo el estado de la entrega."""
        delivery = self.get_object()
        serializer = DeliveryStatusUpdateSerializer(
            delivery, data=request.data, partial=True
        )
        
        if serializer.is_valid():
            new_status = serializer.validated_data['status']
            
            try:
                if new_status == 'in_transit':
                    delivery.mark_as_shipped()
                elif new_status == 'delivered':
                    delivery.mark_as_delivered()
                else:
                    delivery.status = new_status
                    delivery.save()
                
                # Retornar datos actualizados
                response_serializer = DeliveryDetailSerializer(delivery)
                return Response(response_serializer.data)
                
            except Exception as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        method='post',
        responses={
            200: DeliveryDetailSerializer,
            400: 'Error de validación',
            404: 'Entrega no encontrada'
        },
        operation_description="Marcar una entrega como enviada"
    )
    @action(detail=True, methods=['post'])
    def mark_shipped(self, request, pk=None):
        """Marcar entrega como enviada."""
        delivery = self.get_object()
        
        try:
            delivery.mark_as_shipped()
            serializer = DeliveryDetailSerializer(delivery)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @swagger_auto_schema(
        method='post',
        responses={
            200: DeliveryDetailSerializer,
            400: 'Error de validación',
            404: 'Entrega no encontrada'
        },
        operation_description="Marcar una entrega como entregada"
    )
    @action(detail=True, methods=['post'])
    def mark_delivered(self, request, pk=None):
        """Marcar entrega como entregada."""
        delivery = self.get_object()
        
        try:
            delivery.mark_as_delivered()
            serializer = DeliveryDetailSerializer(delivery)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @swagger_auto_schema(
        method='get',
        responses={200: DeliveryStatsSerializer},
        operation_description="Obtener estadísticas generales de entregas",
        manual_parameters=[
            openapi.Parameter(
                'start_date', openapi.IN_QUERY,
                description="Fecha de inicio (YYYY-MM-DD)",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'end_date', openapi.IN_QUERY,
                description="Fecha de fin (YYYY-MM-DD)",
                type=openapi.TYPE_STRING
            ),
        ]
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Obtener estadísticas de entregas."""
        # Filtros de fecha opcionales
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=start_date)
            except ValueError:
                return Response(
                    {'error': 'Formato de start_date inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=end_date)
            except ValueError:
                return Response(
                    {'error': 'Formato de end_date inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Estadísticas básicas
        total_deliveries = queryset.count()
        pending_deliveries = queryset.filter(status='pending').count()
        in_transit_deliveries = queryset.filter(status='in_transit').count()
        delivered_deliveries = queryset.filter(status='delivered').count()
        
        # Tiempo promedio de entrega
        delivered_queryset = queryset.filter(
            status='delivered',
            shipped_at__isnull=False,
            delivered_at__isnull=False
        )
        
        avg_delivery_time = 0
        if delivered_queryset.exists():
            total_time = sum([
                (d.delivered_at - d.shipped_at).total_seconds() / 86400
                for d in delivered_queryset
            ])
            avg_delivery_time = total_time / delivered_queryset.count()
        
        # Estadísticas por ubicación
        deliveries_by_origin = {}
        deliveries_by_destination = {}
        
        for location in Location.objects.all():
            origin_count = queryset.filter(origin_location=location).count()
            dest_count = queryset.filter(dest_location=location).count()
            
            if origin_count > 0:
                deliveries_by_origin[location.name] = origin_count
            if dest_count > 0:
                deliveries_by_destination[location.name] = dest_count
        
        # Tendencias temporales
        now = timezone.now()
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        
        deliveries_this_month = queryset.filter(created_at__gte=this_month_start).count()
        deliveries_last_month = queryset.filter(
            created_at__gte=last_month_start,
            created_at__lt=this_month_start
        ).count()
        
        growth_rate = 0
        if deliveries_last_month > 0:
            growth_rate = ((deliveries_this_month - deliveries_last_month) / deliveries_last_month) * 100
        
        stats_data = {
            'total_deliveries': total_deliveries,
            'pending_deliveries': pending_deliveries,
            'in_transit_deliveries': in_transit_deliveries,
            'delivered_deliveries': delivered_deliveries,
            'average_delivery_time': round(avg_delivery_time, 2),
            'deliveries_by_origin': deliveries_by_origin,
            'deliveries_by_destination': deliveries_by_destination,
            'deliveries_this_month': deliveries_this_month,
            'deliveries_last_month': deliveries_last_month,
            'growth_rate': round(growth_rate, 2)
        }
        
        serializer = DeliveryStatsSerializer(stats_data)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        method='get',
        responses={200: LocationDeliverySummarySerializer(many=True)},
        operation_description="Obtener resumen de entregas por ubicación"
    )
    @action(detail=False, methods=['get'])
    def location_summary(self, request):
        """Obtener resumen de entregas por ubicación."""
        summaries = []
        
        for location in Location.objects.all():
            outgoing = self.get_queryset().filter(origin_location=location)
            incoming = self.get_queryset().filter(dest_location=location)
            
            summary = {
                'location_id': location.id,
                'location_name': location.name,
                'total_outgoing': outgoing.count(),
                'total_incoming': incoming.count(),
                'pending_outgoing': outgoing.filter(status='pending').count(),
                'pending_incoming': incoming.filter(status='pending').count(),
            }
            
            # Solo incluir ubicaciones con actividad
            if summary['total_outgoing'] > 0 or summary['total_incoming'] > 0:
                summaries.append(summary)
        
        serializer = LocationDeliverySummarySerializer(summaries, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        method='get',
        responses={200: DeliveryListSerializer(many=True)},
        operation_description="Obtener entregas atrasadas (más de 7 días sin entregar)"
    )
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Obtener entregas atrasadas."""
        overdue_date = timezone.now() - timedelta(days=7)
        
        overdue_deliveries = self.get_queryset().filter(
            Q(status__in=['pending', 'in_transit']) &
            Q(created_at__lt=overdue_date)
        )
        
        serializer = DeliveryListSerializer(overdue_deliveries, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        method='get',
        responses={200: DeliveryListSerializer(many=True)},
        operation_description="Obtener entregas por ruta (misma ubicación de origen)"
    )
    @action(detail=False, methods=['get'])
    def by_route(self, request):
        """Obtener entregas agrupadas por ruta."""
        origin_id = request.query_params.get('origin_location')
        
        if not origin_id:
            return Response(
                {'error': 'Se requiere el parámetro origin_location'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            deliveries = self.get_queryset().filter(
                origin_location_id=origin_id,
                status__in=['pending', 'in_transit']
            )
            
            serializer = DeliveryListSerializer(deliveries, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
