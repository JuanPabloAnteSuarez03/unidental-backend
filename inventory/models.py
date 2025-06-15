from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from catalogs.models import Product, ProductBatch


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
    """
    Modelo para representar el stock actual por producto y ubicación.
    Modificado para manejar lotes cuando sea necesario.
    """
    
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
    batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Lote",
        help_text="Lote específico (solo para productos que requieren control de lotes)"
    )
    quantity = models.IntegerField(default=0, verbose_name="Cantidad")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    
    class Meta:
        verbose_name = "Stock de inventario"
        verbose_name_plural = "Stock de inventario"
        unique_together = ['product', 'location', 'batch']
        ordering = ['product__name', 'location__name']
    
    def __str__(self):
        batch_info = f" - Lote: {self.batch.batch_number}" if self.batch else ""
        return f"{self.product.name} - {self.location.name}: {self.quantity}{batch_info}"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        if self.quantity < 0:
            raise ValidationError({'quantity': 'La cantidad no puede ser negativa.'})
        
        # Validar que el batch corresponde al producto
        if self.batch and self.batch.product != self.product:
            raise ValidationError({'batch': 'El lote no corresponde al producto seleccionado.'})
        
        # Validar que si el producto requiere control de lotes, se especifique un lote
        if self.product.requires_batch_control and not self.batch:
            raise ValidationError({'batch': 'Este producto requiere especificar un lote.'})
        
        # Validar que si el producto no requiere control de lotes, no se especifique un lote
        if not self.product.requires_batch_control and self.batch:
            raise ValidationError({'batch': 'Este producto no requiere control de lotes.'})

    @classmethod
    def get_total_stock(cls, product, location):
        """Obtiene el stock total de un producto en una ubicación (suma de todos los lotes)."""
        return cls.objects.filter(
            product=product,
            location=location
        ).aggregate(total=models.Sum('quantity'))['total'] or 0

    @classmethod
    def get_available_batches(cls, product, location):
        """Obtiene los lotes disponibles de un producto en una ubicación, ordenados por fecha de vencimiento (FIFO)."""
        return cls.objects.filter(
            product=product,
            location=location,
            quantity__gt=0,
            batch__isnull=False
        ).select_related('batch').order_by('batch__expiry_date')


class InventoryMovement(models.Model):
    """
    Modelo para registrar movimientos de entrada y salida de inventario.
    Modificado para manejar lotes y productos compuestos.
    """
    
    MOVEMENT_TYPE_CHOICES = [
        ('in', 'Entrada'),
        ('out', 'Salida'),
        ('composite_conversion', 'Conversión de Producto Compuesto'),
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
    batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Lote",
        help_text="Lote específico (solo para productos que requieren control de lotes)"
    )
    movement_type = models.CharField(
        max_length=20, 
        choices=MOVEMENT_TYPE_CHOICES, 
        verbose_name="Tipo de movimiento"
    )
    quantity = models.IntegerField(verbose_name="Cantidad")
    occurred_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de ocurrencia")
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Usuario",
        related_name="inventory_movements"
    )
    notes = models.TextField(blank=True, default='', verbose_name="Notas")
    
    # Campos para productos compuestos
    related_composite_movement = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Movimiento de Producto Compuesto Relacionado",
        help_text="Movimiento del producto padre que generó este movimiento"
    )
    
    class Meta:
        verbose_name = "Movimiento de inventario"
        verbose_name_plural = "Movimientos de inventario"
        ordering = ['-occurred_at']
    
    def __str__(self):
        sign = "+" if self.movement_type == 'in' else "-"
        batch_info = f" - Lote: {self.batch.batch_number}" if self.batch else ""
        return f"{sign}{self.quantity} {self.product.name} - {self.location.name}{batch_info}"

    def clean(self):
        """Validaciones personalizadas."""
        super().clean()
        
        # Validar cantidad positiva
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'La cantidad debe ser mayor a cero.'})
        
        # Validar tipo de movimiento
        if self.movement_type not in ['in', 'out', 'composite_conversion']:
            raise ValidationError({'movement_type': 'Tipo de movimiento inválido.'})
        
        # Validar que el batch corresponde al producto
        if self.batch and self.batch.product != self.product:
            raise ValidationError({'batch': 'El lote no corresponde al producto seleccionado.'})
        
        # Validar que si el producto requiere control de lotes, se especifique un lote
        if self.product.requires_batch_control and not self.batch:
            raise ValidationError({'batch': 'Este producto requiere especificar un lote.'})
        
        # Validar que no se genere stock negativo en movimientos de salida
        if self.movement_type == 'out':
            if self.batch:
                # Verificar stock del lote específico
                current_stock = InventoryStock.objects.filter(
                    product=self.product,
                    location=self.location,
                    batch=self.batch
                ).first()
                available_quantity = current_stock.quantity if current_stock else 0
            else:
                # Verificar stock total del producto
                available_quantity = InventoryStock.get_total_stock(self.product, self.location)
            
            if available_quantity < self.quantity:
                raise ValidationError({
                    'quantity': f'Stock insuficiente. Disponible: {available_quantity}, solicitado: {self.quantity}'
                })
    
    def save(self, *args, **kwargs):
        """Actualizar el stock automáticamente cuando se crea un movimiento."""
        # Ejecutar validaciones antes de guardar
        self.full_clean()
        
        super().save(*args, **kwargs)
        
        # Actualizar stock
        self._update_stock()
        
        # Si es un producto compuesto, manejar los componentes
        if self.product.is_composite() and self.movement_type in ['in', 'out']:
            self._handle_composite_movement()
    
    def _update_stock(self):
        """Actualiza el stock según el movimiento."""
        # Obtener o crear el registro de stock
        stock, created = InventoryStock.objects.get_or_create(
            product=self.product,
            location=self.location,
            batch=self.batch,
            defaults={'quantity': 0}
        )
        
        # Actualizar la cantidad según el tipo de movimiento
        if self.movement_type == 'in':
            stock.quantity += self.quantity
        elif self.movement_type in ['out', 'composite_conversion']:
            stock.quantity -= self.quantity
            
        # Asegurar que la cantidad no sea negativa
        stock.quantity = max(0, stock.quantity)
        stock.save()
    
    def _handle_composite_movement(self):
        """Maneja los movimientos automáticos de productos compuestos."""
        if not self.product.is_composite():
            return
        
        # Obtener todos los componentes del producto compuesto
        components = self.product.get_components()
        
        for component in components:
            # Calcular la cantidad total de componentes a mover
            component_quantity = self.quantity * component.quantity
            
            # Crear el movimiento para el componente
            InventoryMovement.objects.create(
                product=component.component_product,
                location=self.location,
                batch=None,  # Los componentes no necesariamente tienen el mismo lote
                movement_type='composite_conversion' if self.movement_type == 'out' else 'in',
                quantity=component_quantity,
                user=self.user,
                notes=f"Movimiento automático por {'venta' if self.movement_type == 'out' else 'ingreso'} de {self.product.name}",
                related_composite_movement=self
            )

    @classmethod
    def create_composite_breakdown(cls, composite_product, location, quantity, user=None, notes=""):
        """
        Crea un movimiento para 'desarmar' un producto compuesto.
        Ejemplo: Se tiene 1 caja y se quiere tener 10 blisters disponibles.
        """
        if not composite_product.is_composite():
            raise ValidationError("El producto debe ser un compuesto/kit.")
        
        # Crear movimiento de salida del producto compuesto
        # Usamos save sin argumentos para evitar el manejo automático de componentes
        composite_movement = cls(
            product=composite_product,
            location=location,
            movement_type='out',
            quantity=quantity,
            user=user,
            notes=f"Desarmado de kit: {notes}"
        )
        
        # Primero validamos y guardamos sin trigger automático
        composite_movement.full_clean()
        super(cls, composite_movement).save()
        
        # Actualizar stock del compuesto manualmente
        composite_movement._update_stock()
        
        # Crear movimientos de entrada para los componentes
        components = composite_product.get_components()
        for component in components:
            component_quantity = quantity * component.quantity
            
            cls.objects.create(
                product=component.component_product,
                location=location,
                batch=None,
                movement_type='in',  # Entrada de componentes
                quantity=component_quantity,
                user=user,
                notes=f"Componente de desarmado de {composite_product.name}",
                related_composite_movement=composite_movement
            )
        
        return composite_movement
