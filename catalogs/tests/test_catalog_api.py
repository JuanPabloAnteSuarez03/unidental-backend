import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from catalogs.models import Category, Product
from catalogs.serializers import CategorySerializer, ProductSerializer # Para comparar datos

User = get_user_model()

@pytest.fixture
def api_client_authenticated():
    """Fixture para un cliente API autenticado."""
    client = APIClient()
    user_data = {
        'username': 'testauthuser_catalog',
        'password': 'Str0ngP@sswOrd!CAT',
        'email': 'testauthuser_catalog@example.com'
    }
    # Limpiar usuario si existe de una ejecución anterior
    User.objects.filter(username=user_data['username']).delete()
    
    # Registrar usuario (usando las URLs de Djoser si es posible o la URL directa)
    try:
        register_url = reverse('user-list')
    except:
        register_url = "/api/auth/users/"
    client.post(register_url, user_data, format='json')

    # Loguear usuario
    try:
        login_url = reverse('login')
    except:
        login_url = "/api/auth/token/login/"
    login_payload = {'username': user_data['username'], 'password': user_data['password']}
    response = client.post(login_url, login_payload, format='json')
    token = response.data['auth_token']
    client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    return client

@pytest.mark.django_db
class TestCategoryAPI:
    def setup_method(self):
        self.categories_url = reverse('category-list') # DRF router genera 'basename-list'
        # No necesitamos un cliente no autenticado aquí si todas las vistas son protegidas

    def test_create_category_authenticated(self, api_client_authenticated):
        """Prueba la creación de una categoría por un usuario autenticado."""
        payload = {'name': 'Insumos Médicos', 'description': 'Materiales para uso médico general'}
        response = api_client_authenticated.post(self.categories_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert Category.objects.filter(name='Insumos Médicos').exists()
        assert response.data['name'] == payload['name']

    def test_create_category_unauthenticated(self):
        """Prueba que un usuario no autenticado no puede crear una categoría."""
        client = APIClient()
        payload = {'name': 'Test Category Unauth', 'description': 'Desc'}
        response = client.post(self.categories_url, payload, format='json')
        assert response.status_code == 401 # Unauthorized

    def test_create_category_duplicate_name(self, api_client_authenticated):
        """Prueba la creación de una categoría con un nombre duplicado."""
        Category.objects.create(name='Insumos Dentales')
        payload = {'name': 'Insumos Dentales', 'description': 'Otra descripción'}
        response = api_client_authenticated.post(self.categories_url, payload, format='json')
        assert response.status_code == 400, f"Error: {response.data}" # Espera error de validación (nombre único)

    def test_list_categories(self, api_client_authenticated):
        """Prueba obtener la lista de categorías."""
        Category.objects.create(name='Equipamiento Dental', description='Equipos para consultorios')
        Category.objects.create(name='Material de Oficina', description='Papelería y consumibles')
        response = api_client_authenticated.get(self.categories_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert len(response.data) >= 2 # Puede haber otras categorías creadas por otros tests

    def test_retrieve_category(self, api_client_authenticated):
        """Prueba obtener el detalle de una categoría."""
        category = Category.objects.create(name='Ortodoncia', description='Materiales para ortodoncia')
        detail_url = reverse('category-detail', kwargs={'pk': category.pk})
        response = api_client_authenticated.get(detail_url)
        assert response.status_code == 200, f"Error: {response.data}"
        serializer = CategorySerializer(category)
        assert response.data == serializer.data

    def test_update_category(self, api_client_authenticated):
        """Prueba actualizar una categoría (PUT)."""
        category = Category.objects.create(name='Prótesis')
        detail_url = reverse('category-detail', kwargs={'pk': category.pk})
        payload = {'name': 'Prótesis Dentales', 'description': 'Dispositivos protésicos'}
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        category.refresh_from_db()
        assert category.name == 'Prótesis Dentales'
        assert category.description == 'Dispositivos protésicos'

    def test_partial_update_category(self, api_client_authenticated):
        """Prueba actualizar parcialmente una categoría (PATCH)."""
        category = Category.objects.create(name='Endodoncia', description='Materiales endo')
        detail_url = reverse('category-detail', kwargs={'pk': category.pk})
        payload = {'description': 'Materiales y herramientas para tratamientos de conducto'}
        response = api_client_authenticated.patch(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        category.refresh_from_db()
        assert category.description == 'Materiales y herramientas para tratamientos de conducto'

    def test_delete_category(self, api_client_authenticated):
        """Prueba eliminar una categoría."""
        category = Category.objects.create(name='Consumibles Varios')
        detail_url = reverse('category-detail', kwargs={'pk': category.pk})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 204, f"Error: {response.data if response.data else ''}"
        assert not Category.objects.filter(pk=category.pk).exists()

@pytest.mark.django_db
class TestProductAPI:
    def setup_method(self):
        self.products_url = reverse('product-list')
        self.category1 = Category.objects.create(name='Anestésicos', description='Para control del dolor')
        self.product_data = {
            'sku': 'ANEST-LIDO-001',
            'name': 'Lidocaína 2% con Epinefrina',
            'description': 'Cartucho de anestésico local.',
            'unit': 'cartucho',
            'category': self.category1.pk
        }

    def test_create_product_authenticated(self, api_client_authenticated):
        """Prueba la creación de un producto por un usuario autenticado."""
        response = api_client_authenticated.post(self.products_url, self.product_data, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert Product.objects.filter(sku=self.product_data['sku']).exists()
        created_product = Product.objects.get(sku=self.product_data['sku'])
        assert created_product.name == self.product_data['name']
        assert created_product.category.pk == self.product_data['category']

    def test_create_product_unauthenticated(self):
        """Prueba que un usuario no autenticado no puede crear un producto."""
        client = APIClient()
        response = client.post(self.products_url, self.product_data, format='json')
        assert response.status_code == 401 # Unauthorized

    def test_create_product_duplicate_sku(self, api_client_authenticated):
        """Prueba la creación de un producto con SKU duplicado."""
        Product.objects.create(
            sku='SKUDUP001', name='Producto Existente', unit='unidad', category=self.category1
        )
        payload = {
            'sku': 'SKUDUP001', 
            'name': 'Producto Nuevo Mismo SKU', 
            'unit': 'caja', 
            'category': self.category1.pk
        }
        response = api_client_authenticated.post(self.products_url, payload, format='json')
        assert response.status_code == 400, f"Error: {response.data}"

    def test_create_product_nonexistent_category(self, api_client_authenticated):
        """Prueba crear un producto con un ID de categoría que no existe."""
        non_existent_category_id = 9999
        payload = {**self.product_data, 'category': non_existent_category_id, 'sku': 'NEWPRODSKU002'}
        response = api_client_authenticated.post(self.products_url, payload, format='json')
        assert response.status_code == 400, f"Error: {response.data}"
        # DRF devuelve 400 si una FK no es válida.

    def test_list_products(self, api_client_authenticated):
        """Prueba obtener la lista de productos."""
        Product.objects.create(sku='P001', name='Producto A', unit='un', category=self.category1)
        Product.objects.create(sku='P002', name='Producto B', unit='kg', category=self.category1)
        response = api_client_authenticated.get(self.products_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert len(response.data) >= 2
        # Verificar que category_name está en la respuesta
        if len(response.data) > 0:
            assert 'category_name' in response.data[0]
            assert response.data[0]['category_name'] == self.category1.name

    def test_retrieve_product(self, api_client_authenticated):
        """Prueba obtener el detalle de un producto."""
        product = Product.objects.create(**self.product_data)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        response = api_client_authenticated.get(detail_url)
        assert response.status_code == 200, f"Error: {response.data}"
        # Comparar campos clave. Evitar comparar el objeto serializador completo si hay campos dinámicos como updated_at.
        assert response.data['sku'] == product.sku
        assert response.data['name'] == product.name
        assert response.data['category'] == product.category.pk
        assert response.data['category_name'] == product.category.name

    def test_update_product(self, api_client_authenticated):
        """Prueba actualizar un producto (PUT)."""
        product = Product.objects.create(**self.product_data)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        category2 = Category.objects.create(name='Suturas')
        payload = {
            'sku': product.sku, # SKU no debería cambiar o ser manejado con cuidado
            'name': 'Lidocaína 2% Cartucho (Actualizado)',
            'description': 'Descripción actualizada.',
            'unit': 'caja de 50',
            'category': category2.pk
        }
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        product.refresh_from_db()
        assert product.name == 'Lidocaína 2% Cartucho (Actualizado)'
        assert product.unit == 'caja de 50'
        assert product.category == category2

    def test_partial_update_product(self, api_client_authenticated):
        """Prueba actualizar parcialmente un producto (PATCH)."""
        product = Product.objects.create(**self.product_data)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        payload = {'name': 'Lidocaína Cartucho Gold'}
        response = api_client_authenticated.patch(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        product.refresh_from_db()
        assert product.name == 'Lidocaína Cartucho Gold'

    def test_delete_product(self, api_client_authenticated):
        """Prueba eliminar un producto."""
        product = Product.objects.create(**self.product_data)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 204, f"Error: {response.data if response.data else ''}"
        assert not Product.objects.filter(pk=product.pk).exists() 