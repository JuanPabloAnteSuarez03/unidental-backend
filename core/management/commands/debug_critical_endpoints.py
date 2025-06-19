import time
import traceback
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import connection, reset_queries
from django.test.utils import override_settings
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Diagnostica los endpoints críticos que están causando timeouts con análisis detallado de SQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default='admin_unidental',
            help='Usuario para autenticación'
        )
        parser.add_argument(
            '--password',
            default='admin123',
            help='Password para autenticación'
        )

    def handle(self, *args, **options):
        self.username = options['username']
        self.password = options['password']
        
        self.stdout.write(self.style.SUCCESS('🔍 DIAGNÓSTICO DE ENDPOINTS CRÍTICOS'))
        self.stdout.write('=' * 80)
        
        # Configurar cliente de prueba
        self.client = APIClient()
        
        # Autenticar
        if not self._authenticate():
            self.stdout.write(self.style.ERROR('❌ Error de autenticación'))
            return
        
        # Endpoints críticos que están causando timeouts
        critical_endpoints = [
            {
                'name': '🔥 Products All (5 min timeout)',
                'url': '/api/catalogs/products/all/',
                'expected_issue': 'N+1 queries, sin select_related/prefetch_related'
            },
            {
                'name': '🔥 Stock Summary (timeout)',
                'url': '/api/inventory/stock/summary/',
                'expected_issue': 'Agregaciones complejas sin optimización'
            },
            {
                'name': '🔥 Sales Statistics (timeout)',
                'url': '/api/sales/sales/statistics/',
                'expected_issue': 'Consultas de agregación sin índices'
            },
            {
                'name': '🔥 Debt Summary (timeout)',
                'url': '/api/credits/accounts/debt_summary/',
                'expected_issue': 'Cálculos complejos sin caché'
            }
        ]
        
        for endpoint in critical_endpoints:
            self._analyze_endpoint(endpoint)
            self.stdout.write('-' * 60)
        
        self._generate_optimization_report()

    def _authenticate(self):
        """Autentica usando el APIClient de Django REST Framework."""
        try:
            # Intentar obtener usuario existente
            user = User.objects.filter(username=self.username).first()
            if not user:
                self.stdout.write(self.style.ERROR(f'Usuario {self.username} no encontrado'))
                return False
            
            # Obtener o crear token
            token, created = Token.objects.get_or_create(user=user)
            
            # Configurar autenticación
            self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
            
            self.stdout.write(self.style.SUCCESS(f'✅ Autenticado como: {self.username}'))
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error de autenticación: {e}'))
            return False

    def _analyze_endpoint(self, endpoint):
        """Analiza un endpoint específico con métricas detalladas."""
        self.stdout.write(f'\n📊 ANALIZANDO: {endpoint["name"]}')
        self.stdout.write(f'🎯 URL: {endpoint["url"]}')
        self.stdout.write(f'🔍 Problema esperado: {endpoint["expected_issue"]}')
        
        # Reset SQL queries counter
        reset_queries()
        
        # Medir tiempo y ejecutar request
        start_time = time.time()
        
        try:
            # Timeout de 10 segundos para endpoints críticos
            with override_settings(DEBUG=True):  # Enable SQL logging
                response = self.client.get(endpoint['url'], timeout=10)
            
            response_time = (time.time() - start_time) * 1000
            query_count = len(connection.queries)
            
            # Análisis de respuesta
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        record_count = data.get('count', len(data.get('results', [])))
                        if 'results' not in data:
                            record_count = len(data) if isinstance(data, list) else 1
                    else:
                        record_count = len(data) if isinstance(data, list) else 1
                except:
                    record_count = 0
                
                self.stdout.write(self.style.SUCCESS(f'✅ Status: {response.status_code}'))
                self.stdout.write(f'⏱️  Tiempo: {response_time:.2f}ms')
                self.stdout.write(f'🗃️  SQL Queries: {query_count}')
                self.stdout.write(f'📝 Records: {record_count}')
                
                # Análisis de eficiencia
                if query_count > 0:
                    queries_per_record = query_count / max(record_count, 1)
                    self.stdout.write(f'🔢 Queries/Record: {queries_per_record:.2f}')
                    
                    if queries_per_record > 2:
                        self.stdout.write(self.style.ERROR('🚨 PROBLEMA N+1 DETECTADO'))
                
                # Categorizar rendimiento
                if response_time > 5000:
                    self.stdout.write(self.style.ERROR('🔴 CRÍTICO: >5 segundos'))
                elif response_time > 2000:
                    self.stdout.write(self.style.WARNING('🟠 LENTO: >2 segundos'))
                elif response_time > 500:
                    self.stdout.write(self.style.WARNING('🟡 MODERADO: >500ms'))
                else:
                    self.stdout.write(self.style.SUCCESS('🟢 BUENO: <500ms'))
                
                # Mostrar queries más problemáticas
                self._analyze_sql_queries(endpoint['url'])
                
            else:
                self.stdout.write(self.style.ERROR(f'❌ Status: {response.status_code}'))
                self.stdout.write(f'❌ Error: {response.content[:200]}')
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.stdout.write(self.style.ERROR(f'💥 EXCEPCIÓN: {str(e)}'))
            self.stdout.write(f'⏱️  Tiempo hasta error: {response_time:.2f}ms')
            
            # Mostrar traceback si es útil
            if 'timeout' not in str(e).lower():
                self.stdout.write(f'🔍 Traceback: {traceback.format_exc()[:500]}')

    def _analyze_sql_queries(self, endpoint_url):
        """Analiza las consultas SQL ejecutadas."""
        if not connection.queries:
            return
        
        # Contar tipos de queries
        select_queries = [q for q in connection.queries if q['sql'].strip().upper().startswith('SELECT')]
        
        if len(select_queries) > 10:
            self.stdout.write(f'⚠️  {len(select_queries)} SELECT queries (posible N+1)')
        
        # Encontrar queries más lentas
        slow_queries = []
        for query in connection.queries:
            try:
                time_taken = float(query['time'])
                if time_taken > 0.1:  # Más de 100ms
                    slow_queries.append((time_taken, query['sql'][:100]))
            except:
                pass
        
        if slow_queries:
            self.stdout.write('🐌 QUERIES LENTAS (>100ms):')
            for time_taken, sql in sorted(slow_queries, reverse=True)[:3]:
                self.stdout.write(f'   {time_taken:.3f}s: {sql}...')
        
        # Detectar patterns problemáticos
        sql_text = ' '.join([q['sql'] for q in connection.queries])
        
        if 'JOIN' not in sql_text.upper() and len(select_queries) > 5:
            self.stdout.write(self.style.WARNING('⚠️  Sin JOINs con múltiples queries - considera select_related()'))
        
        if sql_text.upper().count('SELECT') > sql_text.upper().count('JOIN') * 3:
            self.stdout.write(self.style.WARNING('⚠️  Ratio SELECT/JOIN alto - posible N+1'))

    def _generate_optimization_report(self):
        """Genera reporte con recomendaciones específicas."""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('🚀 REPORTE DE OPTIMIZACIÓN'))
        self.stdout.write('=' * 80)
        
        recommendations = [
            {
                'endpoint': '/api/catalogs/products/all/',
                'problem': 'Carga todos los productos sin optimización',
                'solutions': [
                    'Agregar select_related("category") en el queryset',
                    'Considerar prefetch_related() para relaciones M2M',
                    'Implementar paginación automática para listas grandes',
                    'Agregar índices en campos de filtro frecuentes',
                    'Considerar caché Redis para productos estables'
                ]
            },
            {
                'endpoint': '/api/inventory/stock/summary/',
                'problem': 'Agregaciones complejas sin optimización',
                'solutions': [
                    'Usar annotate() para agregaciones en base de datos',
                    'Implementar caché para resúmenes que no cambian frecuentemente',
                    'Crear vistas materializadas en PostgreSQL',
                    'Usar queryset.aggregate() en lugar de loops Python',
                    'Considerar jobs background para cálculos pesados'
                ]
            },
            {
                'endpoint': '/api/sales/sales/statistics/',
                'problem': 'Consultas de estadísticas sin índices',
                'solutions': [
                    'Crear índices compuestos en (fecha, estado, location)',
                    'Usar Django aggregation framework',
                    'Implementar caché de estadísticas por períodos',
                    'Pre-calcular estadísticas diarias/mensuales',
                    'Usar raw SQL optimizado para consultas complejas'
                ]
            },
            {
                'endpoint': '/api/credits/accounts/debt_summary/',
                'problem': 'Cálculos de deuda en tiempo real',
                'solutions': [
                    'Desnormalizar totales de deuda en modelo Customer',
                    'Usar signals para actualizar balances incrementalmente',
                    'Implementar caché Redis con invalidación inteligente',
                    'Crear tabla resumen actualizada por triggers',
                    'Paginar resultados de cuentas con deuda'
                ]
            }
        ]
        
        for rec in recommendations:
            self.stdout.write(f'\n🎯 {rec["endpoint"]}')
            self.stdout.write(f'❌ Problema: {rec["problem"]}')
            self.stdout.write('✅ Soluciones:')
            for i, solution in enumerate(rec['solutions'], 1):
                self.stdout.write(f'   {i}. {solution}')
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('💡 PRIORIDADES DE IMPLEMENTACIÓN:')
        self.stdout.write('=' * 80)
        self.stdout.write('1. 🔥 INMEDIATO: Agregar select_related() en ProductViewSet')
        self.stdout.write('2. 🔥 INMEDIATO: Implementar paginación en /products/all/')
        self.stdout.write('3. 🟡 MEDIO: Optimizar agregaciones en stock/summary')
        self.stdout.write('4. 🟡 MEDIO: Caché para estadísticas de ventas')
        self.stdout.write('5. 🟢 LARGO: Desnormalización para cálculos de crédito')
        
        self.stdout.write('\n✅ Diagnóstico completado')
        self.stdout.write('💻 Siguiente paso: python manage.py benchmark_endpoints --detailed') 