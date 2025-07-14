from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from .validators import validate_sku

# --- Modelos para la estructura del SKU ---

class SkuCategory(models.Model):
    """
    Categoría principal para la construcción de un SKU.
    Ej: ART (Artículos), TST (Test), LAB (Laboratorio).
    """
    code = models.CharField(
        max_length=3, 
        unique=True, 
        verbose_name="Código de Categoría SKU",
        help_text="Código único de 3 letras para la categoría del SKU (ej: ART)."
    )
    name = models.CharField(
        max_length=100, 
        verbose_name="Nombre de Categoría SKU",
        help_text="Nombre descriptivo de la categoría del SKU."
    )

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        verbose_name = "Categoría de SKU"
        verbose_name_plural = "Categorías de SKU"
        ordering = ['code']

class SkuSubCategory(models.Model):
    """
    Subcategoría para la construcción de un SKU, dependiente de una Categoría.
    Ej: PRE (Preventivos), NUE (Nuevos), YEP (Yesos).
    """
    category = models.ForeignKey(
        SkuCategory, 
        on_delete=models.CASCADE, 
        related_name='subcategories', 
        verbose_name="Categoría de SKU"
    )
    code = models.CharField(
        max_length=3, 
        verbose_name="Código de Subcategoría SKU",
        help_text="Código de 3 letras para la subcategoría (único por categoría)."
    )
    name = models.CharField(
        max_length=100, 
        verbose_name="Nombre de Subcategoría SKU",
        help_text="Nombre descriptivo de la subcategoría del SKU."
    )

    def __str__(self):
        return f"{self.category.code}-{self.code} - {self.name}"

    class Meta:
        verbose_name = "Subcategoría de SKU"
        verbose_name_plural = "Subcategorías de SKU"
        unique_together = ['category', 'code']
        ordering = ['category__code', 'code']

class SkuType(models.Model):
    """
    Tipo para la construcción de un SKU, dependiente de una Subcategoría.
    Ej: BIO (Bioseguridad), VAP (Varios), ELI (Elite).
    """
    subcategory = models.ForeignKey(
        SkuSubCategory, 
        on_delete=models.CASCADE, 
        related_name='types', 
        verbose_name="Subcategoría de SKU"
    )
    code = models.CharField(
        max_length=3, 
        verbose_name="Código de Tipo de SKU",
        help_text="Código de 3 letras para el tipo (único por subcategoría)."
    )
    name = models.CharField(
        max_length=100, 
        verbose_name="Nombre de Tipo de SKU",
        help_text="Nombre descriptivo del tipo de SKU."
    )

    def __str__(self):
        return f"{self.subcategory.category.code}-{self.subcategory.code}-{self.code} - {self.name}"

    class Meta:
        verbose_name = "Tipo de SKU"
        verbose_name_plural = "Tipos de SKU"
        unique_together = ['subcategory', 'code']
        ordering = ['subcategory__category__code', 'subcategory__code', 'code']


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
    # Nuevos tipos para soportar la diferenciación entre cajas homogéneas (boxed_component)
    # y kits mixtos (mixed_kit). Se mantiene "composite" para compatibilidad con datos
    # existentes, pero se recomienda migrar a los nuevos tipos.
    PRODUCT_TYPE_CHOICES = [
        ('simple', 'Producto Simple'),
        ('boxed_component', 'Caja/Empaque de componente único'),
        ('mixed_kit', 'Kit Mixto de varios productos'),
        ('composite', 'Producto Compuesto/Kit (LEGACY)'),
        ('component', 'Componente individual de Kit'),
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
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Precio de venta",
        help_text="Precio de lista o PVP recomendado"
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
        """Retorna True si este producto es un producto compuesto (caja o kit)."""
        return self.product_type in ['boxed_component', 'mixed_kit', 'composite']

    def is_boxed_component(self):
        """True si el producto es una caja que contiene unidades homogéneas del mismo componente."""
        return self.product_type == 'boxed_component'

    def is_mixed_kit(self):
        """True si el producto es un kit mixto con distintos componentes."""
        return self.product_type == 'mixed_kit'
    
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

    def is_component(self):
        """True si el producto es un componente individual que puede formar parte de un kit."""
        return self.product_type == 'component'


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
        
        if not self.composite_product.is_composite():
            raise ValidationError("El producto padre debe ser de tipo compuesto (boxed_component o mixed_kit).")
        
        if self.component_product.is_composite():
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
