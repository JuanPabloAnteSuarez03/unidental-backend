from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from catalogs.models import Product


class Location(models.Model):
    """Modelo para representar sedes y bodegas."""
    
    TYPE_CHOICES = [
        ('sede', 'Sede'),
        ('bodega', 'Bodega'),
    ]
    
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Tipo")
    address = models.CharField(max_length=200, blank=True, default='', verbose_name="Dirección")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    
    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        ordering = ['type', 'name']
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.name}"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        if self.type not in ['sede', 'bodega']:
            raise ValidationError({'type': 'Tipo de ubicación inválido.'})


class InventoryStock(models.Model):
    """Modelo para representar el stock actual por producto y ubicación."""
    
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        verbose_name="Producto",
        related_name="stock_locations"
    )
    location = models.ForeignKey(
        Location, 
        on_delete=models.CASCADE, 
        verbose_name="Ubicación",
        related_name="product_stocks"
    )
    quantity = models.IntegerField(default=0, verbose_name="Cantidad")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    
    class Meta:
        verbose_name = "Stock de inventario"
        verbose_name_plural = "Stock de inventario"
        unique_together = ['product', 'location']
        ordering = ['product__name', 'location__name']
    
    def __str__(self):
        return f"{self.product.name} - {self.location.name}: {self.quantity}"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        if self.quantity < 0:
            raise ValidationError({'quantity': 'La cantidad no puede ser negativa.'})


class InventoryMovement(models.Model):
    """Modelo para registrar movimientos de entrada y salida de inventario."""
    
    MOVEMENT_TYPE_CHOICES = [
        ('in', 'Entrada'),
        ('out', 'Salida'),
    ]
    
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        verbose_name="Producto",
        related_name="movements"
    )
    location = models.ForeignKey(
        Location, 
        on_delete=models.CASCADE, 
        verbose_name="Ubicación",
        related_name="movements"
    )
    movement_type = models.CharField(
        max_length=10, 
        choices=MOVEMENT_TYPE_CHOICES, 
        verbose_name="Tipo de movimiento"
    )
    quantity = models.IntegerField(verbose_name="Cantidad")
    occurred_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de ocurrencia")
    expiry_date = models.DateField(
        blank=True, 
        null=True, 
        verbose_name="Fecha de vencimiento"
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Usuario",
        related_name="inventory_movements"
    )
    notes = models.TextField(blank=True, default='', verbose_name="Notas")
    
    class Meta:
        verbose_name = "Movimiento de inventario"
        verbose_name_plural = "Movimientos de inventario"
        ordering = ['-occurred_at']
    
    def __str__(self):
        sign = "+" if self.movement_type == 'in' else "-"
        return f"{sign}{self.quantity} {self.product.name} - {self.location.name}"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        
        # Validar cantidad positiva
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'La cantidad debe ser mayor a cero.'})
        
        # Validar tipo de movimiento
        if self.movement_type not in ['in', 'out']:
            raise ValidationError({'movement_type': 'Tipo de movimiento inválido.'})
        
        # Validar que no se genere stock negativo en movimientos de salida
        if self.movement_type == 'out':
            try:
                stock = InventoryStock.objects.get(
                    product=self.product,
                    location=self.location
                )
                if stock.quantity < self.quantity:
                    raise ValidationError({
                        'quantity': f'Stock insuficiente. Disponible: {stock.quantity}, solicitado: {self.quantity}'
                    })
            except InventoryStock.DoesNotExist:
                raise ValidationError({
                    'quantity': 'No hay stock disponible para este producto en esta ubicación.'
                })
    
    def save(self, *args, **kwargs):
        """Actualizar el stock automáticamente cuando se crea un movimiento."""
        # Ejecutar validaciones antes de guardar
        self.full_clean()
        
        super().save(*args, **kwargs)
        
        # Obtener o crear el registro de stock para este producto y ubicación
        stock, created = InventoryStock.objects.get_or_create(
            product=self.product,
            location=self.location,
            defaults={'quantity': 0}
        )
        
        # Actualizar la cantidad según el tipo de movimiento
        if self.movement_type == 'in':
            stock.quantity += self.quantity
        elif self.movement_type == 'out':
            stock.quantity -= self.quantity
            
        # Asegurar que la cantidad no sea negativa
        stock.quantity = max(0, stock.quantity)
        stock.save()
