from django.db import models
from django.core.validators import MinValueValidator
from sales.models import Sale
from datetime import date


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
