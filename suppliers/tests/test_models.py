import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from suppliers.models import Supplier, PurchaseOption
from catalogs.models import Category, Product


@pytest.fixture
def supplier_data():
    """
    Fixture con datos de muestra para crear proveedores.
    """
    return {
        'name': 'Dental Supplies Inc.',
        'contact_name': 'Juan Pérez',
        'phone': '+1-555-0123',
        'email': 'contacto@dentalsupplies.com'
    }


@pytest.fixture
def category():
    """
    Fixture que crea una categoría de muestra.
    """
    return Category.objects.create(
        name='Instrumental Dental',
        description='Herramientas dentales'
    )


@pytest.fixture
def product(category):
    """
    Fixture que crea un producto de muestra.
    """
    return Product.objects.create(
        sku='INS-DEN-JER-001',
        name='Jeringa Dental',
        description='Jeringa para procedimientos dentales',
        unit='unidad',
        category=category
    )


@pytest.fixture
def supplier():
    """
    Fixture que crea un proveedor de muestra.
    """
    return Supplier.objects.create(
        name='Dental Supplies Inc.',
        contact_name='Juan Pérez',
        email='contacto@dentalsupplies.com'
    )


@pytest.fixture
def purchase_option_data(product, supplier):
    """
    Fixture con datos de muestra para crear opciones de compra.
    """
    return {
        'product': product,
        'supplier': supplier,
        'brand': 'DentalTech',
        'purchase_price': Decimal('20.00'),
        'valid_from': date.today(),
        'valid_to': date.today() + timedelta(days=90)
    }


# Tests para el modelo Supplier

@pytest.mark.django_db
def test_create_supplier_with_all_fields(supplier_data):
    """
    Test para crear un proveedor con todos los campos.
    """
    supplier = Supplier.objects.create(**supplier_data)
    
    assert supplier.id is not None
    assert supplier.name == supplier_data['name']
    assert supplier.contact_name == supplier_data['contact_name']
    assert supplier.phone == supplier_data['phone']
    assert supplier.email == supplier_data['email']
    assert supplier.created_at is not None
    assert supplier.updated_at is not None


@pytest.mark.django_db
def test_create_supplier_with_required_fields_only():
    """
    Test para crear un proveedor solo con campos requeridos.
    """
    supplier = Supplier.objects.create(name='Minimal Supplier')
    
    assert supplier.name == 'Minimal Supplier'
    assert supplier.contact_name is None
    assert supplier.phone is None
    assert supplier.email is None


@pytest.mark.django_db
def test_supplier_str_representation():
    """
    Test para la representación string del proveedor.
    """
    supplier = Supplier.objects.create(name='Test Supplier')
    assert str(supplier) == 'Test Supplier'


@pytest.mark.django_db
def test_supplier_ordering():
    """
    Test para verificar el ordenamiento por defecto de proveedores.
    """
    Supplier.objects.create(name='Zebra Supplies')
    Supplier.objects.create(name='Alpha Dental')
    Supplier.objects.create(name='Beta Medical')
    
    suppliers = list(Supplier.objects.all())
    supplier_names = [s.name for s in suppliers]
    
    assert supplier_names == ['Alpha Dental', 'Beta Medical', 'Zebra Supplies']


@pytest.mark.django_db
def test_supplier_email_validation():
    """
    Test para validar el formato de email.
    """
    supplier = Supplier(
        name='Test Supplier',
        email='invalid-email'
    )
    
    with pytest.raises(ValidationError):
        supplier.full_clean()


@pytest.mark.django_db
def test_supplier_max_length_validation():
    """
    Test para validar longitud máxima de campos.
    """
    # Test name max_length=200
    supplier = Supplier(name='x' * 201)
    with pytest.raises(ValidationError):
        supplier.full_clean()
    
    # Test contact_name max_length=100
    supplier = Supplier(
        name='Valid Name',
        contact_name='x' * 101
    )
    with pytest.raises(ValidationError):
        supplier.full_clean()
    
    # Test phone max_length=20
    supplier = Supplier(
        name='Valid Name',
        phone='x' * 21
    )
    with pytest.raises(ValidationError):
        supplier.full_clean()
    
    # Test email max_length=100
    # Crear un email que sea más largo que 100 caracteres pero mantenga formato válido
    long_email = 'x' * 85 + '@example.com'  # Total 96 chars, válido
    supplier = Supplier(
        name='Valid Name',
        email=long_email
    )
    # Este debería pasar
    supplier.full_clean()
    
    # Ahora probar uno que realmente exceda los 100 caracteres
    very_long_email = 'x' * 90 + '@example.com'  # Total 101 chars
    supplier = Supplier(
        name='Valid Name',
        email=very_long_email
    )
    with pytest.raises(ValidationError):
        supplier.full_clean()


# Tests para el modelo PurchaseOption

@pytest.mark.django_db
def test_create_purchase_option_with_all_fields(purchase_option_data):
    """
    Test para crear una opción de compra con todos los campos.
    """
    option = PurchaseOption.objects.create(**purchase_option_data)
    
    assert option.id is not None
    assert option.product == purchase_option_data['product']
    assert option.supplier == purchase_option_data['supplier']
    assert option.brand == 'DentalTech'
    assert option.purchase_price == Decimal('20.00')
    assert option.valid_from == date.today()
    assert option.valid_to == date.today() + timedelta(days=90)
    assert option.created_at is not None


@pytest.mark.django_db
def test_create_purchase_option_without_valid_to(product, supplier):
    """
    Test para crear una opción de compra sin fecha de vencimiento.
    """
    data = {
        'product': product,
        'supplier': supplier,
        'brand': 'DentalTech',
        'purchase_price': Decimal('20.00'),
        'valid_from': date.today()
    }
    
    option = PurchaseOption.objects.create(**data)
    assert option.valid_to is None


@pytest.mark.django_db
def test_purchase_option_str_representation(product, supplier):
    """
    Test para la representación string de la opción de compra.
    """
    option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='DentalTech',
        purchase_price=Decimal('20.00'),
        valid_from=date.today()
    )
    expected_str = f"{product.name} - {supplier.name} (DentalTech)"
    assert str(option) == expected_str


@pytest.mark.django_db
def test_is_currently_valid_method_with_valid_to(product, supplier):
    """
    Test para el método is_currently_valid con fecha de vencimiento.
    """
    # Opción válida (fechas actuales)
    option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='DentalTech',
        purchase_price=Decimal('20.00'),
        valid_from=date.today(),
        valid_to=date.today() + timedelta(days=90)
    )
    assert option.is_currently_valid() is True
    
    # Opción no válida (fecha futura)
    option.valid_from = date.today() + timedelta(days=10)
    option.save()
    assert option.is_currently_valid() is False
    
    # Opción expirada
    option.valid_from = date.today() - timedelta(days=100)
    option.valid_to = date.today() - timedelta(days=10)
    option.save()
    assert option.is_currently_valid() is False


@pytest.mark.django_db
def test_is_currently_valid_method_without_valid_to(product, supplier):
    """
    Test para el método is_currently_valid sin fecha de vencimiento.
    """
    # Opción válida sin fecha de vencimiento
    option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='DentalTech',
        purchase_price=Decimal('20.00'),
        valid_from=date.today()
    )
    assert option.is_currently_valid() is True
    
    # Opción no válida (fecha futura)
    option.valid_from = date.today() + timedelta(days=10)
    option.save()
    assert option.is_currently_valid() is False


@pytest.mark.django_db
def test_purchase_option_ordering(category, supplier):
    """
    Test para verificar el ordenamiento por defecto de opciones de compra.
    El ordenamiento es: ['product__name', 'supplier__name', '-valid_from']
    """
    # Crear productos
    product1 = Product.objects.create(
        sku='INS-DEN-JER-001',
        name='Jeringa Dental',
        description='Jeringa para procedimientos',
        unit='unidad',
        category=category
    )
    
    product2 = Product.objects.create(
        sku='MAT-DEN-AMA-001',
        name='Amalgama Dental',
        description='Material de amalgama',
        unit='caja',
        category=category
    )
    
    # Crear opciones con diferentes fechas
    option1 = PurchaseOption.objects.create(
        product=product1,  # Jeringa Dental
        supplier=supplier,
        brand='Brand A',
        purchase_price=Decimal('20.00'),
        valid_from=date.today() - timedelta(days=10)
    )
    
    option2 = PurchaseOption.objects.create(
        product=product2,  # Amalgama Dental
        supplier=supplier,
        brand='Brand B',
        purchase_price=Decimal('15.00'),
        valid_from=date.today()
    )
    
    option3 = PurchaseOption.objects.create(
        product=product1,  # Jeringa Dental
        supplier=supplier,
        brand='Brand C',
        purchase_price=Decimal('22.00'),
        valid_from=date.today() + timedelta(days=5)
    )
    
    options = list(PurchaseOption.objects.all())
    
    # Verificar ordenamiento: product__name, supplier__name, -valid_from
    # 1. Amalgama Dental viene antes que Jeringa Dental (alfabético)
    # 2. Para mismo producto y proveedor, fecha más reciente primero
    assert options[0] == option2  # Amalgama Dental
    assert options[1] == option3  # Jeringa Dental (fecha más reciente)
    assert options[2] == option1  # Jeringa Dental (fecha más antigua)


@pytest.mark.django_db
def test_purchase_option_unique_together_constraint(purchase_option_data):
    """
    Test para la restricción unique_together.
    """
    # Crear primera opción
    PurchaseOption.objects.create(**purchase_option_data)
    
    # Intentar crear opción duplicada
    with pytest.raises(IntegrityError):
        PurchaseOption.objects.create(**purchase_option_data)


@pytest.mark.django_db
def test_purchase_option_decimal_precision(product, supplier):
    """
    Test para verificar la precisión de decimales en purchase_price.
    """
    option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Test Brand',
        purchase_price=Decimal('123456789.99'),
        valid_from=date.today()
    )
    
    assert option.purchase_price == Decimal('123456789.99')


@pytest.mark.django_db
def test_purchase_option_relationships(product, supplier):
    """
    Test para verificar las relaciones con otros modelos.
    """
    option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='DentalTech',
        purchase_price=Decimal('20.00'),
        valid_from=date.today()
    )
    
    # Verificar relación con producto
    assert option.product == product
    assert option in product.purchase_options.all()
    
    # Verificar relación con proveedor
    assert option.supplier == supplier
    assert option in supplier.purchase_options.all()


@pytest.mark.django_db
def test_cascade_delete_product(product, supplier):
    """
    Test para verificar que las opciones se eliminan cuando se elimina el producto.
    """
    option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='DentalTech',
        purchase_price=Decimal('20.00'),
        valid_from=date.today()
    )
    option_id = option.id
    
    # Eliminar producto
    product.delete()
    
    # Verificar que la opción también se eliminó
    assert not PurchaseOption.objects.filter(id=option_id).exists()


@pytest.mark.django_db
def test_cascade_delete_supplier(product, supplier):
    """
    Test para verificar que las opciones se eliminan cuando se elimina el proveedor.
    """
    option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='DentalTech',
        purchase_price=Decimal('20.00'),
        valid_from=date.today()
    )
    option_id = option.id
    
    # Eliminar proveedor
    supplier.delete()
    
    # Verificar que la opción también se eliminó
    assert not PurchaseOption.objects.filter(id=option_id).exists()


@pytest.mark.django_db
def test_default_valid_from_value(product, supplier):
    """
    Test para verificar el valor por defecto de valid_from.
    """
    option = PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='Test Brand',
        purchase_price=Decimal('20.00')
        # No especificamos valid_from
    )
    
    assert option.valid_from == timezone.localdate() 