import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def sample_user():
    """
    Fixture que crea un usuario de muestra para los tests.
    """
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def api_client():
    """
    Fixture que proporciona un cliente API básico.
    """
    return APIClient()


@pytest.fixture
def authenticated_api_client(sample_user):
    """
    Fixture que proporciona un cliente API autenticado.
    """
    client = APIClient()
    client.force_authenticate(user=sample_user)
    return client 