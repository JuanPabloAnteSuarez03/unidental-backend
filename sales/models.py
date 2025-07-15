from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from catalogs.models import Product, ProductBatch
from inventory.models import Location, InventoryMovement
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from sales.logic import process_return_item, reverse_return_item


class Customer(models.Model):
    """Modelo para gestionar la información de clientes."""
    
    name = models.CharField(max_length=200, verbose_name="Nombre")
    phone = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono")
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name="Correo electrónico")
    address = models.TextField(blank=True, null=True, verbose_name="Dirección")
    birthday = models.DateField(blank=True, null=True, verbose_name="Fecha de cumpleaños")
    emergency_contact = models.CharField(max_length=300, blank=True, null=True, verbose_name="Contacto de emergencia")
    notes = models.TextField(blank=True, null=True, verbose_name="Notas")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['-created_at']


class Sale(models.Model):
    """Modelo para gestionar las ventas y sus detalles principales."""
    
    SALE_TYPE_CHOICES = [
        ('normal', 'Efectivo'),
        ('card', 'Tarjeta'),
        ('credit', 'Crédito'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name="Cliente"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name="Sede de venta",
        help_text="Sede donde se realizó la venta"
    )
    sale_date = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Fecha de venta"
    )
    sale_type = models.CharField(
        max_length=20,
        choices=SALE_TYPE_CHOICES,
        default='normal',
        verbose_name="Tipo de venta"
    )
    should_invoice = models.BooleanField(
        default=True, 
        verbose_name="Requiere factura"
    )
    total_gross = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Total bruto"
    )
    total_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Total neto"
    )

    def __str__(self):
        customer_name = self.customer.name if self.customer else "Anónimo"
        return f"Venta {self.id} - {customer_name} - {self.location.name} - {self.sale_date}"

    def calculate_totals(self):
        """Calcula y actualiza los montos totales de la venta."""
        items = self.items.all()
        self.total_gross = sum(item.quantity * item.unit_price for item in items)
        self.total_net = self.total_gross  # Puede modificarse después para descuentos
        self.save()

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-sale_date']


class SaleItem(models.Model):
    """Modelo para gestionar los items individuales de cada venta."""
    
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Venta"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='sale_items',
        verbose_name="Producto"
    )
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Cantidad"
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Precio unitario"
    )
    batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sale_items',
        verbose_name="Lote",
        help_text="Lote específico (requerido solo para productos con control de lotes)"
    )

    def __str__(self):
        batch_info = f" - Lote: {self.batch.batch_number}" if self.batch else ""
        return f"{self.quantity} x {self.product.name}{batch_info} en Venta {self.sale.id}"

    def clean(self):
        """Validaciones personalizadas para el item de venta."""
        super().clean()
        
        # Validar que si el producto no requiere control de lotes, no se especifique un lote
        if self.product and not self.product.requires_batch_control and self.batch:
            raise ValidationError({'batch': 'Este producto no requiere control de lotes.'})
        
        # Validar que si el producto requiere control de lotes, se especifique un lote
        if self.product and self.product.requires_batch_control and not self.batch:
            raise ValidationError({'batch': 'Este producto requiere especificar un lote.'})
        
        # Validar que el batch corresponde al producto (solo si se especifica un lote)
        if self.batch and self.batch.product != self.product:
            raise ValidationError({'batch': 'El lote no corresponde al producto seleccionado.'})

    def save(self, *args, **kwargs):
        """Actualiza los totales de la venta al guardar un item."""
        # Ejecutar validaciones antes de guardar
        self.full_clean()
        super().save(*args, **kwargs)
        self.sale.calculate_totals()

    class Meta:
        verbose_name = "Detalle de venta"
        verbose_name_plural = "Detalles de venta"
        ordering = ['id']


class Return(models.Model):
    """Modelo para gestionar las devoluciones de ventas."""
    
    REASON_CHOICES = [
        ('defective', 'Producto defectuoso'),
        ('wrong_item', 'Producto incorrecto'),
        ('customer_change', 'Cambio de opinión del cliente'),
        ('damaged', 'Producto dañado'),
        ('expired', 'Producto vencido'),
        ('other', 'Otro'),
    ]
    
    original_sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name='returns',
        verbose_name="Venta original"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='returns',
        verbose_name="Cliente"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='returns',
        verbose_name="Sede de devolución"
    )
    return_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de devolución"
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        verbose_name="Motivo de devolución"
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name="Notas adicionales"
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Monto total devuelto"
    )

    def __str__(self):
        customer_name = self.customer.name if self.customer else "Anónimo"
        return f"Devolución {self.id} - {customer_name} - {self.location.name} - {self.return_date}"

    def calculate_total(self):
        """Calcula y actualiza el monto total de la devolución."""
        items = self.items.all()
        self.total_amount = sum(item.quantity_returned * item.unit_price for item in items)
        self.save()

    class Meta:
        verbose_name = "Devolución"
        verbose_name_plural = "Devoluciones"
        ordering = ['-return_date']


class ReturnItem(models.Model):
    """Modelo para gestionar los items individuales de cada devolución."""
    
    return_obj = models.ForeignKey(
        Return,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Devolución"
    )
    sale_item = models.ForeignKey(
        SaleItem,
        on_delete=models.PROTECT,
        related_name='return_items',
        verbose_name="Item de venta original"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='return_items',
        verbose_name="Producto"
    )
    quantity_returned = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Cantidad devuelta"
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Precio unitario"
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Subtotal"
    )

    def __str__(self):
        return f"{self.quantity_returned} x {self.product.name} devuelto de Venta {self.sale_item.sale.id}"

    def save(self, *args, **kwargs):
        """Calcula el subtotal y actualiza el total de la devolución al guardar."""
        self.subtotal = self.quantity_returned * self.unit_price
        super().save(*args, **kwargs)
        self.return_obj.calculate_total()

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        
        # Validar que el producto corresponde al item de venta
        if self.product != self.sale_item.product:
            raise ValidationError({
                'product': 'El producto debe corresponder al item de venta original.'
            })
        
        # Validar que no se devuelva más cantidad de la vendida
        # Obtener cantidad ya devuelta para este sale_item
        already_returned = ReturnItem.objects.filter(
            sale_item=self.sale_item
        ).exclude(id=self.id).aggregate(
            total=models.Sum('quantity_returned')
        )['total'] or 0
        
        available_to_return = self.sale_item.quantity - already_returned
        
        if self.quantity_returned > available_to_return:
            raise ValidationError({
                'quantity_returned': f'No se puede devolver más cantidad de la disponible. '
                                   f'Disponible para devolver: {available_to_return}'
            })

    class Meta:
        verbose_name = "Item de devolución"
        verbose_name_plural = "Items de devolución"
        ordering = ['id']


# Señal para actualizar el total de la devolución cuando se guarda/elimina un item
@receiver([post_save, post_delete], sender=ReturnItem)
def update_return_total(sender, instance, **kwargs):
    """Actualiza el `total_amount` de la devolución padre."""
    if instance.return_obj:
        instance.return_obj.calculate_total()


# Señales para actualizar el inventario cuando se gestiona un ReturnItem
@receiver(post_save, sender=ReturnItem)
def update_inventory_on_return_item_save(sender, instance, created, **kwargs):
    """
    Actualiza el inventario cuando se crea un item de devolución.
    La lógica detallada (lotes, compuestos) se delega a sales.logic.
    """
    if created:
        process_return_item(instance)

@receiver(post_delete, sender=ReturnItem)
def update_inventory_on_return_item_delete(sender, instance, **kwargs):
    """
    Revierte el stock cuando se elimina un item de devolución.
    La lógica detallada (lotes, compuestos) se delega a sales.logic.
    """
    reverse_return_item(instance)
