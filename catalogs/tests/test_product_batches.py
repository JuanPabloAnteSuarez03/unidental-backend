import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import date, timedelta
from catalogs.models import Category, Product, ProductBatch


@pytest.fixture
def test_category():
    """Fixture para una categoría de prueba."""
    return Category.objects.create(
        name='Medicamentos Test',
        description='Categoría para tests de lotes'
    )


@pytest.fixture
def test_products(test_category):
    """Fixture para productos de prueba."""
    # Producto que requiere control de lotes
    batch_product = Product.objects.create(
        sku='MED-ANE-LID-001',
        name='Anestesia Lidocaína',
        description='Anestesia con fecha de vencimiento',
        unit='ampolla',
        category=test_category,
        requires_batch_control=True
    )
    
    # Producto que NO requiere control de lotes
    no_batch_product = Product.objects.create(
        sku='EQU-FOR-ESP-001',
        name='Fórceps Espátula',
        description='Instrumento que no vence',
        unit='unidad',
        category=test_category,
        requires_batch_control=False
    )
    
    return {
        'batch_product': batch_product,
        'no_batch_product': no_batch_product
    }


@pytest.mark.django_db
class TestProductBatch:
    """Tests para el modelo ProductBatch."""

    def test_create_product_batch(self, test_products):
        """Test crear un lote básico."""
        batch = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024001',
            manufacturing_date=date(2024, 1, 15),
            expiry_date=date(2026, 1, 15),
            supplier_reference='PROV-REF-001',
            notes='Lote en condiciones óptimas'
        )
        
        assert batch.product == test_products['batch_product']
        assert batch.batch_number == 'LOT2024001'
        assert batch.manufacturing_date == date(2024, 1, 15)
        assert batch.expiry_date == date(2026, 1, 15)
        assert batch.supplier_reference == 'PROV-REF-001'
        assert str(batch) == f"{test_products['batch_product'].name} - Lote: LOT2024001 (Vence: 2026-01-15)"

    def test_batch_unique_constraint(self, test_products):
        """Test que no se pueden duplicar números de lote para el mismo producto."""
        # Crear el primer lote
        ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024001',
            expiry_date=date(2026, 1, 15)
        )
        
        # Intentar crear un duplicado
        with pytest.raises(IntegrityError):
            ProductBatch.objects.create(
                product=test_products['batch_product'],
                batch_number='LOT2024001',  # Mismo número de lote
                expiry_date=date(2026, 2, 15)
            )

    def test_batch_for_non_batch_product_fails(self, test_products):
        """Test que no se puede crear lote para producto que no requiere control de lotes."""
        with pytest.raises(ValidationError) as exc_info:
            batch = ProductBatch(
                product=test_products['no_batch_product'],  # Producto sin control de lotes
                batch_number='LOT2024001',
                expiry_date=date(2026, 1, 15)
            )
            batch.full_clean()
        
        assert "Este producto no requiere control de lotes" in str(exc_info.value)

    def test_manufacturing_date_after_expiry_fails(self, test_products):
        """Test que la fecha de fabricación debe ser anterior a la de vencimiento."""
        with pytest.raises(ValidationError) as exc_info:
            batch = ProductBatch(
                product=test_products['batch_product'],
                batch_number='LOT2024001',
                manufacturing_date=date(2026, 1, 15),  # Después del vencimiento
                expiry_date=date(2025, 1, 15)
            )
            batch.full_clean()
        
        assert "La fecha de fabricación debe ser anterior a la fecha de vencimiento" in str(exc_info.value)

    def test_is_expired_property(self, test_products):
        """Test de la propiedad is_expired."""
        # Lote expirado
        expired_batch = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2020001',
            expiry_date=date(2020, 1, 15)  # Fecha pasada
        )
        
        # Lote válido
        valid_batch = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2030001',
            expiry_date=date(2030, 1, 15)  # Fecha futura
        )
        
        assert expired_batch.is_expired == True
        assert valid_batch.is_expired == False

    def test_days_to_expiry_property(self, test_products):
        """Test de la propiedad days_to_expiry."""
        today = timezone.now().date()
        
        # Lote que vence en 30 días
        future_batch = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024FUTURE',
            expiry_date=today + timedelta(days=30)
        )
        
        # Lote que venció hace 10 días
        past_batch = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024PAST',
            expiry_date=today - timedelta(days=10)
        )
        
        assert future_batch.days_to_expiry == 30
        assert past_batch.days_to_expiry == -10

    def test_batch_minimal_fields(self, test_products):
        """Test crear lote solo con campos obligatorios."""
        batch = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024MIN',
            expiry_date=date(2026, 1, 15)
        )

        assert batch.product == test_products['batch_product']
        assert batch.batch_number == 'LOT2024MIN'
        assert batch.expiry_date == date(2026, 1, 15)
        assert batch.manufacturing_date is None
        assert batch.supplier_reference is None
        assert batch.notes is None

    def test_batch_different_products_same_number(self, test_products):
        """Test que productos diferentes pueden tener el mismo número de lote."""
        # Crear otro producto que requiere lotes
        another_product = Product.objects.create(
            sku='MED-ANE-ART-001',
            name='Anestesia Articaína',
            unit='ampolla',
            category=test_products['batch_product'].category,
            requires_batch_control=True
        )
        
        # Crear lotes con el mismo número pero diferentes productos
        batch1 = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024001',
            expiry_date=date(2026, 1, 15)
        )
        
        batch2 = ProductBatch.objects.create(
            product=another_product,
            batch_number='LOT2024001',  # Mismo número de lote
            expiry_date=date(2026, 1, 15)
        )
        
        # Debe funcionar sin problemas
        assert batch1.batch_number == batch2.batch_number
        assert batch1.product != batch2.product


@pytest.mark.django_db
class TestProductBatchIntegration:
    """Tests de integración para ProductBatch."""

    def test_product_batches_relationship(self, test_products):
        """Test de la relación entre Product y ProductBatch."""
        # Crear varios lotes para el mismo producto
        batch1 = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024001',
            expiry_date=date(2026, 1, 15)
        )
        
        batch2 = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024002',
            expiry_date=date(2026, 2, 15)
        )
        
        # Test de la relación
        batches = test_products['batch_product'].batches.all()
        assert batches.count() == 2
        assert batch1 in batches
        assert batch2 in batches
        
        # Producto sin lotes no debe tener ninguno
        assert test_products['no_batch_product'].batches.count() == 0

    def test_batch_ordering(self, test_products):
        """Test que los lotes se ordenan por fecha de vencimiento."""
        # Crear lotes con diferentes fechas de vencimiento
        batch_far = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024FAR',
            expiry_date=date(2027, 1, 15)
        )
        
        batch_near = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024NEAR',
            expiry_date=date(2025, 1, 15)
        )
        
        batch_middle = ProductBatch.objects.create(
            product=test_products['batch_product'],
            batch_number='LOT2024MID',
            expiry_date=date(2026, 1, 15)
        )
        
        # Los lotes deben estar ordenados por fecha de vencimiento
        ordered_batches = ProductBatch.objects.all()
        assert list(ordered_batches) == [batch_near, batch_middle, batch_far] 