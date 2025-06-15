import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from catalogs.models import Category, Product, ProductComponent


@pytest.fixture
def test_category():
    """Fixture para una categoría de prueba."""
    return Category.objects.create(
        name='Medicamentos Test',
        description='Categoría para tests de productos compuestos'
    )


@pytest.fixture
def test_products(test_category):
    """Fixture para productos de prueba."""
    # Producto compuesto (caja)
    composite_product = Product.objects.create(
        sku='MED-CAJ-IBU-001',
        name='Caja de Ibuprofeno',
        description='Caja con 10 blisters de ibuprofeno',
        unit='caja',
        category=test_category,
        product_type='composite'
    )
    
    # Producto componente (blister)
    component_product = Product.objects.create(
        sku='MED-BLI-IBU-001',
        name='Blister Ibuprofeno',
        description='Blister individual de ibuprofeno',
        unit='blister',
        category=test_category,
        product_type='component'
    )
    
    # Producto simple (no compuesto)
    simple_product = Product.objects.create(
        sku='MED-SIM-ASP-001',
        name='Aspirina Simple',
        description='Producto simple de aspirina',
        unit='unidad',
        category=test_category,
        product_type='simple'
    )
    
    return {
        'composite': composite_product,
        'component': component_product,
        'simple': simple_product
    }


@pytest.mark.django_db
class TestProductComponent:
    """Tests para el modelo ProductComponent."""

    def test_create_product_component(self, test_products):
        """Test crear un componente de producto básico."""
        component = ProductComponent.objects.create(
            composite_product=test_products['composite'],
            component_product=test_products['component'],
            quantity=10
        )
        
        assert component.composite_product == test_products['composite']
        assert component.component_product == test_products['component']
        assert component.quantity == 10
        assert str(component) == f"{test_products['composite'].name} contiene 10x {test_products['component'].name}"

    def test_cannot_be_component_of_itself(self, test_products):
        """Test que un producto no puede ser componente de sí mismo."""
        with pytest.raises(ValidationError) as exc_info:
            component = ProductComponent(
                composite_product=test_products['composite'],
                component_product=test_products['composite'],  # Mismo producto
                quantity=1
            )
            component.full_clean()
        
        assert "Un producto no puede ser componente de sí mismo" in str(exc_info.value)

    def test_composite_product_must_be_composite_type(self, test_products):
        """Test que el producto padre debe ser de tipo 'composite'."""
        with pytest.raises(ValidationError) as exc_info:
            component = ProductComponent(
                composite_product=test_products['simple'],  # Producto simple, no compuesto
                component_product=test_products['component'],
                quantity=1
            )
            component.full_clean()
        
        assert "El producto padre debe ser de tipo 'Compuesto/Kit'" in str(exc_info.value)

    def test_component_cannot_be_composite(self, test_products):
        """Test que un producto compuesto no puede ser componente de otro."""
        # Crear otro producto compuesto
        another_composite = Product.objects.create(
            sku='MED-CAJ-ASP-001',
            name='Caja de Aspirina',
            unit='caja',
            category=test_products['composite'].category,
            product_type='composite'
        )
        
        with pytest.raises(ValidationError) as exc_info:
            component = ProductComponent(
                composite_product=another_composite,
                component_product=test_products['composite'],  # Un compuesto como componente
                quantity=1
            )
            component.full_clean()
        
        assert "Un producto compuesto no puede ser componente de otro" in str(exc_info.value)

    def test_unique_constraint(self, test_products):
        """Test que no se pueden duplicar componentes para el mismo producto compuesto."""
        # Crear el primer componente
        ProductComponent.objects.create(
            composite_product=test_products['composite'],
            component_product=test_products['component'],
            quantity=10
        )
        
        # Intentar crear un duplicado
        with pytest.raises(IntegrityError):
            ProductComponent.objects.create(
                composite_product=test_products['composite'],
                component_product=test_products['component'],  # Mismo componente
                quantity=5
            )


@pytest.mark.django_db
class TestProductMethods:
    """Tests para los métodos del modelo Product relacionados con componentes."""

    def test_is_composite_method(self, test_products):
        """Test del método is_composite()."""
        assert test_products['composite'].is_composite() == True
        assert test_products['component'].is_composite() == False
        assert test_products['simple'].is_composite() == False

    def test_is_component_method(self, test_products):
        """Test del método is_component()."""
        assert test_products['composite'].is_component() == False
        assert test_products['component'].is_component() == True
        assert test_products['simple'].is_component() == False

    def test_get_components(self, test_products):
        """Test del método get_components()."""
        # Crear componentes
        component1 = ProductComponent.objects.create(
            composite_product=test_products['composite'],
            component_product=test_products['component'],
            quantity=10
        )
        
        # Crear otro componente
        another_component = Product.objects.create(
            sku='MED-BLI-DOL-001',
            name='Blister Dolex',
            unit='blister',
            category=test_products['composite'].category,
            product_type='component'
        )
        
        component2 = ProductComponent.objects.create(
            composite_product=test_products['composite'],
            component_product=another_component,
            quantity=5
        )
        
        # Test
        components = test_products['composite'].get_components()
        assert components.count() == 2
        assert component1 in components
        assert component2 in components
        
        # Producto no compuesto no debe tener componentes
        assert test_products['simple'].get_components().count() == 0

    def test_get_parent_kits(self, test_products):
        """Test del método get_parent_kits()."""
        # Crear relación
        component_relation = ProductComponent.objects.create(
            composite_product=test_products['composite'],
            component_product=test_products['component'],
            quantity=10
        )
        
        # Test
        parent_kits = test_products['component'].get_parent_kits()
        assert parent_kits.count() == 1
        assert component_relation in parent_kits
        
        # Producto compuesto no debe ser componente de otros
        assert test_products['composite'].get_parent_kits().count() == 0 