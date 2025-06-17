import time
import psutil
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from catalogs.models import Product, Category
from inventory.models import InventoryStock
from sales.models import Sale
from purchases.models import PurchaseOrder


class Command(BaseCommand):
    help = 'Realiza un chequeo de salud del sistema para diagnosticar problemas de rendimiento'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Realizar un chequeo completo incluyendo consultas complejas'
        )
        parser.add_argument(
            '--db-only',
            action='store_true',
            help='Solo verificar la base de datos'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🏥 INICIANDO CHEQUEO DE SALUD DEL SISTEMA'))
        self.stdout.write('=' * 60)
        
        start_time = time.time()
        
        # Información del sistema
        if not options['db_only']:
            self._check_system_resources()
        
        # Verificar configuración de Django
        self._check_django_config()
        
        # Verificar conexión a la base de datos
        self._check_database_connection()
        
        # Verificar rendimiento de consultas básicas
        self._check_basic_queries()
        
        if options['full']:
            # Verificar consultas complejas
            self._check_complex_queries()
            
            # Verificar caché
            self._check_cache()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        self.stdout.write('=' * 60)
        self.stdout.write(
            self.style.SUCCESS(f'✅ CHEQUEO COMPLETADO EN {total_time:.2f} segundos')
        )
        
        if total_time > 10:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  El sistema está respondiendo lentamente. '
                    'Revisa la configuración de la base de datos y Railway.'
                )
            )

    def _check_system_resources(self):
        """Verificar recursos del sistema."""
        self.stdout.write('\n🖥️  RECURSOS DEL SISTEMA:')
        
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            self.stdout.write(f'   CPU: {cpu_percent}%')
            
            # Memoria
            memory = psutil.virtual_memory()
            self.stdout.write(f'   Memoria: {memory.percent}% ({memory.used / 1024**2:.1f}MB / {memory.total / 1024**2:.1f}MB)')
            
            # Disco
            disk = psutil.disk_usage('/')
            self.stdout.write(f'   Disco: {disk.percent}% ({disk.used / 1024**3:.1f}GB / {disk.total / 1024**3:.1f}GB)')
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  No se pudo obtener información del sistema: {e}')
            )

    def _check_django_config(self):
        """Verificar configuración de Django."""
        self.stdout.write('\n⚙️  CONFIGURACIÓN DE DJANGO:')
        
        self.stdout.write(f'   DEBUG: {settings.DEBUG}')
        self.stdout.write(f'   ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}')
        
        # Verificar configuración de base de datos
        db_config = settings.DATABASES['default']
        self.stdout.write(f'   DB Engine: {db_config.get("ENGINE", "N/A")}')
        self.stdout.write(f'   DB CONN_MAX_AGE: {db_config.get("CONN_MAX_AGE", "N/A")}')
        
        # Verificar caché
        cache_config = settings.CACHES['default']
        self.stdout.write(f'   Cache Backend: {cache_config.get("BACKEND", "N/A")}')

    def _check_database_connection(self):
        """Verificar conexión a la base de datos."""
        self.stdout.write('\n🗄️  BASE DE DATOS:')
        
        try:
            start_time = time.time()
            
            # Probar conexión básica
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            
            connection_time = (time.time() - start_time) * 1000
            
            if result[0] == 1:
                self.stdout.write(f'   ✅ Conexión exitosa ({connection_time:.2f}ms)')
            else:
                self.stdout.write(
                    self.style.ERROR('   ❌ Error en la conexión')
                )
                
            # Verificar pool de conexiones
            self.stdout.write(f'   Queries ejecutadas: {len(connection.queries)}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Error de conexión: {e}')
            )

    def _check_basic_queries(self):
        """Verificar rendimiento de consultas básicas."""
        self.stdout.write('\n🔍 CONSULTAS BÁSICAS:')
        
        queries = [
            ('Categorías', Category.objects.count),
            ('Productos', Product.objects.count),
            ('Stock', InventoryStock.objects.count),
            ('Ventas', Sale.objects.count),
            ('Órdenes de compra', PurchaseOrder.objects.count),
        ]
        
        for name, query_func in queries:
            try:
                start_time = time.time()
                count = query_func()
                query_time = (time.time() - start_time) * 1000
                
                status = '✅' if query_time < 100 else '⚠️' if query_time < 500 else '❌'
                self.stdout.write(f'   {status} {name}: {count} registros ({query_time:.2f}ms)')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Error en {name}: {e}')
                )

    def _check_complex_queries(self):
        """Verificar rendimiento de consultas complejas."""
        self.stdout.write('\n🔍 CONSULTAS COMPLEJAS:')
        
        complex_queries = [
            ('Productos con stock', lambda: Product.objects.filter(stock_locations__quantity__gt=0).distinct().count()),
            ('Ventas con items', lambda: Sale.objects.prefetch_related('items').count()),
            ('Stock por ubicación', lambda: InventoryStock.objects.select_related('product', 'location').count()),
        ]
        
        for name, query_func in complex_queries:
            try:
                start_time = time.time()
                result = query_func()
                query_time = (time.time() - start_time) * 1000
                
                status = '✅' if query_time < 200 else '⚠️' if query_time < 1000 else '❌'
                self.stdout.write(f'   {status} {name}: {result} registros ({query_time:.2f}ms)')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Error en {name}: {e}')
                )

    def _check_cache(self):
        """Verificar funcionamiento del caché."""
        self.stdout.write('\n🚀 CACHÉ:')
        
        try:
            # Probar escritura en caché
            start_time = time.time()
            cache.set('health_check_test', 'test_value', 60)
            write_time = (time.time() - start_time) * 1000
            
            # Probar lectura de caché
            start_time = time.time()
            cached_value = cache.get('health_check_test')
            read_time = (time.time() - start_time) * 1000
            
            if cached_value == 'test_value':
                self.stdout.write(f'   ✅ Caché funcionando (Write: {write_time:.2f}ms, Read: {read_time:.2f}ms)')
            else:
                self.stdout.write(
                    self.style.WARNING('   ⚠️  Caché no está funcionando correctamente')
                )
                
            # Limpiar caché de prueba
            cache.delete('health_check_test')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Error en caché: {e}')
            ) 