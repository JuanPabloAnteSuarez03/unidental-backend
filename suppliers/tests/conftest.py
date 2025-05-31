import pytest
from datetime import date, timedelta
from decimal import Decimal

from suppliers.models import Supplier, PurchaseOption
from catalogs.models import Category, Product


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
        phone='+1-555-0123',
        email='contacto@dentalsupplies.com'
    )


@pytest.fixture
def purchase_option(product, supplier):
    """
    Fixture que crea una opción de compra de muestra.
    """
    return PurchaseOption.objects.create(
        product=product,
        supplier=supplier,
        brand='DentalTech',
        purchase_price=Decimal('20.00'),
        valid_from=date.today(),
        valid_to=date.today() + timedelta(days=90)
    ) 