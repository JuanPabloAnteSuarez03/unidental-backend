from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from sales.models import Sale
from inventory.models import Location


class Delivery(models.Model):
    """Modelo para manejar domicilios y seguimiento de envíos."""
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('in_transit', 'En Tránsito'),
        ('delivered', 'Entregado'),
    ]
    
    sale = models.OneToOneField(
        Sale,
        on_delete=models.CASCADE,
        related_name='delivery',
        verbose_name='Venta'
    )
    origin_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='deliveries_origin',
        verbose_name='Ubicación de Origen'
    )
    dest_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='deliveries_destination',
        verbose_name='Ubicación de Destino'
    )
    shipped_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Envío'
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Entrega'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Estado'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Entrega'
        verbose_name_plural = 'Entregas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['shipped_at']),
            models.Index(fields=['delivered_at']),
        ]
    
    def __str__(self):
        return f"Entrega #{self.id} - Venta #{self.sale.id} - {self.get_status_display()}"
    
    def clean(self):
        """Validaciones del modelo."""
        super().clean()
        
        # Validar que las fechas sean coherentes
        if self.shipped_at and self.delivered_at:
            if self.shipped_at > self.delivered_at:
                raise ValidationError({
                    'delivered_at': 'La fecha de entrega no puede ser anterior a la fecha de envío.'
                })
        
        # Solo validar estado y fechas si no estamos en proceso de cambio de estado
        if not getattr(self, '_skip_validation', False):
            # Validar estado y fechas
            if self.status == 'in_transit' and not self.shipped_at:
                raise ValidationError({
                    'shipped_at': 'Se requiere fecha de envío para estado "En Tránsito".'
                })
            
            if self.status == 'delivered' and not self.delivered_at:
                raise ValidationError({
                    'delivered_at': 'Se requiere fecha de entrega para estado "Entregado".'
                })
        
        # No se puede tener fecha de entrega sin fecha de envío
        if self.delivered_at and not self.shipped_at:
            raise ValidationError({
                'shipped_at': 'Se requiere fecha de envío antes de la fecha de entrega.'
            })
    
    def save(self, *args, **kwargs):
        # Solo validar si no estamos en el proceso de mark_as_shipped o mark_as_delivered
        if not getattr(self, '_skip_validation', False):
            self.full_clean()
        super().save(*args, **kwargs)
    
    # Métodos de negocio
    def mark_as_shipped(self):
        """Marcar como enviado."""
        if self.status != 'pending':
            raise ValidationError('Solo se puede enviar una entrega pendiente.')
        
        self.status = 'in_transit'
        self.shipped_at = timezone.now()
        self._skip_validation = True
        self.save()
        self._skip_validation = False
    
    def mark_as_delivered(self):
        """Marcar como entregado."""
        if self.status not in ['pending', 'in_transit']:
            raise ValidationError('No se puede entregar una entrega que ya fue entregada.')
        
        self.status = 'delivered'
        now = timezone.now()
        self.delivered_at = now
        
        # Si no tiene fecha de envío, la establecemos al mismo tiempo
        if not self.shipped_at:
            self.shipped_at = now
        
        self._skip_validation = True
        self.save()
        self._skip_validation = False
    
    def can_be_modified(self):
        """Verificar si la entrega puede ser modificada."""
        return self.status == 'pending'
    
    def is_pending(self):
        """Verificar si está pendiente."""
        return self.status == 'pending'
    
    def is_in_transit(self):
        """Verificar si está en tránsito."""
        return self.status == 'in_transit'
    
    def is_delivered(self):
        """Verificar si fue entregado."""
        return self.status == 'delivered'
    
    @property
    def delivery_time(self):
        """Tiempo total de entrega en días."""
        if self.shipped_at and self.delivered_at:
            delta = self.delivered_at - self.shipped_at
            return delta.days
        return None
    
    @property
    def customer_name(self):
        """Nombre del cliente para facilitar acceso."""
        return self.sale.customer.name if self.sale.customer else "Cliente Anónimo"
    
    @property
    def sale_total(self):
        """Total de la venta asociada."""
        return self.sale.total_gross
