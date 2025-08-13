from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from inventory.models import Location


class Cashes(models.Model):
    """
    Modelo para representar una caja de efectivo asociada a una ubicación.
    """
    location = models.OneToOneField(
        Location,
        on_delete=models.CASCADE,
        verbose_name="Sede",
        related_name="cash",
        help_text="Sede a la que pertenece esta caja"
    )
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Saldo Actual",
        help_text="Saldo actual de la caja (calculado automáticamente)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Indica si la caja está activa para operaciones"
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
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        ordering = ['location__name']

    def __str__(self):
        return f"Caja de {self.location.name}"

    # Elimina update_balance y la recursión
    # El balance solo se actualiza de forma incremental

    @classmethod
    def get_total_balance(cls):
        """Retorna el saldo total de todas las cajas activas."""
        return cls.objects.filter(is_active=True).aggregate(
            total=models.Sum('balance')
        )['total'] or Decimal('0.00')

    def has_sufficient_balance(self, amount):
        """Verifica si la caja tiene saldo suficiente para un egreso."""
        return self.balance >= amount


class Movements(models.Model):
    """
    Modelo para representar movimientos de efectivo en las cajas.
    """
    MOVEMENT_TYPE_CHOICES = [
        ('ingreso', 'Ingreso'),
        ('egreso', 'Egreso'),
        ('ajuste', 'Ajuste'),
    ]
    
    REFERENCE_TYPE_CHOICES = [
        ('venta', 'Venta'),
        ('compra', 'Compra'),
        ('ajuste_manual', 'Ajuste Manual'),
        ('transferencia', 'Transferencia'),
        ('otro', 'Otro'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('cancelled', 'Anulado'),
    ]
    
    cash = models.ForeignKey(
        Cashes,
        on_delete=models.CASCADE,
        verbose_name="Caja",
        related_name="movements",
        help_text="Caja donde se registra el movimiento"
    )
    movement_type = models.CharField(
        max_length=10,
        choices=MOVEMENT_TYPE_CHOICES,
        verbose_name="Tipo de Movimiento",
        help_text="Tipo de movimiento: ingreso, egreso o ajuste"
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Monto",
        help_text="Monto del movimiento (siempre positivo)"
    )
    reference_type = models.CharField(
        max_length=20,
        choices=REFERENCE_TYPE_CHOICES,
        verbose_name="Tipo de Referencia",
        help_text="Indica el origen del movimiento"
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name="Notas",
        help_text="Motivo o descripción del movimiento"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="Estado",
        help_text="Estado del movimiento"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Creado por",
        related_name="created_cash_movements",
        help_text="Usuario que creó el movimiento"
    )
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Anulado por",
        related_name="cancelled_cash_movements",
        help_text="Usuario que anuló el movimiento"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de anulación"
    )
    cancellation_reason = models.TextField(
        blank=True,
        default='',
        verbose_name="Motivo de Anulación",
        help_text="Razón por la cual se anuló el movimiento"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de actualización"
    )
    
    # Referencias opcionales a otros modelos
    sale = models.ForeignKey(
        'sales.Sale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Venta Relacionada",
        related_name="cash_movements",
        help_text="Venta asociada a este movimiento (si aplica)"
    )
    purchase_order = models.ForeignKey(
        'purchases.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Orden de Compra Relacionada",
        related_name="cash_movements",
        help_text="Orden de compra asociada a este movimiento (si aplica)"
    )

    class Meta:
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cash', 'status'], name='cash_cashmo_cash_id_590b7e_idx'),
            models.Index(fields=['movement_type', 'created_at'], name='cash_cashmo_movemen_be744e_idx'),
            models.Index(fields=['reference_type'], name='cash_cashmo_referen_77a2e7_idx'),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} ${self.amount} - {self.cash.location.name}"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        
        if self.amount <= 0:
            raise ValidationError({
                'amount': 'El monto debe ser mayor a cero.'
            })

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        previous_status = None
        previous_movement_type = None
        previous_amount = None
        previous_balance = None
        
        if not is_new:
            try:
                previous = Movements.objects.get(pk=self.pk)
                previous_status = previous.status
                previous_movement_type = previous.movement_type
                previous_amount = previous.amount
                # Guardar el balance anterior para ajustes
                if previous.movement_type == 'ajuste':
                    previous_balance = previous.cash.balance
            except Movements.DoesNotExist:
                # Si no existe el registro anterior, es un nuevo registro
                is_new = True

        super().save(*args, **kwargs)

        # Solo si es nuevo o cambió el estado, tipo o monto
        if is_new:
            self.apply_to_cash_balance(sign=1)
        elif previous_status != self.status or previous_movement_type != self.movement_type or previous_amount != self.amount:
            # Revertir el anterior
            self.apply_to_cash_balance(sign=-1, movement_type=previous_movement_type, amount=previous_amount, status=previous_status, previous_balance=previous_balance)
            # Aplicar el nuevo
            self.apply_to_cash_balance(sign=1)

    def apply_to_cash_balance(self, sign=1, movement_type=None, amount=None, status=None, previous_balance=None):
        # Usa los valores actuales si no se pasan
        movement_type = movement_type or self.movement_type
        amount = amount if amount is not None else self.amount
        status = status or self.status
        if status != 'active':
            return
        if movement_type == 'ingreso':
            self.cash.balance += sign * amount
        elif movement_type == 'egreso':
            self.cash.balance -= sign * amount
        elif movement_type == 'ajuste':
            if sign == 1:  # Aplicando el ajuste
                self.cash.balance = amount
            else:  # Revirtiendo el ajuste
                if previous_balance is not None:
                    self.cash.balance = previous_balance
                # Si no tenemos el balance anterior, no podemos revertir el ajuste
                # En este caso, el ajuste no se revierte automáticamente
        self.cash.save(update_fields=['balance'])

    def cancel(self, user, reason=""):
        if self.status == 'cancelled':
            raise ValidationError("El movimiento ya está anulado.")
        # Revertir el efecto en el balance
        self.apply_to_cash_balance(sign=-1)
        self.status = 'cancelled'
        self.cancelled_by = user
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.save()

    def reactivate(self, user):
        if self.status == 'active':
            raise ValidationError("El movimiento ya está activo.")
        # Aplicar el efecto en el balance
        self.status = 'active'
        self.cancelled_by = None
        self.cancelled_at = None
        self.cancellation_reason = ""
        self.save()
        self.apply_to_cash_balance(sign=1)


class Transfers(models.Model):
    """
    Modelo para representar transferencias entre cajas.
    """
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ]
    
    origin_cash = models.ForeignKey(
        Cashes,
        on_delete=models.CASCADE,
        verbose_name="Caja Origen",
        related_name="outgoing_transfers",
        help_text="Caja desde donde sale el dinero"
    )
    destination_cash = models.ForeignKey(
        Cashes,
        on_delete=models.CASCADE,
        verbose_name="Caja Destino",
        related_name="incoming_transfers",
        help_text="Caja donde llega el dinero"
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Monto",
        help_text="Monto a transferir"
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name="Notas",
        help_text="Motivo o descripción de la transferencia"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Estado"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Creado por",
        related_name="created_cash_transfers"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de completación"
    )
    
    # Movimientos generados por la transferencia
    origin_movement = models.ForeignKey(
        Movements,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Movimiento de Salida",
        related_name="origin_transfer",
        help_text="Movimiento de egreso en la caja origen"
    )
    destination_movement = models.ForeignKey(
        Movements,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Movimiento de Entrada",
        related_name="destination_transfer",
        help_text="Movimiento de ingreso en la caja destino"
    )

    class Meta:
        verbose_name = "Transferencia de Caja"
        verbose_name_plural = "Transferencias de Caja"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='cash_cashtr_status_62558e_idx'),
            models.Index(fields=['origin_cash', 'destination_cash'], name='cash_cashtr_origin__339e90_idx'),
        ]

    def __str__(self):
        return f"Transferencia ${self.amount} de {self.origin_cash.location.name} a {self.destination_cash.location.name}"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        
        if self.origin_cash == self.destination_cash:
            raise ValidationError({
                'destination_cash': 'No se puede transferir a la misma caja.'
            })
        
        if self.amount <= 0:
            raise ValidationError({
                'amount': 'El monto debe ser mayor a cero.'
            })

    def execute_transfer(self, user):
        """Ejecuta la transferencia creando los movimientos correspondientes."""
        if self.status != 'pending':
            raise ValidationError("Solo se pueden ejecutar transferencias pendientes.")
        
        if self.origin_cash.balance < self.amount:
            raise ValidationError("Saldo insuficiente en la caja origen.")
        
        # Crear movimiento de egreso en la caja origen
        self.origin_movement = Movements.objects.create(
            cash=self.origin_cash,
            movement_type='egreso',
            amount=self.amount,
            reference_type='transferencia',
            notes=f"Transferencia a {self.destination_cash.location.name}: {self.notes}",
            created_by=user
        )
        
        # Crear movimiento de ingreso en la caja destino
        self.destination_movement = CashMovement.objects.create(
            cash=self.destination_cash,
            movement_type='ingreso',
            amount=self.amount,
            reference_type='transferencia',
            notes=f"Transferencia desde {self.origin_cash.location.name}: {self.notes}",
            created_by=user
        )
        
        # Marcar como completada
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

    def cancel_transfer(self, user, reason=""):
        """Cancela la transferencia."""
        if self.status == 'cancelled':
            raise ValidationError("La transferencia ya está cancelada.")
        
        # Si ya se ejecutó, revertir los movimientos
        if self.status == 'completed':
            if self.origin_movement:
                self.origin_movement.cancel(user, f"Cancelación de transferencia: {reason}")
            if self.destination_movement:
                self.destination_movement.cancel(user, f"Cancelación de transferencia: {reason}")
        
        self.status = 'cancelled'
        self.save()
