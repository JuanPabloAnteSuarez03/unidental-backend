from django.shortcuts import render
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Q, Count, Case, When, DecimalField
from django.utils import timezone
from datetime import date, timedelta
from drf_yasg.utils import swagger_auto_schema
from .filters import CreditAccountFilter, CreditPaymentFilter
from drf_yasg import openapi
from urllib.parse import quote
from django.shortcuts import render
from django.http import JsonResponse

from .models import (
    CreditAccount, CreditPayment,
    CreditPurchaseAccount, CreditPurchasePayment
)
from .serializers import (
    CreditAccountSerializer, CreditPaymentSerializer,
    CreateCreditAccountSerializer, DebtSummarySerializer,
    CreditPurchaseAccountSerializer, CreditPurchasePaymentSerializer
)
from sales.models import Customer


def overdue_debts_page(request):
    """
    Vista para mostrar la página de deudas vencidas con botones de WhatsApp.
    """
    return render(request, 'credits/overdue_debts.html')


def generate_whatsapp_url(phone_number, message):
    """
    Genera una URL de WhatsApp con un mensaje pre-llenado.
    
    Args:
        phone_number (str): Número de teléfono del destinatario
        message (str): Mensaje a enviar
        
    Returns:
        str: URL de WhatsApp lista para usar
    """
    if not phone_number:
        return None
    
    # Limpiar el número de teléfono (remover espacios, guiones, etc.)
    clean_phone = ''.join(filter(str.isdigit, phone_number))
    
    # Agregar código de país si no tiene (Colombia +57)
    if not clean_phone.startswith('57') and len(clean_phone) == 10:
        clean_phone = '57' + clean_phone
    
    # Codificar el mensaje para URL
    encoded_message = quote(message)
    
    # Utilizar enlace directo a WhatsApp Web (funciona tanto en móvil como en PC)
    return f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_message}"


class CreditAccountViewSet(viewsets.ModelViewSet):
    """Vista para gestionar cuentas de crédito."""
    
    queryset = CreditAccount.objects.all()
    serializer_class = CreditAccountSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CreditAccountFilter
    search_fields = ['sale__customer__name', 'sale__customer__email', 'sale__customer__phone']
    ordering_fields = ['created_at', 'due_date', 'next_payment_date', 'remaining_amount', 'original_amount']

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
        - payment_frequency: Frecuencia de pago (opcional)
        - installments_count: Número de cuotas (opcional)
        - installment_amount: Monto por cuota (opcional)
        - next_payment_date: Próxima fecha de pago (opcional)
        - initial_payment: Pago inicial (opcional)
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
            Q(due_date__lt=date.today()) | Q(next_payment_date__lt=date.today()),
            remaining_amount__gt=0
        )
        
        serializer = self.get_serializer(overdue_accounts, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def upcoming_payments(self, request):
        """Retorna cuentas con pagos próximos a vencer."""
        days = int(request.query_params.get('days', 7))
        upcoming_date = date.today() + timedelta(days=days)
        
        upcoming_accounts = self.get_queryset().filter(
            next_payment_date__gte=date.today(),
            next_payment_date__lte=upcoming_date,
            remaining_amount__gt=0
        )
        
        serializer = self.get_serializer(upcoming_accounts, many=True)
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

    @action(detail=False, methods=['get'])
    def overdue_with_whatsapp(self, request):
        """
        Endpoint para obtener créditos de clientes vencidos y próximos a vencer con URLs de WhatsApp.
        
        Retorna una lista de cuentas con:
        - Información del cliente
        - Días de vencimiento (positivo = vencido, negativo = próximo a vencer)
        - URL de WhatsApp con mensaje personalizado
        - Mensaje de WhatsApp sugerido
        
        Parámetros de consulta:
        - include_upcoming: incluir pagos próximos a vencer (default: true)
        - upcoming_days: días antes del vencimiento para incluir (default: 3)
        - include_all: incluir TODOS los créditos activos, no solo vencidos/próximos (default: false)
        """
        include_upcoming = request.query_params.get('include_upcoming', 'true').lower() == 'true'
        upcoming_days = int(request.query_params.get('upcoming_days', 3))
        include_all = request.query_params.get('include_all', 'false').lower() == 'true'
        
        if include_all:
            # Obtener TODOS los créditos activos (con saldo pendiente)
            all_accounts = self.get_queryset().filter(
                remaining_amount__gt=0
            ).select_related('sale__customer')
        else:
            # Lógica original: solo vencidos y próximos a vencer
            # Obtener cuentas vencidas (por due_date o next_payment_date)
            overdue_accounts = self.get_queryset().filter(
                Q(due_date__lt=date.today()) | Q(next_payment_date__lt=date.today()),
                remaining_amount__gt=0
            ).select_related('sale__customer')
            
            # Obtener cuentas próximas a vencer si está habilitado
            upcoming_accounts = []
            if include_upcoming:
                upcoming_date = date.today() + timedelta(days=upcoming_days)
                upcoming_accounts = self.get_queryset().filter(
                    Q(
                        Q(due_date__gte=date.today(), due_date__lte=upcoming_date) |
                        Q(next_payment_date__gte=date.today(), next_payment_date__lte=upcoming_date)
                    ),
                    remaining_amount__gt=0
                ).select_related('sale__customer')
            
            # Combinar ambas consultas
            all_accounts = list(overdue_accounts) + list(upcoming_accounts)
        
        data = []
        for account in all_accounts:
            customer = account.sale.customer
            # Determinar fecha de referencia (next_payment_date tiene prioridad)
            reference_date = account.next_payment_date or account.due_date
            
            # Si no hay cliente, usar datos por defecto
            if not customer:
                customer_name = "Cliente no especificado"
                customer_phone = ""
                customer_email = ""
                has_phone = False
            else:
                customer_name = customer.name
                customer_phone = customer.phone or ""
                customer_email = customer.email or ""
                has_phone = bool(customer.phone and customer.phone.strip())
            
            # Si no hay fecha de referencia, usar fecha de creación
            if not reference_date:
                reference_date = account.created_at.date()
                days_difference = 0  # No vencido
                status = 'sin_fecha'
                status_text = 'Sin fecha de vencimiento'
            else:
                days_difference = (date.today() - reference_date).days
                
                # Determinar estado del pago
                if days_difference > 0:
                    status = 'vencido'
                    status_text = f'{days_difference} días vencido'
                elif days_difference < 0:
                    status = 'proximo'
                    status_text = f'{abs(days_difference)} días restantes'
                else:
                    status = 'hoy'
                    status_text = 'Vence hoy'
            
            # Generar mensaje personalizado para cliente
            whatsapp_message = self._generate_customer_payment_reminder_message(
                customer_name, 
                account.remaining_amount, 
                reference_date,
                days_difference
            )
            
            # Generar URL de WhatsApp (solo si hay teléfono)
            whatsapp_url = ""
            if has_phone:
                whatsapp_url = generate_whatsapp_url(customer_phone, whatsapp_message)
            
            data.append({
                'id': account.id,
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'customer_email': customer_email,
                'remaining_amount': str(account.remaining_amount),
                'reference_date': reference_date.strftime('%Y-%m-%d'),
                'days_overdue': days_difference,
                'status': status,
                'status_text': status_text,
                'whatsapp_url': whatsapp_url,
                'whatsapp_message': whatsapp_message,
                'has_phone': has_phone,
            })
        
        # Ordenar por urgencia: vencidos primero (más días vencidos), luego próximos a vencer
        data.sort(key=lambda x: (-x['days_overdue'] if x['status'] == 'vencido' else x['days_overdue'] + 1000))
        
        return Response({
            'overdue_accounts': data,
            'total_count': len(data)
        })

    def _generate_customer_payment_reminder_message(self, customer_name, amount, due_date, days_overdue):
        """
        Genera un mensaje personalizado para recordatorio de pago a clientes.
        """
        formatted_amount = f"${amount:,.0f}"
        formatted_date = due_date.strftime('%d/%m/%Y')
        
        if days_overdue < 0:
            # Recordatorio preventivo
            days_remaining = abs(days_overdue)
            message = f"""Estimado/a {customer_name},

Reciba un cordial saludo de parte de UNIDENTAL.

Le recordamos que se aproxima la fecha de vencimiento de su saldo pendiente:

💰 Monto: {formatted_amount}
📅 Fecha de vencimiento: {formatted_date}
⏰ Días restantes: {days_remaining}

Le solicitamos comedidamente realizar el pago correspondiente antes de la fecha límite.

Si ya realizó el pago, favor hacer caso omiso a este mensaje.

Cordialmente,
Departamento de Cartera
UNIDENTAL"""
        
        elif days_overdue <= 5:
            # Mensaje formal para pocos días vencidos
            message = f"""Estimado/a {customer_name},

Reciba un cordial saludo de parte de UNIDENTAL.

Nos permitimos informarle que tiene un saldo pendiente vencido:

💰 Monto: {formatted_amount}
📅 Fecha de vencimiento: {formatted_date}
⏰ Días vencidos: {days_overdue}

Le solicitamos comedidamente ponerse al día con su pago a la mayor brevedad posible.

Agradecemos su pronta atención.

Cordialmente,
Departamento de Cartera
UNIDENTAL"""
        
        elif days_overdue > 5:
            # Mensaje más directo para muchos días vencidos
            message = f"""Estimado/a {customer_name},

Saludo cordial de UNIDENTAL.

Tiene un saldo vencido que requiere atención inmediata:

💰 Monto: {formatted_amount}
📅 Fecha de vencimiento: {formatted_date}
⏰ Días vencidos: {days_overdue}

Por favor, comuníquese con nosotros para regularizar su situación.

Gracias por su comprensión.

Departamento de Cartera
UNIDENTAL"""
        
        else:
            # Sin fecha de vencimiento o vence hoy
            if days_overdue == 0:
                message = f"""Estimado/a {customer_name},

Reciba un cordial saludo de parte de UNIDENTAL.

Le recordamos que hoy vence su saldo pendiente:

💰 Monto: {formatted_amount}
📅 Fecha de vencimiento: {formatted_date}

Le solicitamos comedidamente realizar el pago correspondiente hoy mismo.

Si ya realizó el pago, favor hacer caso omiso a este mensaje.

Cordialmente,
Departamento de Cartera
UNIDENTAL"""
            else:
                # Sin fecha de vencimiento
                message = f"""Estimado/a {customer_name},

Reciba un cordial saludo de parte de UNIDENTAL.

Le recordamos que tiene un saldo pendiente:

💰 Monto: {formatted_amount}

Le solicitamos comedidamente ponerse en contacto con nosotros para acordar un plan de pagos.

Gracias por su atención.

Cordialmente,
Departamento de Cartera
UNIDENTAL"""
        
        return message


class CreditPaymentViewSet(viewsets.ModelViewSet):
    """Vista para gestionar pagos de crédito."""
    
    queryset = CreditPayment.objects.all()
    serializer_class = CreditPaymentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = CreditPaymentFilter
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


# ==============================================================
# COMPRAS A CRÉDITO - VIEWSETS
# ==============================================================


class CreditPurchaseAccountViewSet(viewsets.ModelViewSet):
    """Vista para gestionar cuentas de crédito de compras."""

    queryset = CreditPurchaseAccount.objects.all()
    serializer_class = CreditPurchaseAccountSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['purchase_order__supplier']
    search_fields = ['purchase_order__supplier__name']
    ordering_fields = ['created_at', 'next_payment_date', 'remaining_amount', 'original_amount']

    def get_queryset(self):
        queryset = super().get_queryset()

        paid_status = self.request.query_params.get('paid_status')
        if paid_status == 'paid':
            queryset = queryset.filter(remaining_amount=0)
        elif paid_status == 'pending':
            queryset = queryset.filter(remaining_amount__gt=0)

        overdue_status = self.request.query_params.get('overdue_status')
        if overdue_status == 'overdue':
            queryset = queryset.filter(
                next_payment_date__lt=date.today(),
                remaining_amount__gt=0
            )
        elif overdue_status == 'current':
            queryset = queryset.filter(
                Q(next_payment_date__gte=date.today()) | Q(next_payment_date__isnull=True)
            )

        return queryset.select_related('purchase_order__supplier').prefetch_related('payments')

    @swagger_auto_schema(
        method='get',
        operation_summary="Historial de pagos",
        operation_description="Obtiene el historial completo de abonos registrados para esta cuenta de crédito de compra.",
        responses={
            200: openapi.Response(
                description="Historial obtenido exitosamente",
                schema=CreditPurchasePaymentSerializer(many=True)
            )
        }
    )
    @action(detail=True, methods=['get'])
    def payment_history(self, request, pk=None):
        """Retorna el historial de pagos de una cuenta de crédito de compra."""
        credit_account = self.get_object()
        serializer = CreditPurchasePaymentSerializer(credit_account.payments.all(), many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Cuentas vencidas",
        operation_description="Lista todas las cuentas de crédito de compra con pagos vencidos.",
        responses={
            200: openapi.Response(
                description="Cuentas vencidas obtenidas exitosamente",
                schema=CreditPurchaseAccountSerializer(many=True)
            )
        }
    )
    @action(detail=False)
    def overdue_accounts(self, request):
        """Retorna todas las cuentas de crédito de compra vencidas."""
        overdue_accounts = self.get_queryset().filter(
            next_payment_date__lt=date.today(),
            remaining_amount__gt=0
        )
        serializer = self.get_serializer(overdue_accounts, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Estadísticas",
        operation_description="Obtiene estadísticas generales del sistema de créditos de compra.",
        manual_parameters=[
            openapi.Parameter('days', openapi.IN_QUERY, description="Número de días hacia atrás (default 30)", type=openapi.TYPE_INTEGER)
        ],
        responses={
            200: openapi.Response(description="Estadísticas obtenidas exitosamente")
        }
    )
    @action(detail=False)
    def statistics(self, request):
        """Retorna estadísticas del sistema de créditos de compra."""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        total_credits = self.get_queryset().count()
        active_credits = self.get_queryset().filter(remaining_amount__gt=0).count()
        overdue_credits = self.get_queryset().filter(
            next_payment_date__lt=date.today(),
            remaining_amount__gt=0
        ).count()

        total_credit_amount = self.get_queryset().aggregate(total=Sum('original_amount'))['total'] or 0
        remaining_debt = self.get_queryset().aggregate(total=Sum('remaining_amount'))['total'] or 0
        overdue_debt = self.get_queryset().filter(
            next_payment_date__lt=date.today(),
            remaining_amount__gt=0
        ).aggregate(total=Sum('remaining_amount'))['total'] or 0

        recent_payments_amount = CreditPurchasePayment.objects.filter(
            payment_date__gte=start_date
        ).aggregate(total=Sum('amount_paid'))['total'] or 0

        stats = {
            'total_credits': total_credits,
            'active_credits': active_credits,
            'overdue_credits': overdue_credits,
            'total_credit_amount': total_credit_amount,
            'remaining_debt': remaining_debt,
            'overdue_debt': overdue_debt,
            'recent_payments_amount': recent_payments_amount,
            'collection_rate': ((total_credit_amount - remaining_debt) / total_credit_amount * 100) if total_credit_amount > 0 else 0
        }

        return Response(stats)

    @swagger_auto_schema(
        method='get',
        operation_summary="Deudas vencidas y próximas a vencer con WhatsApp",
        operation_description="Obtiene las deudas vencidas y próximas a vencer con URLs de WhatsApp para enviar recordatorios.",
        manual_parameters=[
            openapi.Parameter('include_upcoming', openapi.IN_QUERY, description="Incluir pagos próximos a vencer (default: true)", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('upcoming_days', openapi.IN_QUERY, description="Días antes del vencimiento para incluir (default: 3)", type=openapi.TYPE_INTEGER)
        ],
        responses={
            200: openapi.Response(
                description="Deudas y recordatorios obtenidos exitosamente",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'overdue_accounts': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'supplier_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'contact_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'phone': openapi.Schema(type=openapi.TYPE_STRING),
                                    'remaining_amount': openapi.Schema(type=openapi.TYPE_STRING),
                                    'next_payment_date': openapi.Schema(type=openapi.TYPE_STRING),
                                    'days_overdue': openapi.Schema(type=openapi.TYPE_INTEGER, description="Positivo = vencido, Negativo = próximo a vencer"),
                                    'status': openapi.Schema(type=openapi.TYPE_STRING, description="Estado: vencido, proximo, hoy"),
                                    'status_text': openapi.Schema(type=openapi.TYPE_STRING, description="Descripción del estado"),
                                    'whatsapp_url': openapi.Schema(type=openapi.TYPE_STRING),
                                    'whatsapp_message': openapi.Schema(type=openapi.TYPE_STRING),
                                    'has_phone': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                }
                            )
                        ),
                        'total_count': openapi.Schema(type=openapi.TYPE_INTEGER)
                    }
                )
            )
        }
    )
    @action(detail=False, methods=['get'])
    def overdue_with_whatsapp(self, request):
        """
        Endpoint para obtener deudas vencidas y próximas a vencer con URLs de WhatsApp pre-configuradas.
        
        Retorna una lista de cuentas con:
        - Información del proveedor
        - Días de vencimiento (positivo = vencido, negativo = próximo a vencer)
        - URL de WhatsApp con mensaje personalizado
        - Mensaje de WhatsApp sugerido
        
        Parámetros de consulta:
        - include_upcoming: incluir pagos próximos a vencer (default: true)
        - upcoming_days: días antes del vencimiento para incluir (default: 3)
        """
        include_upcoming = request.query_params.get('include_upcoming', 'true').lower() == 'true'
        upcoming_days = int(request.query_params.get('upcoming_days', 3))
        
        # Obtener cuentas vencidas
        overdue_accounts = self.get_queryset().filter(
            next_payment_date__lt=date.today(),
            remaining_amount__gt=0,
            is_active=True
        ).select_related('purchase_order__supplier')
        
        # Obtener cuentas próximas a vencer si está habilitado
        upcoming_accounts = []
        if include_upcoming:
            upcoming_date = date.today() + timedelta(days=upcoming_days)
            upcoming_accounts = self.get_queryset().filter(
                next_payment_date__gte=date.today(),
                next_payment_date__lte=upcoming_date,
                remaining_amount__gt=0,
                is_active=True
            ).select_related('purchase_order__supplier')
        
        # Combinar ambas consultas
        all_accounts = list(overdue_accounts) + list(upcoming_accounts)
        
        data = []
        for account in all_accounts:
            supplier = account.purchase_order.supplier
            days_difference = (date.today() - account.next_payment_date).days
            
            # Determinar estado del pago
            if days_difference > 0:
                status = 'vencido'
                status_text = f'{days_difference} días vencido'
            elif days_difference < 0:
                status = 'proximo'
                status_text = f'{abs(days_difference)} días restantes'
            else:
                status = 'hoy'
                status_text = 'Vence hoy'
            
            # Generar mensaje personalizado
            contact_name = supplier.contact_name or supplier.name
            whatsapp_message = self._generate_payment_reminder_message(
                contact_name, 
                account.remaining_amount, 
                account.next_payment_date,
                days_difference
            )
            
            # Generar URL de WhatsApp
            whatsapp_url = generate_whatsapp_url(supplier.phone, whatsapp_message)
            
            data.append({
                'id': account.id,
                'supplier_name': supplier.name,
                'contact_name': contact_name,
                'phone': supplier.phone,
                'remaining_amount': str(account.remaining_amount),
                'next_payment_date': account.next_payment_date.strftime('%Y-%m-%d'),
                'days_overdue': days_difference,
                'status': status,
                'status_text': status_text,
                'whatsapp_url': whatsapp_url,
                'whatsapp_message': whatsapp_message,
                'has_phone': bool(supplier.phone and supplier.phone.strip()),
            })
        
        # Ordenar por urgencia: vencidos primero (más días vencidos), luego próximos a vencer (menos días restantes)
        data.sort(key=lambda x: (-x['days_overdue'] if x['status'] == 'vencido' else x['days_overdue'] + 1000))
        
        return Response({
            'overdue_accounts': data,
            'total_count': len(data)
        })

    def _generate_payment_reminder_message(self, contact_name, amount, due_date, days_overdue):
        """
        Genera un mensaje personalizado para recordatorio de pago.
        
        Args:
            contact_name (str): Nombre del contacto
            amount (Decimal): Monto adeudado
            due_date (date): Fecha de vencimiento
            days_overdue (int): Días vencidos (puede ser negativo para fechas futuras)
            
        Returns:
            str: Mensaje personalizado
        """
        formatted_amount = f"${amount:,.0f}"
        formatted_date = due_date.strftime('%d/%m/%Y')
        
        if days_overdue < 0:
            # Recordatorio preventivo (antes del vencimiento)
            days_remaining = abs(days_overdue)
            message = f"""Estimado/a {contact_name},

Reciba un cordial saludo de parte de UNIDENTAL.

Le recordamos que se aproxima la fecha de vencimiento de su saldo pendiente de un crédito con nosotros:

💰 Monto: {formatted_amount}
📅 Fecha de vencimiento: {formatted_date}
⏰ Días restantes: {days_remaining}

Le solicitamos comedidamente realizar el pago correspondiente antes de la fecha límite para evitar inconvenientes.

Si ya realizó el pago, favor hacer caso omiso a este mensaje.

Cordialmente,
Departamento de Cartera
UNIDENTAL"""
        
        elif days_overdue <= 5:
            # Mensaje formal para pocos días vencidos
            message = f"""Estimado/a {contact_name},

Reciba un cordial saludo de parte de UNIDENTAL.

Nos permitimos informarle que tiene un saldo pendiente de un crédito vencido con nosotros:

💰 Monto: {formatted_amount}
📅 Fecha de vencimiento: {formatted_date}
⏰ Días vencidos: {days_overdue}

Le solicitamos comedidamente regularizar su situación a la brevedad posible. Estamos disponibles para cualquier aclaración que requiera.

Agradecemos su pronta gestión.

Cordialmente,
Departamento de Cartera
UNIDENTAL"""
        
        elif days_overdue <= 15:
            # Mensaje formal para vencimiento moderado
            message = f"""Estimado/a {contact_name},

Reciba un cordial saludo de parte de UNIDENTAL.

Le informamos que mantiene un saldo pendiente de un crédito vencido con nosotros:

💰 Monto: {formatted_amount}
📅 Fecha de vencimiento: {formatted_date}
⚠️ Días vencidos: {days_overdue}

Es importante regularizar su situación. Le solicitamos confirmar la fecha en que realizará el pago correspondiente.

Esperamos su pronta respuesta y gestión.

Cordialmente,
Departamento de Cartera
UNIDENTAL"""
        
        else:
            # Mensaje formal urgente para vencimientos largos
            message = f"""Estimado/a {contact_name},

Reciba un cordial saludo de parte de UNIDENTAL.

Le informamos que tiene un saldo pendiente de un crédito con vencimiento considerable:

💰 Monto: {formatted_amount}
📅 Fecha de vencimiento: {formatted_date}
🚨 Días vencidos: {days_overdue}

Es urgente que se comunique con nuestro Departamento de Cartera para regularizar su situación y preservar nuestra relación de negocios.

Su pronta gestión es fundamental.

Cordialmente,
Departamento de Cartera
UNIDENTAL"""
        
        return message


class CreditPurchasePaymentViewSet(viewsets.ModelViewSet):
    """Vista para gestionar pagos de créditos de compra."""

    queryset = CreditPurchasePayment.objects.all()
    serializer_class = CreditPurchasePaymentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['credit_account', 'payment_date', 'payment_method']
    ordering_fields = ['payment_date', 'amount_paid', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('credit_account__purchase_order__supplier')

    @swagger_auto_schema(
        method='post',
        operation_summary="Registrar pago",
        operation_description="Registra un nuevo abono a una cuenta de crédito de compra.",
        request_body=CreditPurchasePaymentSerializer,
        responses={
            201: openapi.Response(description="Pago registrado exitosamente", schema=CreditPurchasePaymentSerializer),
            400: openapi.Response(description="Datos inválidos")
        }
    )
    @action(detail=False, methods=['post'])
    def register_payment(self, request):
        """Endpoint para registrar un pago de crédito de compra."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            payment = serializer.save(recorded_by=request.user if request.user.is_authenticated else None)
            return Response(self.get_serializer(payment).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        method='get',
        operation_summary="Pagos recientes",
        operation_description="Obtiene los abonos registrados en los últimos días.",
        manual_parameters=[
            openapi.Parameter('days', openapi.IN_QUERY, description="Días a retroceder (default 7)", type=openapi.TYPE_INTEGER)
        ],
        responses={
            200: openapi.Response(description="Pagos obtenidos exitosamente", schema=CreditPurchasePaymentSerializer(many=True))
        }
    )
    @action(detail=False)
    def recent_payments(self, request):
        """Retorna los pagos de crédito de compra más recientes."""
        days = int(request.query_params.get('days', 7))
        start_date = date.today() - timedelta(days=days)
        recent_payments = self.get_queryset().filter(payment_date__gte=start_date)
        serializer = self.get_serializer(recent_payments, many=True)
        return Response(serializer.data)
