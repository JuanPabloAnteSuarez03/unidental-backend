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
        Category.objects.create(name='Equipamiento Dental-TEST', description='Equipos para consultorios')
        Category.objects.create(name='Material de Oficina-TEST', description='Papelería y consumibles')
        response = api_client_authenticated.get(self.categories_url)
        assert response.status_code == 200, f"Error: {response.data}"
        # Ajustamos la aserción para ser más flexible con otros tests
        test_categories_in_response = [cat for cat in response.data['results'] if isinstance(cat, dict) and cat.get('name', '').endswith('-TEST')]
        assert len(test_categories_in_response) >= 2

    def test_category_pagination(self, api_client_authenticated):
        """Prueba la paginación para la lista de categorías."""
        # Crear más categorías que el PAGE_SIZE (asumiendo PAGE_SIZE=10 de settings)
        for i in range(12):
            Category.objects.create(name=f'Categoria Paginada {i}-TEST', description=f'Desc {i}')
        
        response = api_client_authenticated.get(self.categories_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert 'results' in response.data
        
        assert len(response.data['results']) == 10 # Asumiendo PAGE_SIZE = 10
        assert response.data['count'] >= 12 # Debería ser el total de categorías, incluyendo las de este test
        assert response.data['next'] is not None # Debería haber una página siguiente
        assert response.data['previous'] is None # Primera página

        # Probar ir a la segunda página
        response_page2 = api_client_authenticated.get(response.data['next'])
        assert response_page2.status_code == 200
        assert len(response_page2.data['results']) >= 2 # Los ítems restantes
        assert response_page2.data['previous'] is not None

    def test_filter_category_by_name(self, api_client_authenticated):
        """Prueba filtrar categorías por nombre."""
        Category.objects.create(name='FiltroNombreExacto-TEST', description='Para test de filtro exacto')
        Category.objects.create(name='FiltroNombreParcialUno-TEST', description='Para test de filtro parcial')
        Category.objects.create(name='FiltroNombreParcialDos-TEST', description='Otro para test de filtro parcial')
        Category.objects.create(name='OtraCategoriaSinFiltro-TEST', description='No debe aparecer')

        # Filtro por nombre exacto (icontains debería funcionar)
        response = api_client_authenticated.get(self.categories_url, {'name': 'FiltroNombreExacto-TEST'})
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'FiltroNombreExacto-TEST'

        # Filtro por nombre parcial (icontains)
        response = api_client_authenticated.get(self.categories_url, {'name': 'FiltroNombreParcial'})
        assert response.status_code == 200
        assert len(response.data['results']) == 2
        names_in_response = {cat['name'] for cat in response.data['results']}
        assert 'FiltroNombreParcialUno-TEST' in names_in_response
        assert 'FiltroNombreParcialDos-TEST' in names_in_response
        
        # Filtro que no encuentra nada
        response = api_client_authenticated.get(self.categories_url, {'name': 'NombreInexistente123'})
        assert response.status_code == 200
        assert len(response.data['results']) == 0

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
        self.category1 = Category.objects.create(name='Anestésicos Test', description='Para control del dolor en tests')
        # Limpiar productos que podrían usar el mismo SKU para evitar IntegrityError en creación directa
        Product.objects.filter(sku='ANEST-LIDO-001-TEST').delete()
        
        self.product_data_dict_for_api = { # Para usar con la API, se envía el ID de categoría
            'sku': 'ANEST-LIDO-001-TEST',
            'name': 'Lidocaína 2% con Epinefrina Test',
            'description': 'Cartucho de anestésico local para test.',
            'unit': 'cartucho',
            'category': self.category1.pk 
        }
        self.product_data_for_model_creation = { # Para crear directamente con el ORM, se pasa la instancia
            'sku': 'ANEST-LIDO-001-TEST',
            'name': 'Lidocaína 2% con Epinefrina Test',
            'description': 'Cartucho de anestésico local para test.',
            'unit': 'cartucho',
            'category': self.category1 # <--- CORRECCIÓN: Usar la instancia de Category
        }

    def test_create_product_authenticated(self, api_client_authenticated):
        """Prueba la creación de un producto por un usuario autenticado."""
        # Usar el diccionario preparado para la API
        response = api_client_authenticated.post(self.products_url, self.product_data_dict_for_api, format='json')
        assert response.status_code == 201, f"Error: {response.data}"
        assert Product.objects.filter(sku=self.product_data_dict_for_api['sku']).exists()
        created_product = Product.objects.get(sku=self.product_data_dict_for_api['sku'])
        assert created_product.name == self.product_data_dict_for_api['name']
        assert created_product.category.pk == self.product_data_dict_for_api['category']

    def test_create_product_unauthenticated(self):
        """Prueba que un usuario no autenticado no puede crear un producto."""
        client = APIClient()
        response = client.post(self.products_url, self.product_data_dict_for_api, format='json')
        assert response.status_code == 401 # Unauthorized

    def test_create_product_duplicate_sku(self, api_client_authenticated):
        """Prueba la creación de un producto con SKU duplicado."""
        # Crear el primer producto usando los datos para la creación directa del modelo
        Product.objects.create(**self.product_data_for_model_creation) 
        # Intentar crear a través de la API con el mismo SKU
        payload_dup_sku = {**self.product_data_dict_for_api, 'name': 'Otro Nombre Mismo SKU'}
        response = api_client_authenticated.post(self.products_url, payload_dup_sku, format='json')
        assert response.status_code == 400, f"Error: {response.data}"

    def test_create_product_nonexistent_category(self, api_client_authenticated):
        """Prueba crear un producto con un ID de categoría que no existe."""
        non_existent_category_id = 9999
        # Crear un SKU único para este test para evitar colisiones con otros tests que puedan crear el mismo SKU base
        unique_sku_for_this_test = f"{self.product_data_dict_for_api['sku']}-noncat"
        payload = {**self.product_data_dict_for_api, 'category': non_existent_category_id, 'sku': unique_sku_for_this_test}
        response = api_client_authenticated.post(self.products_url, payload, format='json')
        assert response.status_code == 400, f"Error: {response.data}"

    def test_list_products(self, api_client_authenticated):
        """Prueba obtener la lista de productos."""
        Product.objects.create(sku='P001-LIST-TEST', name='Producto A List Test', unit='un', category=self.category1)
        Product.objects.create(sku='P002-LIST-TEST', name='Producto B List Test', unit='kg', category=self.category1)
        response = api_client_authenticated.get(self.products_url)
        assert response.status_code == 200, f"Error: {response.data}"
        
        assert 'results' in response.data # Paginación devuelve 'results'
        results = response.data['results']
        
        # Contar solo los productos de test para evitar fallos si otros tests crean productos
        # Y asegurarse de que los resultados sean diccionarios con 'sku'
        test_products_in_response = [
            p for p in results 
            if isinstance(p, dict) and p.get('sku', '').endswith(('-TEST', '-LIST-TEST'))
        ]
        assert len(test_products_in_response) >= 2
        if len(test_products_in_response) > 0:
            assert 'category_name' in test_products_in_response[0]
            assert test_products_in_response[0]['category_name'] == self.category1.name

    def test_product_pagination(self, api_client_authenticated):
        """Prueba la paginación para la lista de productos."""
        category_for_pagination = Category.objects.create(name='Cat Paginación Prod-TEST')
        for i in range(12):
            # Asegurar SKUs únicos para cada producto paginado
            Product.objects.create(
                sku=f'PAGPROD{i}-TEST', 
                name=f'Producto Paginado {i}-TEST', 
                unit='un', 
                category=category_for_pagination
            )
        
        response = api_client_authenticated.get(self.products_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert 'results' in response.data
        
        assert len(response.data['results']) == 10 # Asumiendo PAGE_SIZE = 10
        assert response.data['count'] >= 12
        assert response.data['next'] is not None
        assert response.data['previous'] is None

        # Probar ir a la segunda página
        response_page2 = api_client_authenticated.get(response.data['next'])
        assert response_page2.status_code == 200
        assert len(response_page2.data['results']) >= 2 # Los ítems restantes
        assert response_page2.data['previous'] is not None

    def test_filter_product_by_name(self, api_client_authenticated):
        """Prueba filtrar productos por nombre."""
        cat_filter_prod = Category.objects.create(name='Cat Filtro Prod Name-TEST')
        Product.objects.create(sku='FILTERPRODNAME1-TEST', name='Producto Buscable Exacto-TEST', unit='un', category=cat_filter_prod)
        Product.objects.create(sku='FILTERPRODNAME2-TEST', name='Producto Buscable Parcial Alfa-TEST', unit='un', category=cat_filter_prod)
        Product.objects.create(sku='FILTERPRODNAME3-TEST', name='Producto Buscable Parcial Beta-TEST', unit='un', category=cat_filter_prod)
        Product.objects.create(sku='OTHERPRODNAME-TEST', name='Otro Producto No Buscado-TEST', unit='un', category=cat_filter_prod)

        response = api_client_authenticated.get(self.products_url, {'name': 'Producto Buscable Exacto-TEST'})
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'Producto Buscable Exacto-TEST'

        response = api_client_authenticated.get(self.products_url, {'name': 'Buscable Parcial'})
        assert response.status_code == 200
        assert len(response.data['results']) == 2
        names_in_response = {p['name'] for p in response.data['results']}
        assert 'Producto Buscable Parcial Alfa-TEST' in names_in_response
        assert 'Producto Buscable Parcial Beta-TEST' in names_in_response

    def test_filter_product_by_sku(self, api_client_authenticated):
        """Prueba filtrar productos por SKU (exacto)."""
        cat_filter_sku = Category.objects.create(name='Cat Filtro SKU-TEST')
        sku_to_find = 'SKUFILTER001-TEST'
        Product.objects.create(sku=sku_to_find, name='Producto SKU Test 1-TEST', unit='un', category=cat_filter_sku)
        Product.objects.create(sku='SKUFILTER002-TEST', name='Producto SKU Test 2-TEST', unit='un', category=cat_filter_sku)

        response = api_client_authenticated.get(self.products_url, {'sku': sku_to_find})
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['sku'] == sku_to_find

    def test_filter_product_by_category_id(self, api_client_authenticated):
        """Prueba filtrar productos por ID de categoría."""
        cat_filter_id_A = Category.objects.create(name='Cat Filtro ID A-TEST')
        cat_filter_id_B = Category.objects.create(name='Cat Filtro ID B-TEST')
        Product.objects.create(sku='PRODFILTCATA1-TEST', name='Prod Cat A1-TEST', unit='un', category=cat_filter_id_A)
        Product.objects.create(sku='PRODFILTCATA2-TEST', name='Prod Cat A2-TEST', unit='un', category=cat_filter_id_A)
        Product.objects.create(sku='PRODFILTCATB1-TEST', name='Prod Cat B1-TEST', unit='un', category=cat_filter_id_B)

        response = api_client_authenticated.get(self.products_url, {'category': cat_filter_id_A.pk})
        assert response.status_code == 200
        assert len(response.data['results']) == 2
        for prod in response.data['results']:
            assert prod['category'] == cat_filter_id_A.pk
            assert prod['category_name'] == cat_filter_id_A.name

    def test_filter_product_by_category_name(self, api_client_authenticated):
        """Prueba filtrar productos por nombre de categoría (parcial)."""
        cat_filter_cname_X = Category.objects.create(name='Filtro CatNombre X-TEST')
        cat_filter_cname_Y = Category.objects.create(name='Filtro CatNombre Y-TEST')
        cat_filter_cname_Z = Category.objects.create(name='Otra Cat Z-TEST')
        Product.objects.create(sku='PRODFILCATNAME_X1-TEST', name='Prod Filtro CatName X1-TEST', unit='un', category=cat_filter_cname_X)
        Product.objects.create(sku='PRODFILCATNAME_Y1-TEST', name='Prod Filtro CatName Y1-TEST', unit='un', category=cat_filter_cname_Y)
        Product.objects.create(sku='PRODFILCATNAME_Z1-TEST', name='Prod Filtro CatName Z1-TEST', unit='un', category=cat_filter_cname_Z)

        response = api_client_authenticated.get(self.products_url, {'category_name': 'Filtro CatNombre'})
        assert response.status_code == 200
        assert len(response.data['results']) == 2
        category_names_in_response = {p['category_name'] for p in response.data['results']}
        assert 'Filtro CatNombre X-TEST' in category_names_in_response
        assert 'Filtro CatNombre Y-TEST' in category_names_in_response

    def test_combined_filters_and_pagination(self, api_client_authenticated):
        """Prueba filtros combinados con paginación para productos."""
        cat_combined = Category.objects.create(name='Cat Combinado Filtro-TEST')
        # Crear 12 productos que coincidan con un filtro de nombre, para forzar paginación
        for i in range(12):
            Product.objects.create(
                sku=f'COMBPROD{i}-TEST', 
                name=f'Producto Combinado Test {i}-TEST', 
                unit='un', 
                category=cat_combined
            )
        # Crear algunos productos que no coincidan
        other_cat = Category.objects.create(name='Cat Otro Combinado-TEST')
        Product.objects.create(sku='NONMATCHPROD1-TEST', name='No Coincide Nombre-TEST', unit='un', category=cat_combined)
        Product.objects.create(sku='NONMATCHPROD2-TEST', name='Producto Combinado Test OtroCat-TEST', unit='un', category=other_cat)

        # Filtrar por nombre (debería haber 12) y categoría
        params = {'name': 'Producto Combinado Test', 'category': cat_combined.pk}
        response = api_client_authenticated.get(self.products_url, params)
        assert response.status_code == 200
        assert 'count' in response.data
        assert response.data['count'] == 12 # Exactamente 12 productos coinciden con ambos filtros
        assert len(response.data['results']) == 10 # Primera página
        assert response.data['next'] is not None

        # Verificar que todos los resultados de la primera página coincidan
        for prod in response.data['results']:
            assert 'Producto Combinado Test' in prod['name']
            assert prod['category'] == cat_combined.pk
        
        # Ir a la segunda página
        response_page2 = api_client_authenticated.get(response.data['next'])
        assert response_page2.status_code == 200
        assert len(response_page2.data['results']) == 2 # Los 2 restantes
        for prod in response_page2.data['results']:
            assert 'Producto Combinado Test' in prod['name']
            assert prod['category'] == cat_combined.pk

    def test_retrieve_product(self, api_client_authenticated):
        """Prueba obtener el detalle de un producto."""
        # Usar el diccionario preparado para la creación directa del modelo
        product = Product.objects.create(**self.product_data_for_model_creation)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        response = api_client_authenticated.get(detail_url)
        assert response.status_code == 200, f"Error: {response.data}"
        assert response.data['sku'] == product.sku
        assert response.data['name'] == product.name
        assert response.data['category'] == product.category.pk
        assert response.data['category_name'] == product.category.name

    def test_update_product(self, api_client_authenticated):
        """Prueba actualizar un producto (PUT)."""
        # Usar el diccionario preparado para la creación directa del modelo
        product = Product.objects.create(**self.product_data_for_model_creation)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        category2 = Category.objects.create(name='Suturas Test')
        payload = {
            'sku': product.sku, 
            'name': 'Lidocaína 2% Cartucho (Actualizado Test)',
            'description': 'Descripción actualizada para test.',
            'unit': 'caja de 50 test',
            'category': category2.pk
        }
        response = api_client_authenticated.put(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        product.refresh_from_db()
        assert product.name == 'Lidocaína 2% Cartucho (Actualizado Test)'
        assert product.unit == 'caja de 50 test'
        assert product.category == category2

    def test_partial_update_product(self, api_client_authenticated):
        """Prueba actualizar parcialmente un producto (PATCH)."""
        # Usar el diccionario preparado para la creación directa del modelo
        product = Product.objects.create(**self.product_data_for_model_creation)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        payload = {'name': 'Lidocaína Cartucho Gold Test'}
        response = api_client_authenticated.patch(detail_url, payload, format='json')
        assert response.status_code == 200, f"Error: {response.data}"
        product.refresh_from_db()
        assert product.name == 'Lidocaína Cartucho Gold Test'

    def test_delete_product(self, api_client_authenticated):
        """Prueba eliminar un producto."""
        # Usar el diccionario preparado para la creación directa del modelo
        product = Product.objects.create(**self.product_data_for_model_creation)
        detail_url = reverse('product-detail', kwargs={'pk': product.pk})
        response = api_client_authenticated.delete(detail_url)
        assert response.status_code == 204, f"Error: {response.data if response.data else ''}"
        assert not Product.objects.filter(pk=product.pk).exists() 