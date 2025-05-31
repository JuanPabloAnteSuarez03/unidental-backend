import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from catalogs.models import Category, Product
from catalogs.serializers import CategorySerializer, ProductSerializer
from catalogs.validators import SKUValidator
from django.core.exceptions import ValidationError

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
        self.categories_url = reverse('category-list')

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
        assert response.status_code == 401

    def test_create_category_duplicate_name(self, api_client_authenticated):
        """Prueba la creación de una categoría con un nombre duplicado."""
        Category.objects.create(name='Insumos Dentales')
        payload = {'name': 'Insumos Dentales', 'description': 'Otra descripción'}
        response = api_client_authenticated.post(self.categories_url, payload, format='json')
        assert response.status_code == 400, f"Error: {response.data}"

    def test_list_categories(self, api_client_authenticated):
        """Prueba obtener la lista de categorías."""
        Category.objects.create(name='Equipamiento Dental-TEST', description='Equipos para consultorios')
        Category.objects.create(name='Material de Oficina-TEST', description='Papelería y consumibles')
        response = api_client_authenticated.get(self.categories_url)
        assert response.status_code == 200, f"Error: {response.data}"
        test_categories_in_response = [cat for cat in response.data['results'] if isinstance(cat, dict) and cat.get('name', '').endswith('-TEST')]
        assert len(test_categories_in_response) >= 2

    def test_category_pagination(self, api_client_authenticated):
        """Prueba la paginación para la lista de categorías."""
        # Crear 30 categorías para asegurar que la paginación funcione (PAGE_SIZE es 25)
        for i in range(30):
            Category.objects.create(name=f'Categoria Paginada {i}-TEST', description=f'Desc {i}')
        
        response = api_client_authenticated.get(self.categories_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert 'results' in response.data
        
        # Con PAGE_SIZE=25, debe devolver 25 items en la primera página
        assert len(response.data['results']) == 25
        assert response.data['count'] >= 30
        assert response.data['next'] is not None
        assert response.data['previous'] is None

    def test_filter_category_by_name(self, api_client_authenticated):
        """Prueba filtrar categorías por nombre."""
        Category.objects.create(name='FiltroNombreExacto-TEST', description='Para test de filtro exacto')
        Category.objects.create(name='FiltroNombreParcialUno-TEST', description='Para test de filtro parcial')
        Category.objects.create(name='FiltroNombreParcialDos-TEST', description='Otro para test de filtro parcial')
        Category.objects.create(name='OtraCategoriaSinFiltro-TEST', description='No debe aparecer')

        response = api_client_authenticated.get(self.categories_url, {'name': 'FiltroNombreExacto-TEST'})
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'FiltroNombreExacto-TEST'

        response = api_client_authenticated.get(self.categories_url, {'name': 'FiltroNombreParcial'})
        assert response.status_code == 200
        assert len(response.data['results']) == 2

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
        self.category1 = Category.objects.create(name='Anestésicos Test', description='Para control del dolor en tests')
        
        # Limpiar productos con SKUs de test
        Product.objects.filter(sku__contains='TEST').delete()
        
        # Datos de producto usando el nuevo formato de SKU
        self.product_data_dict_for_api = {
            'sku': 'ANE-CAR-SEP-001',
            'barcode': '3182818282827',
            'name': 'ANESTESIA SEPTODONT 1/100.000',
            'description': 'Cartucho de anestesia con epinefrina 1:100.000 para procedimientos odontológicos.',
            'unit': 'caja',
            'category': self.category1.pk
        }
        
        self.product_data_for_model_creation = {
            'sku': 'ANE-CAR-SEP-001',
            'barcode': '3182818282827',
            'name': 'ANESTESIA SEPTODONT 1/100.000',
            'description': 'Cartucho de anestesia con epinefrina 1:100.000 para procedimientos odontológicos.',
            'unit': 'caja',
            'category': self.category1
        }

    def test_create_product_authenticated(self, api_client_authenticated):
        """Prueba la creación de un producto por un usuario autenticado."""
        response = api_client_authenticated.post(self.products_url, self.product_data_dict_for_api, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert Product.objects.filter(sku=self.product_data_dict_for_api['sku']).exists()
        created_product = Product.objects.get(sku=self.product_data_dict_for_api['sku'])
        assert created_product.name == self.product_data_dict_for_api['name']
        assert created_product.barcode == self.product_data_dict_for_api['barcode']
        assert created_product.category.pk == self.product_data_dict_for_api['category']

    def test_create_product_with_barcode(self, api_client_authenticated):
        """Prueba la creación de un producto con código de barras."""
        payload = {
            'sku': 'LAB-ART-BIO-001',
            'barcode': '7891234567890',
            'name': 'ARTICULADOR BIO-ART',
            'description': 'Articulador semiajustable para laboratorio dental',
            'unit': 'unidad',
            'category': self.category1.pk
        }
        response = api_client_authenticated.post(self.products_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert response.data['barcode'] == payload['barcode']
        created_product = Product.objects.get(sku=payload['sku'])
        assert created_product.barcode == payload['barcode']

    def test_create_product_without_barcode(self, api_client_authenticated):
        """Prueba la creación de un producto sin código de barras (opcional)."""
        payload = {
            'sku': 'RES-ADH-M3M-001',
            'name': 'Adhesivo 3M Universal 5ML',
            'description': 'Adhesivo universal para restauraciones',
            'unit': 'unidad',
            'category': self.category1.pk
        }
        response = api_client_authenticated.post(self.products_url, payload, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert response.data['barcode'] is None or response.data['barcode'] == ''

    def test_create_product_invalid_sku_format(self, api_client_authenticated):
        """Prueba crear un producto con SKU inválido."""
        payload = {
            'sku': 'INVALID-SKU',
            'name': 'Producto con SKU inválido',
            'unit': 'unidad',
            'category': self.category1.pk
        }
        response = api_client_authenticated.post(self.products_url, payload, format='json')
        assert response.status_code == 400, f"Error: {response.data}"

    def test_create_product_invalid_category(self, api_client_authenticated):
        """Prueba crear un producto con categoría inválida en el SKU."""
        payload = {
            'sku': 'XXX-YYY-ZZZ-001',  # Categoría XXX no existe
            'name': 'Producto con categoría inválida',
            'unit': 'unidad',
            'category': self.category1.pk
        }
        response = api_client_authenticated.post(self.products_url, payload, format='json')
        assert response.status_code == 400, f"Error: {response.data}"

    def test_create_product_unauthenticated(self):
        """Prueba que un usuario no autenticado no puede crear un producto."""
        client = APIClient()
        response = client.post(self.products_url, self.product_data_dict_for_api, format='json')
        assert response.status_code == 401

    def test_create_product_duplicate_sku(self, api_client_authenticated):
        """Prueba la creación de un producto con SKU duplicado."""
        Product.objects.create(**self.product_data_for_model_creation)
        payload_dup_sku = {**self.product_data_dict_for_api, 'name': 'Otro Nombre Mismo SKU'}
        response = api_client_authenticated.post(self.products_url, payload_dup_sku, format='json')
        assert response.status_code == 400, f"Error: {response.data}"

    def test_list_products(self, api_client_authenticated):
        """Prueba obtener la lista de productos."""
        Product.objects.create(sku='LAB-MOD-YEP-001', name='Yeso para modelos', unit='kg', category=self.category1)
        Product.objects.create(sku='DES-GUT-HIP-001', name='Glutaraldehído 2%', unit='litro', category=self.category1)
        response = api_client_authenticated.get(self.products_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        assert 'results' in response.data
        results = response.data['results']
        
        test_products_in_response = [
            p for p in results 
            if isinstance(p, dict) and (p.get('sku', '').startswith(('LAB-', 'DES-', 'ANE-')))
        ]
        assert len(test_products_in_response) >= 2

    def test_filter_product_by_name(self, api_client_authenticated):
        """Prueba filtrar productos por nombre."""
        cat_filter_prod = Category.objects.create(name='Cat Filtro Prod Name-TEST')
        Product.objects.create(sku='IMP-ALG-ZHE-001', name='Alginato Hidrogum ZHERMACK', unit='un', category=cat_filter_prod)
        Product.objects.create(sku='PRO-PIE-FLU-001', name='Piedra pómez profilaxis', unit='un', category=cat_filter_prod)
        Product.objects.create(sku='END-LIM-GAT-001', name='Lima Gates NSK', unit='un', category=cat_filter_prod)

        response = api_client_authenticated.get(self.products_url, {'name': 'Alginato Hidrogum'})
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert 'Alginato Hidrogum' in response.data['results'][0]['name']

    def test_filter_product_by_sku(self, api_client_authenticated):
        """Prueba filtrar productos por SKU (exacto)."""
        cat_filter_sku = Category.objects.create(name='Cat Filtro SKU-TEST')
        sku_to_find = 'BLA-CAS-ULT-001'
        Product.objects.create(sku=sku_to_find, name='Kit blanqueamiento casero Ultradent', unit='kit', category=cat_filter_sku)
        Product.objects.create(sku='BLA-CON-FGM-001', name='Blanqueamiento consultorio FGM', unit='kit', category=cat_filter_sku)

        response = api_client_authenticated.get(self.products_url, {'sku': sku_to_find})
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['sku'] == sku_to_find

    def test_filter_product_by_barcode(self, api_client_authenticated):
        """Prueba filtrar productos por código de barras."""
        cat_filter_barcode = Category.objects.create(name='Cat Filtro Barcode-TEST')
        barcode_to_find = '1234567890123'
        Product.objects.create(
            sku='ACE-GUA-LAT-001', 
            barcode=barcode_to_find,
            name='Guantes latex M', 
            unit='caja', 
            category=cat_filter_barcode
        )
        Product.objects.create(
            sku='ACE-GUA-NIT-001', 
            barcode='9876543210987',
            name='Guantes nitrilo L', 
            unit='caja', 
            category=cat_filter_barcode
        )

        response = api_client_authenticated.get(self.products_url, {'barcode': barcode_to_find})
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['barcode'] == barcode_to_find

    def test_filter_product_by_category_id(self, api_client_authenticated):
        """Prueba filtrar productos por ID de categoría."""
        cat_filter_id_A = Category.objects.create(name='Cat Filtro ID A-TEST')
        cat_filter_id_B = Category.objects.create(name='Cat Filtro ID B-TEST')
        Product.objects.create(sku='ORG-PAP-VAR-001', name='Papel bond A4', unit='resma', category=cat_filter_id_A)
        Product.objects.create(sku='ORG-LIM-DES-001', name='Desinfectante superficies', unit='litro', category=cat_filter_id_A)
        Product.objects.create(sku='ORT-ALA-TIT-001', name='Alambre titanio 0.16', unit='metro', category=cat_filter_id_B)

        response = api_client_authenticated.get(self.products_url, {'category': cat_filter_id_A.pk})
        assert response.status_code == 200
        assert len(response.data['results']) == 2
        for prod in response.data['results']:
            assert prod['category'] == cat_filter_id_A.pk

    def test_retrieve_product(self, api_client_authenticated):
        """Prueba obtener el detalle de un producto."""
        product = Product.objects.create(**self.product_data_for_model_creation)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        response = api_client_authenticated.get(detail_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert response.data['sku'] == product.sku
        assert response.data['name'] == product.name
        assert response.data['barcode'] == product.barcode
        assert response.data['category'] == product.category.pk
        assert response.data['category_name'] == product.category.name

    def test_update_product(self, api_client_authenticated):
        """Prueba actualizar un producto (PUT)."""
        product = Product.objects.create(**self.product_data_for_model_creation)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        category2 = Category.objects.create(name='Suturas Test')
        payload = {
            'sku': product.sku,
            'barcode': '9999888877776666',
            'name': 'ANESTESIA SEPTODONT Actualizada',
            'description': 'Descripción actualizada para test.',
            'unit': 'caja de 50',
            'category': category2.pk
        }
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        product.refresh_from_db()
        assert product.name == 'ANESTESIA SEPTODONT Actualizada'
        assert product.barcode == '9999888877776666'
        assert product.category == category2

    def test_partial_update_product(self, api_client_authenticated):
        """Prueba actualizar parcialmente un producto (PATCH)."""
        product = Product.objects.create(**self.product_data_for_model_creation)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        payload = {'name': 'ANESTESIA SEPTODONT Premium', 'barcode': '1111222233334444'}
        response = api_client_authenticated.patch(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        product.refresh_from_db()
        assert product.name == 'ANESTESIA SEPTODONT Premium'
        assert product.barcode == '1111222233334444'

    def test_delete_product(self, api_client_authenticated):
        """Prueba eliminar un producto."""
        product = Product.objects.create(**self.product_data_for_model_creation)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 204, f"Error: {response.data if response.data else ''}"
        assert not Product.objects.filter(pk=product.pk).exists()

@pytest.mark.django_db
class TestSKUValidation:
    """Tests para el sistema de validación de SKU."""

    def test_sku_validator_valid_skus(self):
        """Prueba que el validador acepta SKUs válidos."""
        validator = SKUValidator()
        valid_skus = [
            'LAB-ART-BIO-001',
            'ANE-CAR-SEP-002',
            'RES-ADH-M3M-001',
            'IMP-ALG-ZHE-001',
            'ACE-GUA-LAT-001',
            'END-LIM-GAT-001',
            'DES-GUT-HIP-001'
        ]
        
        for sku in valid_skus:
            try:
                validator(sku)
            except ValidationError:
                pytest.fail(f"SKU válido '{sku}' fue rechazado por el validador")

    def test_sku_validator_invalid_format(self):
        """Prueba que el validador rechaza formatos inválidos."""
        validator = SKUValidator()
        invalid_skus = [
            'INVALID',
            'LAB-ART-BIO',  # Falta secuencial
            'LAB-ART-BIO-1',  # Secuencial muy corto
            'LAB-ART-BIO-1234',  # Secuencial muy largo
            'lab-art-bio-001',  # Minúsculas
            'LAB_ART_BIO_001',  # Guiones bajos en lugar de guiones
            'LAB-ART-BIO-ABC',  # Secuencial no numérico
            '',  # Vacío
            'LABARTBIO001',  # Sin separadores
        ]
        
        for sku in invalid_skus:
            with pytest.raises(ValidationError):
                validator(sku)

    def test_sku_validator_invalid_category(self):
        """Prueba que el validador rechaza categorías inválidas."""
        validator = SKUValidator()
        invalid_category_skus = [
            'XXX-ART-BIO-001',  # Categoría inexistente
            'ZZZ-CAR-SEP-001',  # Categoría inexistente
        ]
        
        for sku in invalid_category_skus:
            with pytest.raises(ValidationError) as exc_info:
                validator(sku)
            assert "Categoría" in str(exc_info.value)

    def test_sku_validator_invalid_subcategory(self):
        """Prueba que el validador rechaza subcategorías inválidas."""
        validator = SKUValidator()
        invalid_subcategory_skus = [
            'LAB-XXX-BIO-001',  # Subcategoría inexistente para LAB
            'ANE-YYY-SEP-001',  # Subcategoría inexistente para ANE
        ]
        
        for sku in invalid_subcategory_skus:
            with pytest.raises(ValidationError) as exc_info:
                validator(sku)
            assert "Subcategoría" in str(exc_info.value)

    def test_sku_structure_info(self):
        """Prueba que get_sku_structure_info devuelve la información completa."""
        info = SKUValidator.get_sku_structure_info()
        
        assert 'formato' in info
        assert 'categorias' in info
        assert 'subcategorias' in info
        assert 'tipos_materiales' in info
        assert 'ejemplos_reales' in info
        assert 'reglas' in info
        
        # Verificar que contiene las categorías principales
        assert 'LAB' in info['categorias']
        assert 'ANE' in info['categorias']
        assert 'RES' in info['categorias']
        
        # Verificar ejemplos reales
        assert len(info['ejemplos_reales']) >= 5

    def test_generate_next_sku(self):
        """Prueba la generación del siguiente SKU disponible."""
        # Sin SKUs existentes
        next_sku = SKUValidator.generate_next_sku('LAB', 'ART', 'BIO', [])
        assert next_sku == 'LAB-ART-BIO-001'
        
        # Con SKUs existentes
        existing_skus = ['LAB-ART-BIO-001', 'LAB-ART-BIO-003', 'ANE-CAR-SEP-001']
        next_sku = SKUValidator.generate_next_sku('LAB', 'ART', 'BIO', existing_skus)
        assert next_sku == 'LAB-ART-BIO-004'  # Toma el máximo + 1
        
        # Para una combinación diferente
        next_sku = SKUValidator.generate_next_sku('ANE', 'CAR', 'SEP', existing_skus)
        assert next_sku == 'ANE-CAR-SEP-002'

    def test_generate_next_sku_invalid_params(self):
        """Prueba que generate_next_sku falla con parámetros inválidos."""
        # Categoría inválida
        with pytest.raises(ValueError) as exc_info:
            SKUValidator.generate_next_sku('XXX', 'ART', 'BIO', [])
        assert "Categoría 'XXX' no válida" in str(exc_info.value)
        
        # Subcategoría inválida
        with pytest.raises(ValueError) as exc_info:
            SKUValidator.generate_next_sku('LAB', 'XXX', 'BIO', [])
        assert "Subcategoría 'XXX' no válida" in str(exc_info.value)

@pytest.mark.django_db
class TestSKUEndpoints:
    """Tests para los endpoints específicos del sistema SKU."""

    def setup_method(self):
        self.sku_info_url = '/api/catalogs/sku/info/'
        self.sku_generate_url = '/api/catalogs/sku/generate/'
        self.sku_validate_url = '/api/catalogs/sku/validate/'

    def test_sku_info_endpoint(self, api_client_authenticated):
        """Prueba el endpoint de información del sistema SKU."""
        response = api_client_authenticated.get(self.sku_info_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        data = response.data
        assert 'formato' in data
        assert 'categorias' in data
        assert 'subcategorias' in data
        assert 'tipos_materiales' in data
        assert 'ejemplos_reales' in data
        assert 'reglas' in data
        
        # Verificar que contiene las categorías del inventario real
        assert 'LAB' in data['categorias']
        assert 'ANE' in data['categorias']
        assert len(data['ejemplos_reales']) >= 5

    def test_sku_info_unauthenticated(self):
        """Prueba que el endpoint de info SKU requiere autenticación."""
        client = APIClient()
        response = client.get(self.sku_info_url)
        assert response.status_code == 401

    def test_generate_sku_endpoint(self, api_client_authenticated):
        """Prueba el endpoint de generación de SKU."""
        # Crear algunos productos para probar la secuencia
        category = Category.objects.create(name='Test Lab')
        Product.objects.create(sku='LAB-ART-BIO-001', name='Test Product 1', unit='un', category=category)
        Product.objects.create(sku='LAB-ART-BIO-003', name='Test Product 3', unit='un', category=category)

        payload = {
            'categoria': 'LAB',
            'subcategoria': 'ART',
            'tipo': 'BIO'
        }
        response = api_client_authenticated.post(self.sku_generate_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        data = response.data
        assert 'sku_sugerido' in data
        assert 'categoria_nombre' in data
        assert 'subcategoria_nombre' in data
        assert 'tipo_nombre' in data
        
        assert data['sku_sugerido'] == 'LAB-ART-BIO-004'  # Siguiente disponible
        assert data['categoria_nombre'] == 'Laboratorio'

    def test_generate_sku_lowercase_input(self, api_client_authenticated):
        """Prueba que el endpoint acepta entrada en minúsculas."""
        payload = {
            'categoria': 'ane',
            'subcategoria': 'car',
            'tipo': 'sep'
        }
        response = api_client_authenticated.post(self.sku_generate_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        assert response.data['sku_sugerido'] == 'ANE-CAR-SEP-001'

    def test_generate_sku_invalid_category(self, api_client_authenticated):
        """Prueba el endpoint con categoría inválida."""
        payload = {
            'categoria': 'XXX',
            'subcategoria': 'ART',
            'tipo': 'BIO'
        }
        response = api_client_authenticated.post(self.sku_generate_url, payload, format='json')
        assert response.status_code == 400
        assert 'error' in response.data

    def test_generate_sku_missing_params(self, api_client_authenticated):
        """Prueba el endpoint con parámetros faltantes."""
        payload = {
            'categoria': 'LAB',
            'subcategoria': 'ART'
            # Falta 'tipo'
        }
        response = api_client_authenticated.post(self.sku_generate_url, payload, format='json')
        assert response.status_code == 400
        assert 'error' in response.data

    def test_validate_sku_endpoint_valid(self, api_client_authenticated):
        """Prueba el endpoint de validación con SKU válido."""
        payload = {'sku': 'LAB-ART-BIO-001'}
        response = api_client_authenticated.post(self.sku_validate_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        data = response.data
        assert 'valido' in data
        assert 'mensaje' in data
        assert 'disponible' in data
        
        assert data['valido'] is True
        assert data['disponible'] is True

    def test_validate_sku_endpoint_exists(self, api_client_authenticated):
        """Prueba el endpoint de validación con SKU que ya existe."""
        # Crear un producto con este SKU
        category = Category.objects.create(name='Test Category')
        Product.objects.create(sku='LAB-ART-BIO-001', name='Test Product', unit='un', category=category)

        payload = {'sku': 'LAB-ART-BIO-001'}
        response = api_client_authenticated.post(self.sku_validate_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        data = response.data
        assert data['valido'] is True
        assert data['disponible'] is False
        assert 'ya existe' in data['mensaje']

    def test_validate_sku_endpoint_invalid(self, api_client_authenticated):
        """Prueba el endpoint de validación con SKU inválido."""
        payload = {'sku': 'INVALID-SKU-FORMAT'}
        response = api_client_authenticated.post(self.sku_validate_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        data = response.data
        assert data['valido'] is False
        assert data['disponible'] is False

    def test_validate_sku_endpoint_lowercase(self, api_client_authenticated):
        """Prueba que el endpoint de validación convierte a mayúsculas."""
        payload = {'sku': 'lab-art-bio-001'}
        response = api_client_authenticated.post(self.sku_validate_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        
        data = response.data
        assert data['valido'] is True
        assert 'LAB-ART-BIO-001' in data['mensaje']

    def test_validate_sku_endpoint_missing_sku(self, api_client_authenticated):
        """Prueba el endpoint de validación sin SKU."""
        payload = {}
        response = api_client_authenticated.post(self.sku_validate_url, payload, format='json')
        assert response.status_code == 400
        assert 'error' in response.data

    def test_sku_endpoints_unauthenticated(self):
        """Prueba que todos los endpoints de SKU requieren autenticación."""
        client = APIClient()
        
        # Probar generate_sku
        response = client.post(self.sku_generate_url, {'categoria': 'LAB', 'subcategoria': 'ART', 'tipo': 'BIO'})
        assert response.status_code == 401
        
        # Probar validate_sku
        response = client.post(self.sku_validate_url, {'sku': 'LAB-ART-BIO-001'})
        assert response.status_code == 401 