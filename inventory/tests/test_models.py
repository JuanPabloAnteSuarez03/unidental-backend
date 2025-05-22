import pytest
from inventory.models import MiModelo

@pytest.mark.django_db
def test_str_representation():
    obj = MiModelo.objects.create(nombre="Prueba")
    assert str(obj) == "Prueba"
