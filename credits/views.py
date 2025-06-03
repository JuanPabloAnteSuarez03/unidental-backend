from django.shortcuts import render
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Q, Count, Case, When, DecimalField
from django.utils import timezone
from datetime import date, timedelta

from .models import CreditAccount, CreditPayment
from .serializers import (
    CreditAccountSerializer, CreditPaymentSerializer, 
    CreateCreditAccountSerializer, DebtSummarySerializer
)
from sales.models import Customer


class CreditAccountViewSet(viewsets.ModelViewSet):
    """Vista para gestionar cuentas de crédito."""
    
    queryset = CreditAccount.objects.all()
    serializer_class = CreditAccountSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['sale__customer']  # Solo campos del modelo
    search_fields = ['sale__customer__name', 'sale__customer__email', 'sale__customer__phone']
    ordering_fields = ['created_at', 'due_date', 'remaining_amount', 'original_amount']

    def get_queryset(self):
        """Filtros adicionales por query params."""
        queryset = super().get_queryset()
        
        # Filtrar por estado de pago
        paid_status = self.request.query_params.get('paid_status')
        if paid_status == 'paid':
            queryset = queryset.filter(remaining_amount=0)
        elif paid_status == 'pending':
            queryset = queryset.filter(remaining_amount__gt=0)
        
        # Filtrar por estado de vencimiento
        overdue_status = self.request.query_params.get('overdue_status')
        if overdue_status == 'overdue':
            queryset = queryset.filter(
                due_date__lt=date.today(),
                remaining_amount__gt=0
            )
        elif overdue_status == 'current':
            queryset = queryset.filter(
                Q(due_date__gte=date.today()) | Q(due_date__isnull=True)
            )
        
        return queryset.select_related('sale__customer').prefetch_related('payments')

    @action(detail=False, methods=['post'])
    def create_credit(self, request):
        """
        Endpoint para abrir crédito al cliente desde una venta.
        
        Parámetros:
        - sale_id: ID de la venta
        - original_amount: Monto del crédito
        - due_date: Fecha de vencimiento (opcional)
        """
        serializer = CreateCreditAccountSerializer(data=request.data)
        if serializer.is_valid():
            credit_account = serializer.save()
            response_serializer = CreditAccountSerializer(credit_account)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False)
    def debt_summary(self, request):
        """
        Endpoint para obtener resumen de deuda actual en tiempo real.
        
        Retorna un resumen por cliente de todas las deudas pendientes.
        """
        # Calcular deudas por cliente
        debt_data = []
        
        customers_with_debt = Customer.objects.filter(
            sales__credit_account__remaining_amount__gt=0
        ).distinct()
        
        for customer in customers_with_debt:
            # Obtener todas las cuentas de crédito del cliente
            credit_accounts = CreditAccount.objects.filter(
                sale__customer=customer,
                remaining_amount__gt=0
            )
            
            total_debt = credit_accounts.aggregate(
                total=Sum('remaining_amount')
            )['total'] or 0
            
            # Calcular deuda vencida
            overdue_debt = credit_accounts.filter(
                due_date__lt=date.today()
            ).aggregate(
                total=Sum('remaining_amount')
            )['total'] or 0
            
            active_credits_count = credit_accounts.count()
            overdue_credits_count = credit_accounts.filter(
                due_date__lt=date.today()
            ).count()
            
            debt_data.append({
                'customer_id': customer.id,
                'customer_name': customer.name,
                'customer_phone': customer.phone,
                'customer_email': customer.email,
                'total_debt': total_debt,
                'overdue_debt': overdue_debt,
                'active_credits_count': active_credits_count,
                'overdue_credits_count': overdue_credits_count
            })
        
        # Ordenar por deuda total descendente
        debt_data.sort(key=lambda x: x['total_debt'], reverse=True)
        
        serializer = DebtSummarySerializer(debt_data, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def payment_history(self, request, pk=None):
        """Retorna el historial de pagos de una cuenta de crédito específica."""
        credit_account = self.get_object()
        payments = credit_account.payments.all()
        serializer = CreditPaymentSerializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def overdue_accounts(self, request):
        """Retorna todas las cuentas de crédito vencidas."""
        overdue_accounts = self.get_queryset().filter(
            due_date__lt=date.today(),
            remaining_amount__gt=0
        )
        
        serializer = self.get_serializer(overdue_accounts, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def statistics(self, request):
        """
        Retorna estadísticas del sistema de créditos.
        
        Parámetros de consulta:
        - days: Número de días hacia atrás para calcular estadísticas (default: 30)
        """
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Estadísticas generales
        total_credits = self.get_queryset().count()
        active_credits = self.get_queryset().filter(remaining_amount__gt=0).count()
        overdue_credits = self.get_queryset().filter(
            due_date__lt=date.today(),
            remaining_amount__gt=0
        ).count()
        
        # Montos
        total_credit_amount = self.get_queryset().aggregate(
            total=Sum('original_amount')
        )['total'] or 0
        
        remaining_debt = self.get_queryset().aggregate(
            total=Sum('remaining_amount')
        )['total'] or 0
        
        overdue_debt = self.get_queryset().filter(
            due_date__lt=date.today(),
            remaining_amount__gt=0
        ).aggregate(
            total=Sum('remaining_amount')
        )['total'] or 0
        
        # Pagos recientes
        recent_payments_amount = CreditPayment.objects.filter(
            payment_date__gte=start_date
        ).aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        
        stats = {
            'total_credits': total_credits,
            'active_credits': active_credits,
            'overdue_credits': overdue_credits,
            'total_credit_amount': total_credit_amount,
            'remaining_debt': remaining_debt,
            'overdue_debt': overdue_debt,
            'recent_payments_amount': recent_payments_amount,
            'collection_rate': (
                (total_credit_amount - remaining_debt) / total_credit_amount * 100
                if total_credit_amount > 0 else 0
            )
        }
        
        return Response(stats)


class CreditPaymentViewSet(viewsets.ModelViewSet):
    """Vista para gestionar pagos de crédito."""
    
    queryset = CreditPayment.objects.all()
    serializer_class = CreditPaymentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['credit_account', 'payment_date']
    ordering_fields = ['payment_date', 'amount_paid', 'created_at']

    def get_queryset(self):
        """Incluir relaciones necesarias."""
        return super().get_queryset().select_related(
            'credit_account__sale__customer'
        )

    @action(detail=False, methods=['post'])
    def register_payment(self, request):
        """
        Endpoint para registrar pagos parciales.
        
        Parámetros:
        - credit_account: ID de la cuenta de crédito
        - amount_paid: Monto del pago
        - payment_date: Fecha del pago (opcional, default hoy)
        - notes: Notas del pago (opcional)
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            payment = serializer.save()
            return Response(
                self.get_serializer(payment).data, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False)
    def recent_payments(self, request):
        """
        Retorna pagos recientes.
        
        Parámetros de consulta:
        - days: Número de días hacia atrás (default: 7)
        """
        days = int(request.query_params.get('days', 7))
        start_date = date.today() - timedelta(days=days)
        
        recent_payments = self.get_queryset().filter(
            payment_date__gte=start_date
        ).order_by('-payment_date', '-created_at')
        
        serializer = self.get_serializer(recent_payments, many=True)
        return Response(serializer.data)
