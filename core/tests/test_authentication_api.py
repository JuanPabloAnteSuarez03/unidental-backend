import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
class TestAuthenticationAPI:
    def setup_method(self):
        self.client = APIClient()
        # Asegúrate de que los nombres de las URLs coincidan con los que Djoser registra.
        # Puedes verificar esto con `python manage.py show_urls` o revisando la documentación de Djoser.
        # Djoser generalmente registra UserViewSet bajo 'user', y las acciones son 'user-list', 'user-detail', 'user-me'.
        # Las URLs de token suelen ser 'login' y 'logout' si usas djoser.urls.authtoken.
        try:
            self.register_url = reverse('user-list') 
        except Exception:
             # Fallback si 'user-list' no es el nombre exacto para la URL de registro/lista de usuarios de Djoser
            self.register_url = "/api/auth/users/" # Ajusta si tu prefijo es diferente
        
        try:
            self.login_url = reverse('login')
        except Exception:
            self.login_url = "/api/auth/token/login/"

        try:
            self.logout_url = reverse('logout')
        except Exception:
            self.logout_url = "/api/auth/token/logout/"
        
        try:
            self.me_url = reverse('user-me')
        except Exception:
            self.me_url = "/api/auth/users/me/"

        self.user_data = {
            'username': 'testuser_pytest',
            'password': 'Str0ngP@sswOrd!', # Comilla doble corregida
            'email': 'pytestuser@example.com'
        }
        # Limpiar usuario si existe de una ejecución anterior para evitar conflictos
        User.objects.filter(username=self.user_data['username']).delete()

    def test_user_registration_success(self):
        """Prueba el registro exitoso de un usuario."""
        response = self.client.post(self.register_url, self.user_data, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert User.objects.filter(username=self.user_data['username']).exists()
        created_user = User.objects.get(username=self.user_data['username'])
        assert created_user.email == self.user_data['email']

    def test_user_registration_duplicate_username(self):
        """Prueba el registro con un nombre de usuario duplicado."""
        self.client.post(self.register_url, self.user_data, format='json') # Primer registro
        response = self.client.post(self.register_url, self.user_data, format='json') # Intento de duplicado
        assert response.status_code == 400, f"Error: {response.data}"

    def test_user_login_success_and_token_retrieval(self):
        """Prueba el inicio de sesión exitoso y la obtención de un token."""
        self.client.post(self.register_url, self.user_data, format='json')
        login_payload = {'username': self.user_data['username'], 'password': self.user_data['password']}
        response = self.client.post(self.login_url, login_payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        assert 'auth_token' in response.data
        assert response.data['auth_token'] is not None

    def test_user_login_invalid_credentials(self):
        """Prueba el inicio de sesión con credenciales inválidas."""
        login_payload = {'username': self.user_data['username'], 'password': 'wrongpassword'}
        response = self.client.post(self.login_url, login_payload, format='json')
        assert response.status_code == 400, f"Error: {response.data}"

    def test_access_protected_endpoint_with_valid_token(self):
        """Prueba el acceso a un endpoint protegido (/users/me/) con un token válido."""
        self.client.post(self.register_url, self.user_data, format='json')
        login_payload = {'username': self.user_data['username'], 'password': self.user_data['password']}
        login_response = self.client.post(self.login_url, login_payload, format='json')
        token = login_response.data['auth_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get(self.me_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert response.data['username'] == self.user_data['username']

    def test_access_protected_endpoint_without_token(self):
        """Prueba el acceso a /users/me/ sin token (espera 401)."""
        response = self.client.get(self.me_url)
        assert response.status_code == 401, f"Error: {response.data}"

    def test_user_logout_success_and_token_invalidation(self):
        """Prueba el logout exitoso y la invalidación del token."""
        self.client.post(self.register_url, self.user_data, format='json')
        login_payload = {'username': self.user_data['username'], 'password': self.user_data['password']}
        login_response = self.client.post(self.login_url, login_payload, format='json')
        token = login_response.data['auth_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        logout_response = self.client.post(self.logout_url) # No necesita payload ni format='json' para logout de token
        assert logout_response.status_code == 204, f"Error: {logout_response.data if logout_response.data else ''}"
        # Intentar acceder a endpoint protegido con el token invalidado
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}') # Re-autenticar con el mismo token
        response_after_logout = self.client.get(self.me_url)
        assert response_after_logout.status_code == 401, f"Error: {response_after_logout.data}"