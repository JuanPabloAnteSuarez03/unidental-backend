from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from suppliers.models import Supplier, PurchaseOption
from inventory.models import Location
from decimal import Decimal


class PurchaseOrderPayment(models.Model):
    order = models.ForeignKey('PurchaseOrder', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    cash = models.ForeignKey('cash.Cash', on_delete=models.SET_NULL, null=True, blank=True)
    is_annulled = models.BooleanField(default=False)
    annulled_at = models.DateTimeField(null=True, blank=True)
    annulled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='annulled_purchase_payments')

    def clean(self):
        # No permitir pagos mayores al saldo pendiente
        if self.amount <= 0:
            raise ValidationError({'amount': 'El monto debe ser mayor a cero.'})
        if self.order and not self.is_annulled:
            total_paid = self.order.get_total_paid(exclude_payment=self)
            if total_paid + self.amount > self.order.get_total_amount():
                raise ValidationError({'amount': 'No se puede pagar más del total de la orden.'})

    def __str__(self):
        return f"Pago de ${self.amount} para Orden #{self.order.id}"


class PurchaseOrder(models.Model):
    """
    Modelo para representar una orden de compra.
    Encabezado de la orden que contiene información general.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('received', 'Recibida'),
        ('canceled', 'Cancelada'),
    ]
    
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        verbose_name="Proveedor",
        related_name="purchase_orders",
        help_text="Proveedor al cual se realiza la orden de compra"
    )
    destination = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        verbose_name="Destino",
        related_name="purchase_orders",
        help_text="Ubicación donde se recibirán los productos"
    )
    order_date = models.DateField(
        default=timezone.localdate,
        verbose_name="Fecha de orden",
        help_text="Fecha en que se realizó la orden"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Estado",
        help_text="Estado actual de la orden de compra"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Creado por",
        related_name="created_purchase_orders",
        help_text="Usuario que creó la orden"
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name="Notas",
        help_text="Observaciones o notas adicionales sobre la orden"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de actualización"
    )

    class Meta:
        verbose_name = "Orden de compra"
        verbose_name_plural = "Órdenes de compra"
        ordering = ['-order_date', '-created_at']

    def __str__(self):
        return f"Orden #{self.id} - {self.supplier.name} ({self.get_status_display()})"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        
        # Validar que la fecha de orden no sea futura
        if self.order_date and self.order_date > timezone.localdate():
            raise ValidationError({
                'order_date': 'La fecha de orden no puede ser futura.'
            })
        
        # Validar que no se pueda cambiar de 'received' o 'canceled' a 'pending'
        if self.pk:  # Solo para órdenes existentes
            try:
                old_instance = PurchaseOrder.objects.get(pk=self.pk)
                if old_instance.status in ['received', 'canceled'] and self.status == 'pending':
                    raise ValidationError({
                        'status': f'No se puede cambiar el estado de {old_instance.get_status_display()} a Pendiente.'
                    })
            except PurchaseOrder.DoesNotExist:
                pass

    @property
    def payment_status(self):
        total_paid = self.get_total_paid()
        total_amount = self.get_total_amount()
        if total_paid == 0:
            return 'pendiente'
        elif total_paid < total_amount:
            return 'parcial'
        else:
            return 'pagada'

    def get_total_paid(self, exclude_payment=None):
        qs = self.payments.filter(is_annulled=False)
        if exclude_payment:
            qs = qs.exclude(pk=exclude_payment.pk)
        return qs.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    def get_total_amount(self):
        # Si tienes un campo total_amount, úsalo. Si no, calcula sumando los items.
        if hasattr(self, 'total_amount') and self.total_amount:
            return self.total_amount
        return sum(item.line_total for item in self.items.all())

    @property
    def total_amount(self):
        """Calcula el monto total de la orden."""
        return sum(item.line_total for item in self.items.all())

    @property
    def total_items(self):
        """Calcula la cantidad total de items en la orden."""
        return sum(item.quantity_requested for item in self.items.all())

    def can_be_modified(self):
        """Verifica si la orden puede ser modificada."""
        return self.status == 'pending'

    def cancel_order(self):
        """Cancela la orden si está en estado pendiente."""
        if self.status == 'pending':
            self.status = 'canceled'
            self.save()
            return True
        return False

    def mark_as_received(self):
        """Marca la orden como recibida si está en estado pendiente."""
        if self.status == 'pending':
            self.status = 'received'
            self.save()
            return True
        return False


class PurchaseOrderItem(models.Model):
    """
    Modelo para representar un item de una orden de compra.
    Detalle específico de cada producto en la orden.
    """
    
    order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        verbose_name="Orden de compra",
        related_name="items",
        help_text="Orden de compra a la que pertenece este item"
    )
    purchase_option = models.ForeignKey(
        PurchaseOption,
        on_delete=models.CASCADE,
        verbose_name="Opción de compra",
        related_name="order_items",
        help_text="Opción de compra (producto + proveedor + marca + precio)"
    )
    quantity_requested = models.PositiveIntegerField(
        verbose_name="Cantidad solicitada",
        help_text="Cantidad de unidades solicitadas"
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Precio unitario",
        help_text="Precio por unidad al momento de la orden"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )

    class Meta:
        verbose_name = "Item de orden de compra"
        verbose_name_plural = "Items de orden de compra"
        ordering = ['order', 'purchase_option__product__name']
        unique_together = ['order', 'purchase_option']

    def __str__(self):
        return f"{self.purchase_option.product.name} - {self.purchase_option.brand} (x{self.quantity_requested})"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        
        # Validar que el proveedor del purchase_option coincida con el de la orden
        if self.order and self.purchase_option:
            if self.purchase_option.supplier != self.order.supplier:
                raise ValidationError({
                    'purchase_option': 'La opción de compra debe ser del mismo proveedor que la orden.'
                })
        
        # Validar cantidad positiva
        if self.quantity_requested <= 0:
            raise ValidationError({
                'quantity_requested': 'La cantidad solicitada debe ser mayor a cero.'
            })
        
        # Validar precio positivo
        if self.unit_price <= 0:
            raise ValidationError({
                'unit_price': 'El precio unitario debe ser mayor a cero.'
            })
        
        # Validar que la orden pueda ser modificada
        if self.order and not self.order.can_be_modified():
            raise ValidationError({
                'order': f'No se pueden agregar items a una orden en estado {self.order.get_status_display()}.'
            })

    @property
    def line_total(self):
        """Calcula el total de la línea (cantidad × precio unitario)."""
        return self.quantity_requested * self.unit_price

    def save(self, *args, **kwargs):
        """Sobrescribe save para ejecutar validaciones."""
        self.full_clean()
        super().save(*args, **kwargs)
