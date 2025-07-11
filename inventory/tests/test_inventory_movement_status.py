import pytest
from django.contrib.auth.models import User
from catalogs.models import Product, Category
from inventory.models import Location, InventoryMovement, InventoryStock
from django.core.exceptions import ValidationError

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
        self.destination_location = Location.objects.create(name='Destination Location', type='sede')

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


    # --- Pruebas para Transferencias Internas Automatizadas ---

    def test_completing_transfer_updates_both_locations_stock(self):
        """
        Verifica que al completar una transferencia 'pendiente', se actualiza el stock
        en la ubicación de origen y de destino.
        """
        # 1. Crear stock inicial en la ubicación de origen
        InventoryStock.objects.create(product=self.product, location=self.location, quantity=20)

        # 2. Crear transferencia de salida pendiente
        transfer_movement = InventoryMovement.objects.create(
            product=self.product,
            location=self.location,
            destination_location=self.destination_location,
            movement_type='out',
            quantity=5,
            status='pending',
            is_internal_transfer=True
        )

        # 3. Verificar que el stock no ha cambiado aún
        assert InventoryStock.get_total_stock(self.product, self.location) == 20
        assert InventoryStock.get_total_stock(self.product, self.destination_location) == 0

        # 4. Completar la transferencia
        transfer_movement.status = 'completed'
        transfer_movement.save()

        # 5. Verificar que el stock se ha actualizado correctamente
        assert InventoryStock.get_total_stock(self.product, self.location) == 15, "El stock de origen debió disminuir."
        assert InventoryStock.get_total_stock(self.product, self.destination_location) == 5, "El stock de destino debió aumentar."

        # 6. Verificar que se creó el movimiento de entrada vinculado
        incoming_movement = InventoryMovement.objects.get(related_transfer_movement=transfer_movement)
        assert incoming_movement.movement_type == 'in'
        assert incoming_movement.location == self.destination_location
        assert incoming_movement.quantity == 5
        assert incoming_movement.status == 'completed'


    def test_cancelling_completed_transfer_reverts_stock(self):
        """
        Verifica que al cancelar una transferencia 'completada', el stock se
        revierte en ambas ubicaciones.
        """
        # Crear stock inicial en origen
        InventoryStock.objects.create(product=self.product, location=self.location, quantity=10)

        # Crear y completar la transferencia directamente
        transfer_movement = InventoryMovement.objects.create(
            product=self.product,
            location=self.location,
            destination_location=self.destination_location,
            movement_type='out',
            quantity=7,
            status='completed',
            is_internal_transfer=True
        )

        # Verificar estado inicial
        assert InventoryStock.get_total_stock(self.product, self.location) == 3
        assert InventoryStock.get_total_stock(self.product, self.destination_location) == 7

        # Cancelar la transferencia
        transfer_movement.status = 'cancelled'
        transfer_movement.save()

        # Verificar que el stock se revirtió
        assert InventoryStock.get_total_stock(self.product, self.location) == 10, "El stock de origen debió revertirse."
        assert InventoryStock.get_total_stock(self.product, self.destination_location) == 0, "El stock de destino debió revertirse."

        # Verificar que el movimiento de entrada también se canceló
        incoming_movement = InventoryMovement.objects.get(related_transfer_movement=transfer_movement)
        assert incoming_movement.status == 'cancelled'

    def test_transfer_requires_destination_location(self):
        """
        Verifica que una transferencia de salida no se puede crear sin
        una ubicación de destino.
        """
        with pytest.raises(ValidationError, match="Se requiere una ubicación de destino"):
            movement = InventoryMovement(
                product=self.product,
                location=self.location,
                movement_type='out',
                quantity=1,
                is_internal_transfer=True,
                destination_location=None # Forzamos que sea nulo
            )
            movement.clean() # La validación se ejecuta en el clean 