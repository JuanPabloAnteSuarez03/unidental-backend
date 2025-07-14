import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from catalogs.models import Category, Product, SkuCategory, SkuSubCategory, SkuType
from catalogs.validators import SKUValidator
from django.core.exceptions import ValidationError

User = get_user_model()

@pytest.fixture
def api_client_authenticated():
    """Fixture para un cliente API autenticado."""
    client = APIClient()
    user_data = {
        'username': 'testauthuser_sku',
        'password': 'Str0ngP@sswOrd!SKU',
        'email': 'testauthuser_sku@example.com'
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

@pytest.fixture
def sample_sku_structure():
    """Fixture que crea una estructura de SKU de ejemplo en la base de datos."""
    # Crear categoría
    category = SkuCategory.objects.create(
        code='LAB',
        name='Laboratorio'
    )
    
    # Crear subcategoría
    subcategory = SkuSubCategory.objects.create(
        category=category,
        code='ART',
        name='Articuladores'
    )
    
    # Crear tipo
    sku_type = SkuType.objects.create(
        subcategory=subcategory,
        code='BIO',
        name='Bio-Art'
    )
    
    return {
        'category': category,
        'subcategory': subcategory,
        'type': sku_type
    }

@pytest.fixture
def sample_product_category():
    """Fixture que crea una categoría de producto de ejemplo."""
    return Category.objects.create(
        name='Equipos de Laboratorio',
        description='Equipos para laboratorio dental'
    )

@pytest.mark.django_db
class TestUpdatedSKUEndpoints:
    """Tests para los endpoints de SKU actualizados que usan la nueva estructura de base de datos."""
    
    def setup_method(self):
        self.sku_info_url = reverse('sku-info')
        self.sku_structure_url = reverse('sku-structure')
        self.generate_sku_url = reverse('generate-sku')
        self.validate_sku_url = reverse('validate-sku')

    def test_sku_info_endpoint_with_db_structure(self, api_client_authenticated, sample_sku_structure):
        """Prueba que el endpoint sku-info devuelve la estructura desde la base de datos."""
        response = api_client_authenticated.get(self.sku_info_url)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verificar estructura básica
        assert 'formato' in data
        assert 'ejemplo' in data
        assert 'categorias' in data
        assert 'subcategorias' in data
        assert 'tipos' in data
        assert 'reglas' in data
        
        assert data['formato'] == 'CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL'
        assert data['ejemplo'] == 'LAB-ART-BIO-001'
        
        # Verificar que contiene los datos de la base de datos
        assert len(data['categorias']) >= 1
        assert len(data['subcategorias']) >= 1
        assert len(data['tipos']) >= 1
        
        # Verificar estructura de categoría
        category_data = data['categorias'][0]
        assert 'id' in category_data
        assert 'code' in category_data
        assert 'name' in category_data
        assert 'subcategorias' in category_data

    def test_sku_structure_endpoint(self, api_client_authenticated, sample_sku_structure):
        """Prueba que el endpoint sku-structure devuelve la estructura simplificada."""
        response = api_client_authenticated.get(self.sku_structure_url)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verificar estructura
        assert 'categorias' in data
        assert 'subcategorias' in data
        assert 'tipos' in data
        
        # Verificar que contiene los datos
        assert len(data['categorias']) >= 1
        assert len(data['subcategorias']) >= 1
        assert len(data['tipos']) >= 1
        
        # Verificar estructura de categoría
        category = data['categorias'][0]
        assert category['code'] == 'LAB'
        assert category['name'] == 'Laboratorio'
        
        # Verificar estructura de subcategoría
        subcategory = data['subcategorias'][0]
        assert subcategory['code'] == 'ART'
        assert subcategory['name'] == 'Articuladores'
        assert subcategory['category_id'] == sample_sku_structure['category'].id
        
        # Verificar estructura de tipo
        sku_type = data['tipos'][0]
        assert sku_type['code'] == 'BIO'
        assert sku_type['name'] == 'Bio-Art'
        assert sku_type['subcategory_id'] == sample_sku_structure['subcategory'].id

    def test_generate_sku_endpoint_with_ids(self, api_client_authenticated, sample_sku_structure, sample_product_category):
        """Prueba la generación de SKU usando IDs de la base de datos."""
        payload = {
            'category_id': sample_sku_structure['category'].id,
            'subcategory_id': sample_sku_structure['subcategory'].id,
            'type_id': sample_sku_structure['type'].id
        }
        
        response = api_client_authenticated.post(self.generate_sku_url, payload, format='json')
        
        assert response.status_code == 200
        data = response.json()
        
        # Verificar estructura de respuesta
        assert 'sku_sugerido' in data
        assert 'categoria_nombre' in data
        assert 'subcategoria_nombre' in data
        assert 'tipo_nombre' in data
        
        # Verificar que el SKU generado tiene el formato correcto
        assert data['sku_sugerido'] == 'LAB-ART-BIO-001'
        assert data['categoria_nombre'] == 'Laboratorio'
        assert data['subcategoria_nombre'] == 'Articuladores'
        assert data['tipo_nombre'] == 'Bio-Art'

    def test_generate_sku_with_existing_products(self, api_client_authenticated, sample_sku_structure, sample_product_category):
        """Prueba la generación de SKU cuando ya existen productos con SKUs similares."""
        # Crear un producto con SKU existente
        Product.objects.create(
            sku='LAB-ART-BIO-001',
            name='Producto Test',
            unit='unidad',
            category=sample_product_category
        )
        
        payload = {
            'category_id': sample_sku_structure['category'].id,
            'subcategory_id': sample_sku_structure['subcategory'].id,
            'type_id': sample_sku_structure['type'].id
        }
        
        response = api_client_authenticated.post(self.generate_sku_url, payload, format='json')
        
        assert response.status_code == 200
        data = response.json()
        
        # Debería generar el siguiente SKU disponible
        assert data['sku_sugerido'] == 'LAB-ART-BIO-002'

    def test_generate_sku_invalid_category_id(self, api_client_authenticated):
        """Prueba la generación de SKU con ID de categoría inválido."""
        payload = {
            'category_id': 99999,  # ID inexistente
            'subcategory_id': 1,
            'type_id': 1
        }
        
        response = api_client_authenticated.post(self.generate_sku_url, payload, format='json')
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'categoría con ID 99999 no existe' in data['error']

    def test_generate_sku_invalid_subcategory_id(self, api_client_authenticated, sample_sku_structure):
        """Prueba la generación de SKU con ID de subcategoría inválido."""
        payload = {
            'category_id': sample_sku_structure['category'].id,
            'subcategory_id': 99999,  # ID inexistente
            'type_id': sample_sku_structure['type'].id
        }
        
        response = api_client_authenticated.post(self.generate_sku_url, payload, format='json')
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'subcategoría con ID 99999 no existe' in data['error']

    def test_generate_sku_missing_parameters(self, api_client_authenticated):
        """Prueba la generación de SKU con parámetros faltantes."""
        payload = {
            'category_id': 1,
            # Faltan subcategory_id y type_id
        }
        
        response = api_client_authenticated.post(self.generate_sku_url, payload, format='json')
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'Se requieren category_id, subcategory_id y type_id' in data['error']

    def test_validate_sku_endpoint_valid(self, api_client_authenticated, sample_sku_structure):
        """Prueba la validación de un SKU válido."""
        payload = {'sku': 'LAB-ART-BIO-001'}
        
        response = api_client_authenticated.post(self.validate_sku_url, payload, format='json')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['valido'] is True
        assert data['disponible'] is True
        assert 'válido y está disponible' in data['mensaje']

    def test_validate_sku_endpoint_exists(self, api_client_authenticated, sample_sku_structure, sample_product_category):
        """Prueba la validación de un SKU que ya existe."""
        # Crear producto con el SKU
        Product.objects.create(
            sku='LAB-ART-BIO-001',
            name='Producto Existente',
            unit='unidad',
            category=sample_product_category
        )
        
        payload = {'sku': 'LAB-ART-BIO-001'}
        
        response = api_client_authenticated.post(self.validate_sku_url, payload, format='json')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['valido'] is True
        assert data['disponible'] is False
        assert 'válido pero ya existe' in data['mensaje']

    def test_validate_sku_endpoint_invalid_format(self, api_client_authenticated):
        """Prueba la validación de un SKU con formato inválido."""
        payload = {'sku': 'INVALID-SKU'}
        
        response = api_client_authenticated.post(self.validate_sku_url, payload, format='json')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['valido'] is False
        assert data['disponible'] is False
        assert 'formato' in data['mensaje'].lower()

    def test_validate_sku_endpoint_nonexistent_components(self, api_client_authenticated):
        """Prueba la validación de un SKU con componentes que no existen en la BD."""
        payload = {'sku': 'XXX-YYY-ZZZ-001'}
        
        response = api_client_authenticated.post(self.validate_sku_url, payload, format='json')
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['valido'] is False
        assert data['disponible'] is False
        assert 'no existe' in data['mensaje']

    def test_validate_sku_endpoint_missing_sku(self, api_client_authenticated):
        """Prueba la validación sin proporcionar el SKU."""
        payload = {}
        
        response = api_client_authenticated.post(self.validate_sku_url, payload, format='json')
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'Se requiere el campo sku' in data['error']

    def test_endpoints_unauthenticated(self):
        """Prueba que los endpoints requieren autenticación."""
        client = APIClient()
        
        endpoints = [
            self.sku_info_url,
            self.sku_structure_url,
            self.generate_sku_url,
            self.validate_sku_url
        ]
        
        for endpoint in endpoints:
            if endpoint in [self.generate_sku_url, self.validate_sku_url]:
                response = client.post(endpoint, {}, format='json')
            else:
                response = client.get(endpoint)
            
            assert response.status_code == 401 