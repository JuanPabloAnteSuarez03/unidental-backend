from django.db import models
from django.core.validators import MinValueValidator
from sales.models import Sale
from datetime import date, timedelta


class CreditAccount(models.Model):
    """
    Modelo para gestionar cuentas de crédito por venta.
    Permite abrir crédito a clientes y hacer seguimiento de la deuda.
    """
    
    sale = models.OneToOneField(
        Sale,
        on_delete=models.CASCADE,
        related_name='credit_account',
        verbose_name="Venta"
    )
    original_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Monto original"
    )
    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Monto pendiente"
    )
    start_date = models.DateField(
        default=date.today,
        verbose_name="Fecha de inicio"
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de vencimiento"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de actualización"
    )

    def __str__(self):
        customer_name = self.sale.customer.name if self.sale.customer else "Anónimo"
        return f"Crédito {self.id} - {customer_name} - ${self.remaining_amount}"

    @property
    def is_fully_paid(self):
        """Verifica si el crédito está completamente pagado."""
        return self.remaining_amount == 0

    @property
    def is_overdue(self):
        """Verifica si el crédito está vencido."""
        if not self.due_date:
            return False
        return date.today() > self.due_date and not self.is_fully_paid

    @property
    def total_paid(self):
        """Calcula el total pagado hasta la fecha."""
        return self.original_amount - self.remaining_amount

    def calculate_remaining_amount(self):
        """Recalcula el monto pendiente basado en los pagos registrados."""
        total_payments = self.payments.aggregate(
            total=models.Sum('amount_paid')
        )['total'] or 0
        self.remaining_amount = max(0, self.original_amount - total_payments)
        self.save()

    class Meta:
        verbose_name = "Cuenta de crédito"
        verbose_name_plural = "Cuentas de crédito"
        ordering = ['-created_at']


class CreditPayment(models.Model):
    """
    Modelo para registrar pagos parciales de cuentas de crédito.
    """
    
    credit_account = models.ForeignKey(
        CreditAccount,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Cuenta de crédito"
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Monto pagado"
    )
    payment_date = models.DateField(
        default=date.today,
        verbose_name="Fecha de pago"
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name="Notas"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )

    def __str__(self):
        return f"Pago ${self.amount_paid} - Crédito {self.credit_account.id} - {self.payment_date}"

    def save(self, *args, **kwargs):
        """Actualiza el monto pendiente de la cuenta de crédito al guardar un pago."""
        super().save(*args, **kwargs)
        self.credit_account.calculate_remaining_amount()

    class Meta:
        verbose_name = "Pago de crédito"
        verbose_name_plural = "Pagos de crédito"
        ordering = ['-payment_date', '-created_at']


# =============================
# MODELOS PARA COMPRAS A CRÉDITO
# =============================

class CreditPurchaseAccount(models.Model):
    """
    Modelo para gestionar cuentas de crédito por compra.
    Permite abrir crédito con proveedores y hacer seguimiento de la deuda.
    """
    
    PAYMENT_FREQUENCY_CHOICES = [
        ('weekly', 'Semanal'),
        ('biweekly', 'Quincenal'),
        ('monthly', 'Mensual'),
        ('quarterly', 'Trimestral'),
        ('custom', 'Personalizado'),
    ]
    
    purchase_order = models.OneToOneField(
        'purchases.PurchaseOrder',
        on_delete=models.CASCADE,
        related_name='credit_account',
        verbose_name="Orden de compra"
    )
    original_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Monto original"
    )
    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Monto pendiente"
    )
    start_date = models.DateField(
        default=date.today,
        verbose_name="Fecha de inicio"
    )
    payment_frequency = models.CharField(
        max_length=20,
        choices=PAYMENT_FREQUENCY_CHOICES,
        default='monthly',
        verbose_name="Frecuencia de pago"
    )
    next_payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Próxima fecha de pago"
    )
    payment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        null=True,
        blank=True,
        verbose_name="Monto de pago acordado",
        help_text="Monto acordado para cada pago periódico"
    )
    grace_days = models.PositiveIntegerField(
        default=3,
        verbose_name="Días de gracia",
        help_text="Días de gracia antes de enviar recordatorio"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Indica si la cuenta de crédito está activa"
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name="Notas",
        help_text="Observaciones adicionales sobre el crédito"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de actualización"
    )

    def __str__(self):
        supplier_name = self.purchase_order.supplier.name
        return f"Crédito Compra #{self.id} - {supplier_name} - ${self.remaining_amount}"

    @property
    def is_fully_paid(self):
        """Verifica si el crédito está completamente pagado."""
        return self.remaining_amount == 0

    @property
    def is_overdue(self):
        """Verifica si el crédito está vencido."""
        if not self.next_payment_date or not self.is_active:
            return False
        return date.today() > (self.next_payment_date + timedelta(days=self.grace_days)) and not self.is_fully_paid

    @property
    def total_paid(self):
        """Calcula el total pagado hasta la fecha."""
        return self.original_amount - self.remaining_amount

    @property
    def supplier(self):
        """Shortcut para acceder al proveedor."""
        return self.purchase_order.supplier

    def calculate_remaining_amount(self):
        """Recalcula el monto pendiente basado en los pagos registrados."""
        total_payments = self.payments.aggregate(
            total=models.Sum('amount_paid')
        )['total'] or 0
        self.remaining_amount = max(0, self.original_amount - total_payments)
        self.save()

    def calculate_next_payment_date(self):
        """Calcula la próxima fecha de pago basada en la frecuencia."""
        if not self.next_payment_date:
            return
        
        if self.payment_frequency == 'weekly':
            self.next_payment_date += timedelta(weeks=1)
        elif self.payment_frequency == 'biweekly':
            self.next_payment_date += timedelta(weeks=2)
        elif self.payment_frequency == 'monthly':
            # Agregar un mes
            if self.next_payment_date.month == 12:
                self.next_payment_date = self.next_payment_date.replace(year=self.next_payment_date.year + 1, month=1)
            else:
                self.next_payment_date = self.next_payment_date.replace(month=self.next_payment_date.month + 1)
        elif self.payment_frequency == 'quarterly':
            # Agregar 3 meses
            month = self.next_payment_date.month + 3
            year = self.next_payment_date.year
            if month > 12:
                month -= 12
                year += 1
            self.next_payment_date = self.next_payment_date.replace(year=year, month=month)
        # Para 'custom', no se actualiza automáticamente
        
        self.save()

    class Meta:
        verbose_name = "Cuenta de crédito de compra"
        verbose_name_plural = "Cuentas de crédito de compra"
        ordering = ['-created_at']


class CreditPurchasePayment(models.Model):
    """
    Modelo para registrar abonos/pagos parciales de cuentas de crédito de compra.
    """
    
    credit_account = models.ForeignKey(
        CreditPurchaseAccount,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Cuenta de crédito"
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Monto pagado"
    )
    payment_date = models.DateField(
        default=date.today,
        verbose_name="Fecha de pago"
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="Método de pago",
        help_text="Efectivo, transferencia, cheque, etc."
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Número de referencia",
        help_text="Número de transferencia, cheque, etc."
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name="Notas"
    )
    recorded_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Registrado por",
        related_name="recorded_purchase_payments"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )

    def __str__(self):
        return f"Abono ${self.amount_paid} - {self.credit_account.supplier.name} - {self.payment_date}"

    def save(self, *args, **kwargs):
        """Actualiza el monto pendiente de la cuenta de crédito al guardar un pago."""
        super().save(*args, **kwargs)
        self.credit_account.calculate_remaining_amount()
        
        # Si el pago está al día, calcular la próxima fecha de pago
        if self.credit_account.is_active and not self.credit_account.is_fully_paid:
            self.credit_account.calculate_next_payment_date()

    class Meta:
        verbose_name = "Abono de crédito de compra"
        verbose_name_plural = "Abonos de crédito de compra"
        ordering = ['-payment_date', '-created_at']


class CreditPurchaseReminder(models.Model):
    """
    Modelo para gestionar recordatorios de pago de compras a crédito.
    """
    
    REMINDER_TYPE_CHOICES = [
        ('overdue', 'Pago Vencido'),
        ('upcoming', 'Próximo Pago'),
        ('balance_ok', 'Saldo al Día'),
        ('payment_received', 'Pago Recibido'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('failed', 'Fallido'),
        ('cancelled', 'Cancelado'),
    ]
    
    credit_account = models.ForeignKey(
        CreditPurchaseAccount,
        on_delete=models.CASCADE,
        related_name='reminders',
        verbose_name="Cuenta de crédito"
    )
    reminder_type = models.CharField(
        max_length=20,
        choices=REMINDER_TYPE_CHOICES,
        verbose_name="Tipo de recordatorio"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Estado"
    )
    scheduled_date = models.DateTimeField(
        verbose_name="Fecha programada"
    )
    sent_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de envío"
    )
    message_content = models.TextField(
        verbose_name="Contenido del mensaje"
    )
    whatsapp_message_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="ID del mensaje de WhatsApp"
    )
    error_message = models.TextField(
        blank=True,
        default='',
        verbose_name="Mensaje de error"
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Intentos de reenvío"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )

    def __str__(self):
        return f"Recordatorio {self.get_reminder_type_display()} - {self.credit_account.supplier.name}"

    class Meta:
        verbose_name = "Recordatorio de crédito"
        verbose_name_plural = "Recordatorios de crédito"
        ordering = ['-scheduled_date']
