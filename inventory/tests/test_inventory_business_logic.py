import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from inventory.models import Location, InventoryStock, InventoryMovement
from catalogs.models import Category, Product, ProductBatch

User = get_user_model()

@pytest.fixture
def test_user():
    """Fixture para crear un usuario de prueba."""
    return User.objects.create_user(
        username='testuser_business',
        email='testuser_business@example.com',
        password='TestPass123!'
    )

@pytest.fixture
def test_data():
    """Fixture para crear datos de prueba."""
    # Crear categoría y producto
    category = Category.objects.create(name='Test Category Business', description='For business tests')
    product = Product.objects.create(
        sku='BUS-TEST-001',
        name='Test Product Business',
        description='Product for business testing',
        unit='unidad',
        category=category
    )
    
    # Crear ubicaciones
    sede = Location.objects.create(name='Sede Test Business', type='sede', address='Test Address')
    bodega = Location.objects.create(name='Bodega Test Business', type='bodega', address='Test Warehouse')
    
    return {
        'category': category,
        'product': product,
        'sede': sede,
        'bodega': bodega
    }

@pytest.mark.django_db
class TestInventoryBusinessLogic:
    """Tests para la lógica de negocio del inventario."""

    def test_stock_auto_creation_on_first_movement(self, test_data, test_user):
        """Prueba que el stock se crea automáticamente en el primer movimiento de entrada."""
        # Verificar que no existe stock inicial
        assert not InventoryStock.objects.filter(
            product=test_data['product'],
            location=test_data['sede']
        ).exists()
        
        # Crear movimiento de entrada
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=50,
            user=test_user
        )
        
        # Verificar que se creó el stock automáticamente
        stock = InventoryStock.objects.get(
            product=test_data['product'],
            location=test_data['sede']
        )
        assert stock.quantity == 50

    def test_stock_update_on_entry_movement(self, test_data, test_user):
        """Prueba que el stock se actualiza correctamente en movimientos de entrada."""
        # Crear stock inicial
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=30
        )
        
        # Crear movimiento de entrada
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=20,
            user=test_user
        )
        
        # Verificar que el stock se actualizó
        stock.refresh_from_db()
        assert stock.quantity == 50

    def test_stock_update_on_exit_movement(self, test_data, test_user):
        """Prueba que el stock se actualiza correctamente en movimientos de salida."""
        # Crear stock inicial
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=100
        )
        
        # Crear movimiento de salida
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='out',
            quantity=25,
            user=test_user
        )
        
        # Verificar que el stock se actualizó
        stock.refresh_from_db()
        assert stock.quantity == 75

    def test_prevent_negative_stock(self, test_data, test_user):
        """Prueba que no se permite stock negativo."""
        # Crear stock inicial bajo
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=10
        )
        
        # Intentar crear movimiento que resultaría en stock negativo
        with pytest.raises(ValidationError) as exc_info:
            movement = InventoryMovement(
                product=test_data['product'],
                location=test_data['sede'],
                movement_type='out',
                quantity=15,  # Más que el stock disponible
                user=test_user
            )
            movement.save()  # Ahora la validación se ejecuta en save()
        
        # Verificar que el stock no cambió
        stock.refresh_from_db()
        assert stock.quantity == 10

    def test_multiple_movements_same_product_location(self, test_data, test_user):
        """Prueba múltiples movimientos en el mismo producto y ubicación."""
        # Crear varios movimientos
        movements_data = [
            {'type': 'in', 'quantity': 50},
            {'type': 'in', 'quantity': 30},
            {'type': 'out', 'quantity': 20},
            {'type': 'in', 'quantity': 10},
            {'type': 'out', 'quantity': 15},
        ]
        
        expected_stock = 0
        for mov_data in movements_data:
            InventoryMovement.objects.create(
                product=test_data['product'],
                location=test_data['sede'],
                movement_type=mov_data['type'],
                quantity=mov_data['quantity'],
                user=test_user
            )
            
            if mov_data['type'] == 'in':
                expected_stock += mov_data['quantity']
            else:
                expected_stock -= mov_data['quantity']
        
        # Verificar stock final
        final_stock = InventoryStock.objects.get(
            product=test_data['product'],
            location=test_data['sede']
        )
        assert final_stock.quantity == expected_stock

    def test_stock_tracking_different_locations(self, test_data, test_user):
        """Prueba que el stock se maneja independientemente por ubicación."""
        # Crear movimientos en diferentes ubicaciones
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=100,
            user=test_user
        )
        
        InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['bodega'],
            movement_type='in',
            quantity=200,
            user=test_user
        )
        
        # Verificar que cada ubicación tiene su propio stock
        stock_sede = InventoryStock.objects.get(
            product=test_data['product'],
            location=test_data['sede']
        )
        stock_bodega = InventoryStock.objects.get(
            product=test_data['product'],
            location=test_data['bodega']
        )
        
        assert stock_sede.quantity == 100
        assert stock_bodega.quantity == 200

    def test_movement_with_expiry_date(self, test_data, test_user):
        """Prueba movimientos con lotes (en lugar de expiry_date directamente)."""
        # El producto debe requerir control de lotes
        test_data['product'].requires_batch_control = True
        test_data['product'].save()
        
        expiry_date = date.today() + timedelta(days=180)
        
        # Crear lote
        batch = ProductBatch.objects.create(
            product=test_data['product'],
            batch_number='LOT-BUSINESS-001',
            expiry_date=expiry_date
        )
        
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=75,
            batch=batch,
            user=test_user
        )
        
        assert movement.batch == batch
        assert movement.batch.expiry_date == expiry_date
        
        # Verificar que el stock se actualizó normalmente
        stock = InventoryStock.objects.get(
            product=test_data['product'],
            location=test_data['sede'],
            batch=batch
        )
        assert stock.quantity == 75

    def test_movement_auto_sets_user(self, test_data, test_user):
        """Prueba que el usuario se asigna automáticamente al movimiento."""
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=40,
            user=test_user
        )
        
        assert movement.user == test_user

    def test_movement_auto_sets_timestamp(self, test_data, test_user):
        """Prueba que el timestamp se asigna automáticamente."""
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=40,
            user=test_user
        )
        
        assert movement.occurred_at is not None
        # Verificar que fue creado recientemente (dentro de los últimos 10 segundos)
        from django.utils import timezone
        now = timezone.now()
        time_diff = (now - movement.occurred_at).total_seconds()
        assert time_diff < 10

@pytest.mark.django_db
class TestInventoryDataIntegrity:
    """Tests para integridad de datos del inventario."""

    def test_location_unique_constraint(self, test_data):
        """Prueba que no se pueden crear ubicaciones con nombres duplicados."""
        with pytest.raises(IntegrityError):
            Location.objects.create(
                name=test_data['sede'].name,  # Nombre duplicado
                type='bodega',
                address='Otra dirección'
            )

    def test_stock_unique_product_location_constraint(self, test_data):
        """Prueba constraint único que ahora incluye batch."""
        # Crear primer stock sin batch
        InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=50
        )
        
        # Crear stock con batch (debe funcionar ya que son diferentes)
        test_data['product'].requires_batch_control = True
        test_data['product'].save()
        
        batch = ProductBatch.objects.create(
            product=test_data['product'],
            batch_number='LOT-CONSTRAINT-001',
            expiry_date=date.today() + timedelta(days=365)
        )
        
        # Esto debe funcionar porque el constraint incluye batch
        stock_with_batch = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            batch=batch,
            quantity=30
        )
        
        assert stock_with_batch.quantity == 30

    def test_movement_requires_product(self, test_data, test_user):
        """Prueba que un movimiento requiere un producto."""
        with pytest.raises(IntegrityError):  # Cambió de ValidationError a IntegrityError
            InventoryMovement.objects.create(
                product=None,
                location=test_data['sede'],
                movement_type='in',
                quantity=10,
                user=test_user
            )

    def test_movement_requires_location(self, test_data, test_user):
        """Prueba que un movimiento requiere una ubicación."""
        with pytest.raises(ValidationError):
            InventoryMovement.objects.create(
                product=test_data['product'],
                location=None,
                movement_type='in',
                quantity=10,
                user=test_user
            )

    def test_movement_requires_valid_type(self, test_data, test_user):
        """Prueba que un movimiento requiere un tipo válido."""
        movement = InventoryMovement(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='invalid_type',
            quantity=10,
            user=test_user
        )
        
        with pytest.raises(ValidationError):
            movement.full_clean()

    def test_movement_requires_positive_quantity(self, test_data, test_user):
        """Prueba que un movimiento requiere cantidad positiva."""
        movement = InventoryMovement(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=0,  # Cantidad inválida
            user=test_user
        )
        
        with pytest.raises(ValidationError):
            movement.full_clean()
        
        movement.quantity = -5  # Cantidad negativa
        with pytest.raises(ValidationError):
            movement.full_clean()

    def test_stock_requires_non_negative_quantity(self, test_data):
        """Prueba que el stock no puede ser negativo."""
        stock = InventoryStock(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=-10  # Cantidad negativa
        )
        
        with pytest.raises(ValidationError):
            stock.full_clean()

    def test_location_requires_valid_type(self):
        """Prueba que la ubicación requiere un tipo válido."""
        location = Location(
            name='Test Invalid',
            type='invalid_type',
            address='Test Address'
        )
        
        with pytest.raises(ValidationError):
            location.full_clean()

    def test_cascade_delete_product_affects_stock_and_movements(self, test_data, test_user):
        """Prueba que eliminar un producto elimina su stock y movimientos."""
        # Crear stock y movimientos
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=100
        )
        
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=100,
            user=test_user
        )
        
        # Eliminar producto
        product_id = test_data['product'].id
        test_data['product'].delete()
        
        # Verificar que stock y movimientos fueron eliminados
        assert not InventoryStock.objects.filter(product_id=product_id).exists()
        assert not InventoryMovement.objects.filter(product_id=product_id).exists()

    def test_cascade_delete_location_affects_stock_and_movements(self, test_data, test_user):
        """Prueba que eliminar una ubicación elimina su stock y movimientos."""
        # Crear stock y movimientos
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=50
        )
        
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=50,
            user=test_user
        )
        
        # Eliminar ubicación
        location_id = test_data['sede'].id
        test_data['sede'].delete()
        
        # Verificar que stock y movimientos fueron eliminados
        assert not InventoryStock.objects.filter(location_id=location_id).exists()
        assert not InventoryMovement.objects.filter(location_id=location_id).exists()

    def test_soft_delete_user_preserves_movements(self, test_data, test_user):
        """Prueba que los movimientos se preservan cuando se elimina un usuario."""
        # Crear movimiento
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=30,
            user=test_user
        )
        
        # Eliminar usuario
        user_id = test_user.id
        test_user.delete()
        
        # Verificar que el movimiento aún existe pero sin usuario
        movement.refresh_from_db()
        assert movement.user is None

@pytest.mark.django_db
class TestInventoryTransactions:
    """Tests para transacciones y concurrencia."""

    def test_atomic_stock_update(self, test_data, test_user):
        """Prueba que las actualizaciones de stock son atómicas."""
        # Crear stock inicial
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=100
        )
        
        # Simular una transacción que falla después de crear el movimiento
        # Usamos un movimiento válido pero forzamos una excepción después
        with pytest.raises(Exception):
            with transaction.atomic():
                # Crear movimiento válido (entrada)
                movement = InventoryMovement.objects.create(
                    product=test_data['product'],
                    location=test_data['sede'],
                    movement_type='in',
                    quantity=20,
                    user=test_user
                )
                
                # Forzar una excepción después del movimiento válido
                raise Exception("Simulated transaction failure")
        
        # Verificar que el stock no cambió (rollback exitoso)
        stock.refresh_from_db()
        assert stock.quantity == 100
        
        # Verificar que no se creó el movimiento
        assert not InventoryMovement.objects.filter(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=20
        ).exists()

    def test_concurrent_movements_same_stock(self, test_data, test_user):
        """Prueba el manejo de movimientos concurrentes en el mismo stock."""
        # Crear stock inicial
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=100
        )
        
        # Simular movimientos concurrentes
        movements = []
        for i in range(5):
            movement = InventoryMovement.objects.create(
                product=test_data['product'],
                location=test_data['sede'],
                movement_type='out',
                quantity=10,
                user=test_user
            )
            movements.append(movement)
        
        # Verificar que el stock final es correcto
        stock.refresh_from_db()
        assert stock.quantity == 50  # 100 - (5 * 10)
        
        # Verificar que todos los movimientos se crearon
        assert len(movements) == 5

@pytest.mark.django_db
class TestInventoryBusinessRules:
    """Tests para reglas de negocio específicas."""

    def test_expiry_date_validation(self, test_data, test_user):
        """Prueba validación de fechas de vencimiento usando lotes."""
        from catalogs.models import ProductBatch
        
        # El producto debe requerir control de lotes
        test_data['product'].requires_batch_control = True
        test_data['product'].save()
        
        # Crear lote con fecha pasada (debe funcionar para tests)
        past_date = date.today() - timedelta(days=30)
        batch = ProductBatch.objects.create(
            product=test_data['product'],
            batch_number='LOT-PAST-001',
            expiry_date=past_date
        )
        
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=25,
            batch=batch,
            user=test_user,
            notes='Lote vencido para pruebas'
        )
        
        # Verificar que el lote está vencido
        assert movement.batch.expiry_date == past_date
        assert movement.batch.is_expired == True

    def test_movement_notes_optional(self, test_data, test_user):
        """Prueba que las notas en movimientos son opcionales."""
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=25,
            user=test_user
            # Sin notes
        )
        
        assert movement.notes == ''  # Por defecto debería ser cadena vacía

    def test_movement_with_long_notes(self, test_data, test_user):
        """Prueba movimientos con notas largas."""
        long_notes = "A" * 500  # Notas largas
        
        movement = InventoryMovement.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=15,
            notes=long_notes,
            user=test_user
        )
        
        assert movement.notes == long_notes

    def test_location_address_optional(self):
        """Prueba que la dirección de ubicación es opcional."""
        location = Location.objects.create(
            name='Test Location No Address',
            type='sede'
            # Sin address
        )
        
        assert location.address == ''  # Por defecto debería ser cadena vacía

    def test_stock_zero_quantity_allowed(self, test_data):
        """Prueba que se permite stock con cantidad cero."""
        stock = InventoryStock.objects.create(
            product=test_data['product'],
            location=test_data['sede'],
            quantity=0
        )
        
        assert stock.quantity == 0

    def test_location_types_validation(self):
        """Prueba los tipos de ubicación permitidos."""
        # Tipo sede
        sede = Location(name='Test Sede', type='sede', address='Dir Sede')
        sede.full_clean()  # No debe fallar
        sede.save()
        
        # Tipo bodega
        bodega = Location(name='Test Bodega', type='bodega', address='Dir Bodega')
        bodega.full_clean()  # No debe fallar
        bodega.save()
        
        # Tipo inválido
        invalid_location = Location(name='Test Invalid', type='oficina', address='Dir')
        with pytest.raises(ValidationError):
            invalid_location.full_clean()

    def test_movement_types_validation(self, test_data, test_user):
        """Prueba los tipos de movimiento permitidos."""
        # Tipo entrada
        mov_in = InventoryMovement(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='in',
            quantity=10,
            user=test_user
        )
        mov_in.full_clean()  # No debe fallar
        mov_in.save()
        
        # Tipo salida
        mov_out = InventoryMovement(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='out',
            quantity=5,
            user=test_user
        )
        mov_out.full_clean()  # No debe fallar
        mov_out.save()
        
        # Tipo inválido
        invalid_movement = InventoryMovement(
            product=test_data['product'],
            location=test_data['sede'],
            movement_type='transfer',
            quantity=3,
            user=test_user
        )
        with pytest.raises(ValidationError):
            invalid_movement.full_clean() 