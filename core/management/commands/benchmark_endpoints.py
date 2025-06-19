import time
import requests
import json
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.conf import settings
from django.db import connection


class Command(BaseCommand):
    help = 'Prueba el rendimiento de todos los endpoints de la API para identificar cuellos de botella'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url',
            default='http://127.0.0.1:8000',
            help='URL base del servidor (default: http://127.0.0.1:8000)'
        )
        parser.add_argument(
            '--username',
            default='admin_unidental',
            help='Usuario para autenticación (default: admin_unidental)'
        )
        parser.add_argument(
            '--password',
            default='admin123',
            help='Password para autenticación'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout en segundos para cada request (default: 30)'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Mostrar información detallada de SQL queries'
        )

    def handle(self, *args, **options):
        self.base_url = options['base_url'].rstrip('/')
        self.username = options['username']
        self.password = options['password']
        self.timeout = options['timeout']
        self.detailed = options['detailed']
        
        self.stdout.write(self.style.SUCCESS('🚀 INICIANDO BENCHMARK DE ENDPOINTS'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Base URL: {self.base_url}')
        self.stdout.write(f'Timeout: {self.timeout}s')
        self.stdout.write('=' * 80)
        
        # Obtener token de autenticación
        self.token = self._get_auth_token()
        if not self.token:
            self.stdout.write(self.style.ERROR('❌ No se pudo obtener token de autenticación'))
            return
        
        # Definir endpoints a probar
        endpoints = self._get_endpoints_to_test()
        
        # Ejecutar pruebas
        results = []
        total_start = time.time()
        
        for endpoint_group, endpoints_list in endpoints.items():
            self.stdout.write(f'\n📂 PROBANDO: {endpoint_group}')
            self.stdout.write('-' * 60)
            
            for endpoint_info in endpoints_list:
                result = self._test_endpoint(endpoint_info)
                results.append(result)
                
                # Mostrar resultado inmediato
                status_icon = self._get_status_icon(result['response_time'])
                self.stdout.write(
                    f'{status_icon} {endpoint_info["name"]:<40} {result["response_time"]:.2f}ms'
                )
                
                if result['error']:
                    self.stdout.write(
                        self.style.ERROR(f'    ❌ Error: {result["error"]}')
                    )
        
        total_time = time.time() - total_start
        
        # Generar reporte final
        self._generate_report(results, total_time)

    def _get_auth_token(self):
        """Obtiene token de autenticación."""
        try:
            login_url = f'{self.base_url}/api/auth/token/login/'
            response = requests.post(
                login_url,
                json={'username': self.username, 'password': self.password},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json().get('auth_token')
            else:
                self.stdout.write(
                    self.style.ERROR(f'Error de login: {response.status_code} - {response.text}')
                )
                return None
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error conectando: {e}'))
            return None

    def _get_endpoints_to_test(self):
        """Define todos los endpoints a probar organizados por módulo - URLs CORREGIDAS."""
        return {
            'HEALTH CHECK': [
                {'name': 'Health Check', 'url': '/api/health/', 'auth': False, 'method': 'GET'},
            ],
            
            'AUTENTICACIÓN': [
                {'name': 'Auth Users Me', 'url': '/api/auth/users/me/', 'auth': True, 'method': 'GET'},
                {'name': 'Auth Users List', 'url': '/api/auth/users/', 'auth': True, 'method': 'GET'},
            ],
            
            'CATÁLOGOS': [
                {'name': 'Categories List', 'url': '/api/catalogs/categories/', 'auth': True, 'method': 'GET'},
                {'name': 'Products List (Paginado)', 'url': '/api/catalogs/products/', 'auth': True, 'method': 'GET'},
                {'name': 'Products All (CRÍTICO)', 'url': '/api/catalogs/products/all/', 'auth': True, 'method': 'GET'},
                {'name': 'Product Components', 'url': '/api/catalogs/product-components/', 'auth': True, 'method': 'GET'},
                {'name': 'Product Batches', 'url': '/api/catalogs/product-batches/', 'auth': True, 'method': 'GET'},
                {'name': 'Batches Expiring Soon', 'url': '/api/catalogs/product-batches/expiring_soon/', 'auth': True, 'method': 'GET'},
                {'name': 'Batches Expired', 'url': '/api/catalogs/product-batches/expired/', 'auth': True, 'method': 'GET'},
            ],
            
            'PROVEEDORES': [
                {'name': 'Suppliers List', 'url': '/api/suppliers/suppliers/', 'auth': True, 'method': 'GET'},
                {'name': 'Purchase Options', 'url': '/api/suppliers/purchase-options/', 'auth': True, 'method': 'GET'},
                {'name': 'Valid Purchase Options', 'url': '/api/suppliers/purchase-options/valid_options/', 'auth': True, 'method': 'GET'},
            ],
            
            'INVENTARIO': [
                {'name': 'Locations', 'url': '/api/inventory/locations/', 'auth': True, 'method': 'GET'},
                {'name': 'Stock List', 'url': '/api/inventory/stock/', 'auth': True, 'method': 'GET'},
                {'name': 'Stock All (CRÍTICO)', 'url': '/api/inventory/stock/all/', 'auth': True, 'method': 'GET'},
                {'name': 'Stock Summary (CRÍTICO)', 'url': '/api/inventory/stock/summary/', 'auth': True, 'method': 'GET'},
                {'name': 'Movements', 'url': '/api/inventory/movements/', 'auth': True, 'method': 'GET'},
                {'name': 'Stock Alerts', 'url': '/api/inventory/movements/stock_alerts/', 'auth': True, 'method': 'GET'},
                {'name': 'Expiry Alerts', 'url': '/api/inventory/movements/expiry_alerts/', 'auth': True, 'method': 'GET'},
                {'name': 'Expiring Stock', 'url': '/api/inventory/movements/expiring_stock/', 'auth': True, 'method': 'GET'},
                {'name': 'By Batches', 'url': '/api/inventory/movements/by_batches/', 'auth': True, 'method': 'GET'},
            ],
            
            'COMPRAS': [
                {'name': 'Purchase Orders', 'url': '/api/purchases/orders/', 'auth': True, 'method': 'GET'},
                {'name': 'Purchase Order Items', 'url': '/api/purchases/items/', 'auth': True, 'method': 'GET'},
                {'name': 'Purchase Statistics', 'url': '/api/purchases/orders/statistics/', 'auth': True, 'method': 'GET'},
                {'name': 'Alternative Brands', 'url': '/api/purchases/items/alternative_brands/', 'auth': True, 'method': 'GET'},
            ],
            
            'VENTAS': [
                {'name': 'Customers', 'url': '/api/sales/customers/', 'auth': True, 'method': 'GET'},
                {'name': 'Sales List', 'url': '/api/sales/sales/', 'auth': True, 'method': 'GET'},
                {'name': 'Sales Statistics (CRÍTICO)', 'url': '/api/sales/sales/statistics/', 'auth': True, 'method': 'GET'},
                {'name': 'Sales by Location', 'url': '/api/sales/sales/by_location/', 'auth': True, 'method': 'GET'},
                {'name': 'Sales Today', 'url': '/api/sales/sales/today/', 'auth': True, 'method': 'GET'},
                {'name': 'Sale Items', 'url': '/api/sales/sale-items/', 'auth': True, 'method': 'GET'},
                {'name': 'Top Products', 'url': '/api/sales/sale-items/top_products/', 'auth': True, 'method': 'GET'},
                {'name': 'Returns', 'url': '/api/sales/returns/', 'auth': True, 'method': 'GET'},
                {'name': 'Return Items', 'url': '/api/sales/return-items/', 'auth': True, 'method': 'GET'},
                {'name': 'Returns Statistics', 'url': '/api/sales/returns/statistics/', 'auth': True, 'method': 'GET'},
                {'name': 'Returns by Location', 'url': '/api/sales/returns/by_location/', 'auth': True, 'method': 'GET'},
                {'name': 'Top Returned Products', 'url': '/api/sales/return-items/top_returned_products/', 'auth': True, 'method': 'GET'},
            ],
            
            'CRÉDITOS': [
                {'name': 'Credit Accounts', 'url': '/api/credits/accounts/', 'auth': True, 'method': 'GET'},
                {'name': 'Debt Summary (CRÍTICO)', 'url': '/api/credits/accounts/debt_summary/', 'auth': True, 'method': 'GET'},
                {'name': 'Overdue Accounts', 'url': '/api/credits/accounts/overdue_accounts/', 'auth': True, 'method': 'GET'},
                {'name': 'Credit Statistics', 'url': '/api/credits/accounts/statistics/', 'auth': True, 'method': 'GET'},
                {'name': 'Credit Payments', 'url': '/api/credits/payments/', 'auth': True, 'method': 'GET'},
                {'name': 'Recent Payments', 'url': '/api/credits/payments/recent_payments/', 'auth': True, 'method': 'GET'},
            ],
            
            'ENTREGAS': [
                {'name': 'Deliveries List', 'url': '/api/deliveries/deliveries/', 'auth': True, 'method': 'GET'},
                {'name': 'Delivery Statistics', 'url': '/api/deliveries/deliveries/statistics/', 'auth': True, 'method': 'GET'},
                {'name': 'Overdue Deliveries', 'url': '/api/deliveries/deliveries/overdue/', 'auth': True, 'method': 'GET'},
                {'name': 'Location Summary', 'url': '/api/deliveries/deliveries/location_summary/', 'auth': True, 'method': 'GET'},
                {'name': 'By Route', 'url': '/api/deliveries/deliveries/by_route/', 'auth': True, 'method': 'GET'},
            ],
        }

    def _test_endpoint(self, endpoint_info):
        """Prueba un endpoint específico y mide su rendimiento."""
        url = f"{self.base_url}{endpoint_info['url']}"
        headers = {}
        
        if endpoint_info.get('auth', True):
            headers['Authorization'] = f'Token {self.token}'
        
        start_queries = len(connection.queries) if self.detailed else 0
        start_time = time.time()
        
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response_time = (time.time() - start_time) * 1000
            
            end_queries = len(connection.queries) if self.detailed else 0
            query_count = end_queries - start_queries
            
            return {
                'name': endpoint_info['name'],
                'url': endpoint_info['url'],
                'status_code': response.status_code,
                'response_time': response_time,
                'query_count': query_count if self.detailed else 0,
                'response_size': len(response.content),
                'error': None if response.status_code < 400 else f'HTTP {response.status_code}'
            }
            
        except requests.exceptions.Timeout:
            return {
                'name': endpoint_info['name'],
                'url': endpoint_info['url'],
                'status_code': 0,
                'response_time': self.timeout * 1000,
                'query_count': 0,
                'response_size': 0,
                'error': 'TIMEOUT'
            }
        except Exception as e:
            return {
                'name': endpoint_info['name'],
                'url': endpoint_info['url'],
                'status_code': 0,
                'response_time': 0,
                'query_count': 0,
                'response_size': 0,
                'error': str(e)
            }

    def _get_status_icon(self, response_time):
        """Retorna un ícono basado en el tiempo de respuesta."""
        if response_time < 100:
            return '🟢'  # Excelente
        elif response_time < 500:
            return '🟡'  # Bueno
        elif response_time < 2000:
            return '🟠'  # Lento
        else:
            return '🔴'  # Crítico

    def _generate_report(self, results, total_time):
        """Genera un reporte final del benchmark."""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('📊 REPORTE FINAL DE RENDIMIENTO'))
        self.stdout.write('=' * 80)
        
        # Estadísticas generales
        successful_tests = [r for r in results if not r['error']]
        failed_tests = [r for r in results if r['error']]
        
        if successful_tests:
            avg_time = sum(r['response_time'] for r in successful_tests) / len(successful_tests)
            min_time = min(r['response_time'] for r in successful_tests)
            max_time = max(r['response_time'] for r in successful_tests)
            
            self.stdout.write(f'✅ Tests exitosos: {len(successful_tests)}/{len(results)}')
            self.stdout.write(f'⏱️  Tiempo promedio: {avg_time:.2f}ms')
            self.stdout.write(f'🏃 Más rápido: {min_time:.2f}ms')
            self.stdout.write(f'🐌 Más lento: {max_time:.2f}ms')
            self.stdout.write(f'⏰ Tiempo total: {total_time:.2f}s')
        
        # Endpoints críticos (> 2 segundos)
        critical_endpoints = [r for r in successful_tests if r['response_time'] > 2000]
        if critical_endpoints:
            self.stdout.write(f'\n🚨 ENDPOINTS CRÍTICOS (>{2000}ms):')
            self.stdout.write('-' * 60)
            for endpoint in sorted(critical_endpoints, key=lambda x: x['response_time'], reverse=True):
                self.stdout.write(
                    f'🔴 {endpoint["name"]:<40} {endpoint["response_time"]:.2f}ms'
                )
        
        # Endpoints lentos (500ms - 2s)
        slow_endpoints = [r for r in successful_tests if 500 < r['response_time'] <= 2000]
        if slow_endpoints:
            self.stdout.write(f'\n⚠️  ENDPOINTS LENTOS (500-2000ms):')
            self.stdout.write('-' * 60)
            for endpoint in sorted(slow_endpoints, key=lambda x: x['response_time'], reverse=True):
                self.stdout.write(
                    f'🟠 {endpoint["name"]:<40} {endpoint["response_time"]:.2f}ms'
                )
        
        # Endpoints fallidos
        if failed_tests:
            self.stdout.write(f'\n❌ ENDPOINTS FALLIDOS:')
            self.stdout.write('-' * 60)
            for endpoint in failed_tests:
                self.stdout.write(
                    f'❌ {endpoint["name"]:<40} {endpoint["error"]}'
                )
        
        # Recomendaciones
        self.stdout.write(f'\n💡 RECOMENDACIONES:')
        self.stdout.write('-' * 60)
        
        if critical_endpoints:
            self.stdout.write('🔥 ACCIÓN INMEDIATA REQUERIDA:')
            for endpoint in critical_endpoints[:3]:  # Top 3 críticos
                self.stdout.write(f'   • Optimizar: {endpoint["name"]} ({endpoint["response_time"]:.2f}ms)')
        
        if len(slow_endpoints) > 5:
            self.stdout.write('⚡ Considera optimizar endpoints lentos con:')
            self.stdout.write('   • select_related() y prefetch_related()')
            self.stdout.write('   • Índices de base de datos')
            self.stdout.write('   • Paginación más agresiva')
            self.stdout.write('   • Caché de consultas frecuentes')
        
        self.stdout.write(f'\n✅ Benchmark completado en {total_time:.2f} segundos')
        self.stdout.write('=' * 80) 