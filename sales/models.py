from django.db import models
from django.core.validators import MinValueValidator
from catalogs.models import Product
from inventory.models import Location


class Customer(models.Model):
    """Modelo para gestionar la información de clientes."""
    
    name = models.CharField(max_length=200, verbose_name="Nombre")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name="Correo electrónico")
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
        ('normal', 'Normal'),
        ('mayorista', 'Mayorista'),
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

    def __str__(self):
        return f"{self.quantity} x {self.product.name} en Venta {self.sale.id}"

    def save(self, *args, **kwargs):
        """Actualiza los totales de la venta al guardar un item."""
        super().save(*args, **kwargs)
        self.sale.calculate_totals()

    class Meta:
        verbose_name = "Detalle de venta"
        verbose_name_plural = "Detalles de venta"
        ordering = ['id']
