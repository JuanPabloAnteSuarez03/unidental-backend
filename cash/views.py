from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsAdmin
from django.db.models import Sum, Q
from .models import Cash, CashMovement, CashTransfer
from .serializers import (
    CashSerializer, CashMovementSerializer, CashMovementCreateSerializer,
    CashTransferSerializer, CashTransferCreateSerializer, CashSummarySerializer
)


class CashViewSet(viewsets.ModelViewSet):
    """API para gestionar cajas (Cash)."""
    queryset = Cash.objects.select_related('location').all()
    serializer_class = CashSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ['location', 'is_active']
    search_fields = ['location__name', 'location__address']
    ordering_fields = ['location__name', 'balance', 'created_at']
    ordering = ['location__name']

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Resumen general de todas las cajas."""
        try:
            total_balance = Cash.get_total_balance()
            active_cashes_count = Cash.objects.filter(is_active=True).count()
            
            # Manejar el filtro de fecha de manera segura
            since_param = request.query_params.get('since')
            if since_param:
                try:
                    from django.utils.dateparse import parse_datetime
                    since_date = parse_datetime(since_param)
                    if since_date:
                        recent_movements_count = CashMovement.objects.filter(created_at__gte=since_date).count()
                    else:
                        recent_movements_count = CashMovement.objects.count()
                except (ValueError, TypeError):
                    recent_movements_count = CashMovement.objects.count()
            else:
                recent_movements_count = CashMovement.objects.count()
            
            pending_transfers_count = CashTransfer.objects.filter(status='pending').count()
            
            data = {
                'total_balance': total_balance,
                'total_balance_formatted': f"${total_balance:,.2f}",
                'active_cashes_count': active_cashes_count,
                'recent_movements_count': recent_movements_count,
                'pending_transfers_count': pending_transfers_count,
            }
            serializer = CashSummarySerializer(data)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Error al obtener resumen: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CashMovementViewSet(viewsets.ModelViewSet):
    """API para movimientos de caja."""
    queryset = CashMovement.objects.select_related('cash', 'created_by', 'sale', 'purchase_order').all()
    permission_classes = [IsAdmin]
    filterset_fields = ['cash', 'movement_type', 'reference_type', 'status', 'created_by']
    search_fields = ['notes', 'cash__location__name', 'created_by__username']
    ordering_fields = ['created_at', 'amount', 'movement_type']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return CashMovementCreateSerializer
        return CashMovementSerializer

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Anula un movimiento de caja."""
        movement = self.get_object()
        user = request.user
        reason = request.data.get('reason', '')
        movement.cancel(user, reason)
        serializer = self.get_serializer(movement)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        """Reactiva un movimiento de caja anulado."""
        movement = self.get_object()
        user = request.user
        movement.reactivate(user)
        serializer = self.get_serializer(movement)
        return Response(serializer.data)


class CashTransferViewSet(viewsets.ModelViewSet):
    """API para transferencias de caja entre sedes."""
    queryset = CashTransfer.objects.select_related('origin_cash', 'destination_cash', 'created_by').all()
    permission_classes = [IsAdmin]
    filterset_fields = ['origin_cash', 'destination_cash', 'status', 'created_by']
    search_fields = ['notes', 'origin_cash__location__name', 'destination_cash__location__name', 'created_by__username']
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return CashTransferCreateSerializer
        return CashTransferSerializer

    @action(detail=True, methods=['post'], url_path='execute')
    def execute(self, request, pk=None):
        """Ejecuta una transferencia pendiente."""
        transfer = self.get_object()
        user = request.user
        transfer.execute_transfer(user)
        serializer = self.get_serializer(transfer)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancela una transferencia y anula los movimientos relacionados."""
        transfer = self.get_object()
        user = request.user
        reason = request.data.get('reason', '')
        transfer.cancel_transfer(user, reason)
        serializer = self.get_serializer(transfer)
        return Response(serializer.data)
