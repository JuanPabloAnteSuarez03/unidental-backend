from django.db import models
from django.utils import timezone
from catalogs.models import Product


class Supplier(models.Model):
    """
    Modelo para representar un proveedor.
    """
    name = models.CharField(
        max_length=200,
        verbose_name="Nombre del proveedor",
        help_text="Nombre completo del proveedor o empresa"
    )
    contact_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nombre del contacto",
        help_text="Persona de contacto en el proveedor"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Teléfono",
        help_text="Número de teléfono del proveedor"
    )
    email = models.EmailField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Email",
        help_text="Correo electrónico del proveedor"
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
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['name']

    def __str__(self):
        return self.name


class PurchaseOption(models.Model):
    """
    Modelo para representar las opciones de compra de productos por proveedor.
    Incluye precios y marcas específicas por proveedor.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='purchase_options',
        verbose_name="Producto",
        help_text="Producto al que se refiere esta opción de compra"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='purchase_options',
        verbose_name="Proveedor",
        help_text="Proveedor que ofrece este producto"
    )
    brand = models.CharField(
        max_length=100,
        verbose_name="Marca",
        help_text="Marca del producto ofrecida por este proveedor"
    )
    purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Precio de compra",
        help_text="Precio al que el proveedor vende este producto"
    )
    valid_from = models.DateField(
        default=timezone.localdate,
        verbose_name="Válido desde",
        help_text="Fecha desde la cual es válido este precio"
    )
    valid_to = models.DateField(
        blank=True,
        null=True,
        verbose_name="Válido hasta",
        help_text="Fecha hasta la cual es válido este precio (opcional)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )

    class Meta:
        verbose_name = "Opción de compra"
        verbose_name_plural = "Opciones de compra"
        ordering = ['product__name', 'supplier__name', '-valid_from']
        unique_together = [['product', 'supplier', 'brand', 'valid_from']]

    def __str__(self):
        return f"{self.product.name} - {self.supplier.name} ({self.brand})"

    def is_currently_valid(self):
        """
        Verifica si esta opción de compra está actualmente válida.
        """
        today = timezone.localdate()
        if self.valid_to:
            return self.valid_from <= today <= self.valid_to
        return self.valid_from <= today
