import time
import requests
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Prueba rápida de los endpoints críticos optimizados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url',
            default='http://127.0.0.1:8000',
            help='URL base del servidor'
        )
        parser.add_argument(
            '--username',
            default='admin_unidental',
            help='Usuario para autenticación'
        )

    def handle(self, *args, **options):
        self.base_url = options['base_url'].rstrip('/')
        self.username = options['username']
        
        self.stdout.write(self.style.SUCCESS('🚀 PROBANDO OPTIMIZACIONES CRÍTICAS'))
        self.stdout.write('=' * 70)
        
        # Obtener token
        self.token = self._get_auth_token()
        if not self.token:
            self.stdout.write(self.style.ERROR('❌ No se pudo autenticar'))
            return
        
        # Endpoints críticos que optimizamos
        critical_endpoints = [
            {
                'name': 'Stock Summary (era TIMEOUT)',
                'url': '/api/inventory/stock/summary/',
                'target': '<2000ms'
            },
            {
                'name': 'Products All (era TIMEOUT)', 
                'url': '/api/catalogs/products/all/',
                'target': '<3000ms'
            },
            {
                'name': 'Returns (era 22.8s)',
                'url': '/api/sales/returns/',
                'target': '<5000ms'
            },
            {
                'name': 'Deliveries (era 17.9s)',
                'url': '/api/deliveries/deliveries/',
                'target': '<5000ms'
            },
            {
                'name': 'Return Items (era 10.6s)',
                'url': '/api/sales/return-items/',
                'target': '<3000ms'
            },
            {
                'name': 'Sale Items (era 8.6s)',
                'url': '/api/sales/sale-items/',
                'target': '<3000ms'
            }
        ]
        
        results = []
        for endpoint in critical_endpoints:
            result = self._test_endpoint(endpoint)
            results.append(result)
            
            # Mostrar resultado
            if result['success']:
                time_ms = result['time_ms']
                if time_ms < 2000:
                    icon = '🟢'
                elif time_ms < 5000:
                    icon = '🟡'
                else:
                    icon = '🔴'
                
                self.stdout.write(
                    f'{icon} {endpoint["name"]:<35} {time_ms:.0f}ms ({endpoint["target"]})'
                )
            else:
                self.stdout.write(
                    f'❌ {endpoint["name"]:<35} ERROR: {result["error"]}'
                )
        
        # Resumen
        self._show_summary(results)

    def _get_auth_token(self):
        """Obtiene token de autenticación."""
        try:
            user = User.objects.filter(username=self.username).first()
            if not user:
                return None
            
            token, created = Token.objects.get_or_create(user=user)
            return token.key
        except Exception:
            return None

    def _test_endpoint(self, endpoint):
        """Prueba un endpoint y mide su tiempo."""
        url = f"{self.base_url}{endpoint['url']}"
        headers = {'Authorization': f'Token {self.token}'}
        
        start_time = time.time()
        try:
            response = requests.get(url, headers=headers, timeout=30)
            end_time = time.time()
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'time_ms': (end_time - start_time) * 1000,
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'time_ms': (end_time - start_time) * 1000
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'TIMEOUT (30s)',
                'time_ms': 30000
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'time_ms': 0
            }

    def _show_summary(self, results):
        """Muestra resumen de las optimizaciones."""
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 RESUMEN DE OPTIMIZACIONES'))
        self.stdout.write('=' * 70)
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        if successful:
            avg_time = sum(r['time_ms'] for r in successful) / len(successful)
            self.stdout.write(f'✅ Endpoints exitosos: {len(successful)}/{len(results)}')
            self.stdout.write(f'⏱️  Tiempo promedio: {avg_time:.0f}ms')
            
            fast_endpoints = [r for r in successful if r['time_ms'] < 2000]
            if fast_endpoints:
                self.stdout.write(f'🟢 Rápidos (<2s): {len(fast_endpoints)}')
            
            slow_endpoints = [r for r in successful if r['time_ms'] >= 5000]
            if slow_endpoints:
                self.stdout.write(f'🔴 Aún lentos (>5s): {len(slow_endpoints)}')
        
        if failed:
            self.stdout.write(f'❌ Endpoints fallidos: {len(failed)}')
        
        self.stdout.write('\n💡 PRÓXIMOS PASOS:')
        self.stdout.write('1. Ejecutar benchmark completo: python manage.py benchmark_endpoints')
        self.stdout.write('2. Si aún hay timeouts, revisar índices de base de datos')
        self.stdout.write('3. Considerar implementar caché Redis para endpoints lentos')
        
        self.stdout.write('\n✅ Prueba de optimizaciones completada') 