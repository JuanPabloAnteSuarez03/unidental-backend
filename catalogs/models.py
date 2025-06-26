from django.db import models
from django.core.exceptions import ValidationError
from .validators import validate_sku

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
    PRODUCT_TYPE_CHOICES = [
        ('simple', 'Producto Simple'),
        ('composite', 'Producto Compuesto/Kit'),
        ('component', 'Componente de Kit'),
    ]
    
    sku = models.CharField(
        max_length=50, 
        unique=True, 
        null=False, 
        blank=False,
        verbose_name="SKU (Código Único de Producto)",
        validators=[validate_sku],
        help_text="Formato: CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL (ej: ART-PRE-BIO-001)"
    )
    barcode = models.CharField(
        max_length=100,  # Los códigos de barras pueden ser largos, ej. Code 128
        unique=True,
        null=True,
        blank=True,
        verbose_name="Código de Barras",
        help_text="Código de barras del producto (EAN, UPC, etc.) si aplica."
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
    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_TYPE_CHOICES,
        default='simple',
        verbose_name="Tipo de Producto",
        help_text="Simple: producto individual, Compuesto: contiene otros productos, Componente: parte de un kit"
    )
    requires_batch_control = models.BooleanField(
        default=False,
        verbose_name="Requiere Control de Lotes",
        help_text="Marcar si este producto requiere seguimiento por lotes (fechas de vencimiento)"
    )
    min_stock_threshold = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Umbral Mínimo de Stock",
        help_text="Cantidad mínima de stock aceptable para este producto en una sede."
    )
    min_expiry_days_threshold = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Umbral Mínimo de Días de Vencimiento",
        help_text="Número mínimo de días antes del vencimiento para que un lote sea considerado aceptable."
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
    
    def is_composite(self):
        """Retorna True si este producto es un compuesto/kit."""
        return self.product_type == 'composite'
    
    def is_component(self):
        """Retorna True si este producto es componente de un kit."""
        return self.product_type == 'component'
    
    def get_components(self):
        """Retorna los componentes de este producto si es un compuesto."""
        if self.is_composite():
            return self.composite_components.all()
        return ProductComponent.objects.none()
    
    def get_parent_kits(self):
        """Retorna los kits de los cuales este producto es componente."""
        if self.is_component():
            return self.component_of.all()
        return ProductComponent.objects.none()


class ProductComponent(models.Model):
    """
    Relación para productos compuestos (kits).
    Ejemplo: Una caja contiene 10 blisters.
    """
    composite_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='composite_components',
        verbose_name="Producto Compuesto",
        help_text="El producto kit/caja que contiene otros productos"
    )
    component_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='component_of',
        verbose_name="Producto Componente",
        help_text="El producto individual que está contenido en el kit"
    )
    quantity = models.PositiveIntegerField(
        verbose_name="Cantidad",
        help_text="Cantidad del componente contenida en una unidad del producto compuesto"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Componente de Producto"
        verbose_name_plural = "Componentes de Productos"
        unique_together = ['composite_product', 'component_product']
        ordering = ['composite_product__name', 'component_product__name']

    def __str__(self):
        return f"{self.composite_product.name} contiene {self.quantity}x {self.component_product.name}"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        
        if self.composite_product == self.component_product:
            raise ValidationError("Un producto no puede ser componente de sí mismo.")
        
        if self.composite_product.product_type != 'composite':
            raise ValidationError("El producto padre debe ser de tipo 'Compuesto/Kit'.")
        
        if self.component_product.product_type == 'composite':
            raise ValidationError("Un producto compuesto no puede ser componente de otro (no se admiten kits anidados).")


class ProductBatch(models.Model):
    """
    Lote de producto con fecha de vencimiento.
    Permite el control de productos por lotes para fechas de expiración.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='batches',
        verbose_name="Producto"
    )
    batch_number = models.CharField(
        max_length=100,
        verbose_name="Número de Lote",
        help_text="Identificación única del lote del fabricante"
    )
    manufacturing_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Fabricación"
    )
    expiry_date = models.DateField(
        verbose_name="Fecha de Vencimiento",
        help_text="Fecha en que el lote expira"
    )
    supplier_reference = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Referencia del Proveedor",
        help_text="Referencia o código del proveedor para este lote"
    )
    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Notas",
        help_text="Observaciones adicionales sobre el lote"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lote de Producto"
        verbose_name_plural = "Lotes de Productos"
        unique_together = ['product', 'batch_number']
        ordering = ['expiry_date', 'batch_number']

    def __str__(self):
        return f"{self.product.name} - Lote: {self.batch_number} (Vence: {self.expiry_date})"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        
        if not self.product.requires_batch_control:
            raise ValidationError("Este producto no requiere control de lotes.")
        
        if self.manufacturing_date and self.expiry_date and self.manufacturing_date >= self.expiry_date:
            raise ValidationError("La fecha de fabricación debe ser anterior a la fecha de vencimiento.")

    @property
    def is_expired(self):
        """Retorna True si el lote ya ha expirado."""
        from django.utils import timezone
        return self.expiry_date < timezone.now().date()

    @property
    def days_to_expiry(self):
        """Retorna los días hasta el vencimiento (negativo si ya expiró)."""
        from django.utils import timezone
        delta = self.expiry_date - timezone.now().date()
        return delta.days
