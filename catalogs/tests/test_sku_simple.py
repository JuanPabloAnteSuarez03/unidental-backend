import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from catalogs.models import Category, Product, SkuCategory, SkuSubCategory, SkuType
from catalogs.validators import SKUValidator

User = get_user_model()

class TestSKUEndpointsSimple(TestCase):
    """Tests simples para los endpoints de SKU actualizados."""
    
    def setUp(self):
        """Configuración inicial para cada test."""
        # Crear usuario para autenticación
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        
        # Configurar cliente API
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Crear estructura de SKU de prueba
        self.category = SkuCategory.objects.create(
            code='LAB',
            name='Laboratorio'
        )
        
        self.subcategory = SkuSubCategory.objects.create(
            category=self.category,
            code='ART',
            name='Articuladores'
        )
        
        self.sku_type = SkuType.objects.create(
            subcategory=self.subcategory,
            code='BIO',
            name='Bio-Art'
        )
        
        # Crear categoría de producto
        self.product_category = Category.objects.create(
            name='Equipos de Laboratorio',
            description='Equipos para laboratorio dental'
        )

    def test_sku_info_endpoint(self):
        """Test del endpoint de información de SKU."""
        url = '/api/catalogs/sku/info/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Verificar estructura básica
        self.assertIn('formato', data)
        self.assertIn('ejemplo', data)
        self.assertIn('categorias', data)
        self.assertIn('subcategorias', data)
        self.assertIn('tipos', data)
        self.assertIn('reglas', data)
        
        self.assertEqual(data['formato'], 'CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL')
        self.assertEqual(data['ejemplo'], 'LAB-ART-BIO-001')
        
        # Verificar que contiene los datos de la base de datos
        self.assertGreaterEqual(len(data['categorias']), 1)
        self.assertGreaterEqual(len(data['subcategorias']), 1)
        self.assertGreaterEqual(len(data['tipos']), 1)

    def test_sku_structure_endpoint(self):
        """Test del endpoint de estructura de SKU."""
        url = '/api/catalogs/sku/structure/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Verificar estructura
        self.assertIn('categorias', data)
        self.assertIn('subcategorias', data)
        self.assertIn('tipos', data)
        
        # Verificar que contiene los datos
        self.assertGreaterEqual(len(data['categorias']), 1)
        self.assertGreaterEqual(len(data['subcategorias']), 1)
        self.assertGreaterEqual(len(data['tipos']), 1)
        
        # Verificar estructura de categoría
        category = data['categorias'][0]
        self.assertEqual(category['code'], 'LAB')
        self.assertEqual(category['name'], 'Laboratorio')
        
        # Verificar estructura de subcategoría
        subcategory = data['subcategorias'][0]
        self.assertEqual(subcategory['code'], 'ART')
        self.assertEqual(subcategory['name'], 'Articuladores')
        self.assertEqual(subcategory['category_id'], self.category.id)
        
        # Verificar estructura de tipo
        sku_type = data['tipos'][0]
        self.assertEqual(sku_type['code'], 'BIO')
        self.assertEqual(sku_type['name'], 'Bio-Art')
        self.assertEqual(sku_type['subcategory_id'], self.subcategory.id)

    def test_generate_sku_endpoint(self):
        """Test del endpoint de generación de SKU."""
        url = '/api/catalogs/sku/generate/'
        payload = {
            'category_id': self.category.id,
            'subcategory_id': self.subcategory.id,
            'type_id': self.sku_type.id
        }
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Verificar estructura de respuesta
        self.assertIn('sku_sugerido', data)
        self.assertIn('categoria_nombre', data)
        self.assertIn('subcategoria_nombre', data)
        self.assertIn('tipo_nombre', data)
        
        # Verificar que el SKU generado tiene el formato correcto
        self.assertEqual(data['sku_sugerido'], 'LAB-ART-BIO-001')
        self.assertEqual(data['categoria_nombre'], 'Laboratorio')
        self.assertEqual(data['subcategoria_nombre'], 'Articuladores')
        self.assertEqual(data['tipo_nombre'], 'Bio-Art')

    def test_generate_sku_with_existing_product(self):
        """Test de generación de SKU cuando ya existe un producto."""
        # Crear un producto con SKU existente
        Product.objects.create(
            sku='LAB-ART-BIO-001',
            name='Producto Test',
            unit='unidad',
            category=self.product_category
        )
        
        url = '/api/catalogs/sku/generate/'
        payload = {
            'category_id': self.category.id,
            'subcategory_id': self.subcategory.id,
            'type_id': self.sku_type.id
        }
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Debería generar el siguiente SKU disponible
        self.assertEqual(data['sku_sugerido'], 'LAB-ART-BIO-002')

    def test_generate_sku_invalid_category(self):
        """Test de generación de SKU con categoría inválida."""
        url = '/api/catalogs/sku/generate/'
        payload = {
            'category_id': 99999,  # ID inexistente
            'subcategory_id': self.subcategory.id,
            'type_id': self.sku_type.id
        }
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('categoría con ID 99999 no existe', data['error'])

    def test_generate_sku_missing_parameters(self):
        """Test de generación de SKU con parámetros faltantes."""
        url = '/api/catalogs/sku/generate/'
        payload = {
            'category_id': self.category.id,
            # Faltan subcategory_id y type_id
        }
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Se requieren category_id, subcategory_id y type_id', data['error'])

    def test_validate_sku_endpoint_valid(self):
        """Test de validación de SKU válido."""
        url = '/api/catalogs/sku/validate/'
        payload = {'sku': 'LAB-ART-BIO-001'}
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertTrue(data['valido'])
        self.assertTrue(data['disponible'])
        self.assertIn('válido y está disponible', data['mensaje'])

    def test_validate_sku_endpoint_exists(self):
        """Test de validación de SKU que ya existe."""
        # Crear producto con el SKU
        Product.objects.create(
            sku='LAB-ART-BIO-001',
            name='Producto Existente',
            unit='unidad',
            category=self.product_category
        )
        
        url = '/api/catalogs/sku/validate/'
        payload = {'sku': 'LAB-ART-BIO-001'}
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertTrue(data['valido'])
        self.assertFalse(data['disponible'])
        self.assertIn('válido pero ya existe', data['mensaje'])

    def test_validate_sku_endpoint_invalid_format(self):
        """Test de validación de SKU con formato inválido."""
        url = '/api/catalogs/sku/validate/'
        payload = {'sku': 'INVALID-SKU'}
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertFalse(data['valido'])
        self.assertFalse(data['disponible'])
        self.assertIn('formato', data['mensaje'].lower())

    def test_validate_sku_endpoint_nonexistent_components(self):
        """Test de validación de SKU con componentes inexistentes."""
        url = '/api/catalogs/sku/validate/'
        payload = {'sku': 'XXX-YYY-ZZZ-001'}
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertFalse(data['valido'])
        self.assertFalse(data['disponible'])
        self.assertIn('no existe', data['mensaje'])

    def test_validate_sku_endpoint_missing_sku(self):
        """Test de validación sin proporcionar SKU."""
        url = '/api/catalogs/sku/validate/'
        payload = {}
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Se requiere el campo sku', data['error'])

    def test_endpoints_unauthenticated(self):
        """Test que los endpoints requieren autenticación."""
        client = APIClient()  # Cliente sin autenticación
        
        endpoints = [
            '/api/catalogs/sku/info/',
            '/api/catalogs/sku/structure/',
            '/api/catalogs/sku/generate/',
            '/api/catalogs/sku/validate/'
        ]
        
        for endpoint in endpoints:
            if endpoint in ['/api/catalogs/sku/generate/', '/api/catalogs/sku/validate/']:
                response = client.post(endpoint, {}, format='json')
            else:
                response = client.get(endpoint)
            
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestSKUValidator(TestCase):
    """Tests para el validador de SKU actualizado."""
    
    def setUp(self):
        """Configuración inicial para cada test."""
        # Crear estructura de SKU de prueba
        self.category = SkuCategory.objects.create(
            code='LAB',
            name='Laboratorio'
        )
        
        self.subcategory = SkuSubCategory.objects.create(
            category=self.category,
            code='ART',
            name='Articuladores'
        )
        
        self.sku_type = SkuType.objects.create(
            subcategory=self.subcategory,
            code='BIO',
            name='Bio-Art'
        )

    def test_validator_valid_sku(self):
        """Test de validación de SKU válido."""
        validator = SKUValidator()
        
        # No debería lanzar excepción
        try:
            validator('LAB-ART-BIO-001')
        except Exception as e:
            self.fail(f"El validador falló con SKU válido: {e}")

    def test_validator_invalid_format(self):
        """Test de validación de SKU con formato inválido."""
        validator = SKUValidator()
        
        with self.assertRaises(Exception):
            validator('INVALID-SKU')

    def test_validator_nonexistent_components(self):
        """Test de validación de SKU con componentes inexistentes."""
        validator = SKUValidator()
        
        with self.assertRaises(Exception):
            validator('XXX-YYY-ZZZ-001')

    def test_generate_next_sku(self):
        """Test de generación del siguiente SKU."""
        base_sku = 'LAB-ART-BIO'
        existing_skus = ['LAB-ART-BIO-001', 'LAB-ART-BIO-003']
        
        next_sku = SKUValidator.generate_next_sku(base_sku, existing_skus)
        
        self.assertEqual(next_sku, 'LAB-ART-BIO-004')

    def test_generate_next_sku_empty_list(self):
        """Test de generación del primer SKU."""
        base_sku = 'LAB-ART-BIO'
        existing_skus = []
        
        next_sku = SKUValidator.generate_next_sku(base_sku, existing_skus)
        
        self.assertEqual(next_sku, 'LAB-ART-BIO-001') 