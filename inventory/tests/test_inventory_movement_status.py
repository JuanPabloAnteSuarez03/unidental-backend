import pytest
from django.contrib.auth.models import User
from catalogs.models import Product, Category
from inventory.models import Location, InventoryMovement, InventoryStock

@pytest.mark.django_db
class TestInventoryMovementStatus:
    """
    Pruebas para verificar el impacto de los estados de InventoryMovement en el stock.
    """

    def setup_method(self):
        """Configura los datos básicos para las pruebas."""
        self.user = User.objects.create(username='testuser')
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Test Product', 
            sku='TP001', 
            category=self.category,
            unit='unidad'
        )
        self.location = Location.objects.create(name='Test Location', type='bodega')

    def test_pending_movement_does_not_affect_stock(self):
        """Verifica que un movimiento 'pendiente' no cambia el stock."""
        InventoryMovement.objects.create(
            product=self.product,
            location=self.location,
            movement_type='in',
            quantity=10,
            status='pending'
        )
        
        stock = InventoryStock.get_total_stock(self.product, self.location)
        assert stock == 0, "El stock no debería cambiar para movimientos pendientes."

    def test_cancelled_movement_does_not_affect_stock(self):
        """Verifica que un movimiento 'cancelado' no cambia el stock."""
        InventoryMovement.objects.create(
            product=self.product,
            location=self.location,
            movement_type='in',
            quantity=10,
            status='cancelled'
        )
        
        stock = InventoryStock.get_total_stock(self.product, self.location)
        assert stock == 0, "El stock no debería cambiar para movimientos cancelados."

    def test_completed_movement_updates_stock(self):
        """Verifica que un movimiento 'completado' actualiza el stock."""
        InventoryMovement.objects.create(
            product=self.product,
            location=self.location,
            movement_type='in',
            quantity=10,
            status='completed'
        )
        
        stock = InventoryStock.get_total_stock(self.product, self.location)
        assert stock == 10, "El stock debería actualizarse para movimientos completados."

    def test_status_change_from_pending_to_completed_updates_stock(self):
        """Verifica que el stock se actualiza cuando un movimiento pasa de 'pendiente' a 'completado'."""
        movement = InventoryMovement.objects.create(
            product=self.product,
            location=self.location,
            movement_type='in',
            quantity=5,
            status='pending'
        )
        
        # El stock inicial debe ser 0
        assert InventoryStock.get_total_stock(self.product, self.location) == 0
        
        # Cambiar estado a 'completado' y guardar
        movement.status = 'completed'
        movement.save()
        
        stock = InventoryStock.get_total_stock(self.product, self.location)
        assert stock == 5, "El stock debería actualizarse al cambiar el estado a 'completado'."

    def test_status_change_from_completed_to_cancelled_reverts_stock(self):
        """Verifica que el stock se revierte si un movimiento pasa de 'completado' a 'cancelado'."""
        movement = InventoryMovement.objects.create(
            product=self.product,
            location=self.location,
            movement_type='in',
            quantity=8,
            status='completed'
        )
        
        # El stock inicial debe ser 8
        assert InventoryStock.get_total_stock(self.product, self.location) == 8
        
        # Cambiar estado a 'cancelado' y guardar
        movement.status = 'cancelled'
        movement.save()
        
        stock = InventoryStock.get_total_stock(self.product, self.location)
        assert stock == 0, "El stock debería revertirse al cambiar el estado a 'cancelado'."

    def test_revert_and_reapply_stock(self):
        """
        Prueba un ciclo de vida completo:
        1. Creado como 'completado'.
        2. Cambiado a 'pendiente' (revierte).
        3. Cambiado de nuevo a 'completado' (re-aplica).
        """
        # 1. Creado como completado
        movement = InventoryMovement.objects.create(
            product=self.product,
            location=self.location,
            movement_type='in',
            quantity=12,
            status='completed'
        )
        assert InventoryStock.get_total_stock(self.product, self.location) == 12

        # 2. Cambiado a pendiente
        movement.status = 'pending'
        movement.save()
        assert InventoryStock.get_total_stock(self.product, self.location) == 0

        # 3. Cambiado de nuevo a completado
        movement.status = 'completed'
        movement.save()
        assert InventoryStock.get_total_stock(self.product, self.location) == 12, "El stock debería reaplicarse correctamente." 