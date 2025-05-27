from django.db import models

# Create your models here.

class Category(models.Model):
    """
    Categoría para agrupar productos.
    Ejemplos: Insumos Médicos, Equipamiento Dental, Material de Oficina.
    """
    name = models.CharField(
        max_length=100, 
        unique=True, 
        null=False, 
        blank=False,
        verbose_name="Nombre de la Categoría"
    )
    description = models.TextField(
        null=True, 
        blank=True,
        verbose_name="Descripción"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Actualización"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['name']

class Product(models.Model):
    """
    Producto ofrecido o gestionado por Unidental.
    """
    sku = models.CharField(
        max_length=50, 
        unique=True, 
        null=False, 
        blank=False,
        verbose_name="SKU (Código Único de Producto)"
    )
    name = models.CharField(
        max_length=200, 
        null=False, 
        blank=False,
        verbose_name="Nombre del Producto"
    )
    description = models.TextField(
        null=True, 
        blank=True,
        verbose_name="Descripción"
    )
    unit = models.CharField(
        max_length=20, 
        null=False, 
        blank=False,
        verbose_name="Unidad de Medida",
        help_text="Ej: unidad, caja, kg, litro"
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, # O models.SET_NULL si un producto puede quedar sin categoría
        related_name='products',
        verbose_name="Categoría"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Actualización"
    )

    def __str__(self):
        return f"{self.name} ({self.sku})"

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['name']
