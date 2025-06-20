from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from datetime import date, timedelta
from catalogs.models import Category, Product, ProductBatch, ProductComponent
from inventory.models import Location, InventoryStock, InventoryMovement
import random


class Command(BaseCommand):
    help = 'Crea productos de prueba con lotes y componentes para testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Elimina los productos de prueba existentes antes de crear nuevos',
        )

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                if options['clean']:
                    self.clean_test_data()
                
                self.create_test_data()
                self.stdout.write(
                    self.style.SUCCESS('Productos de prueba creados exitosamente!')
                )
        except Exception as e:
            raise CommandError(f'Error creando productos de prueba: {str(e)}')

    def clean_test_data(self):
        """Elimina productos de prueba existentes."""
        self.stdout.write('Eliminando productos de prueba existentes...')
        
        # Eliminar stock de productos de prueba
        test_products = Product.objects.filter(sku__startswith='TEST-')
        stock_count = InventoryStock.objects.filter(product__in=test_products).count()
        InventoryStock.objects.filter(product__in=test_products).delete()
        
        # Eliminar movimientos de productos de prueba
        movement_count = InventoryMovement.objects.filter(product__in=test_products).count()
        InventoryMovement.objects.filter(product__in=test_products).delete()
        
        # Eliminar productos que empiecen con TEST-
        product_count = test_products.count()
        test_products.delete()
        
        # Eliminar categorías de prueba
        category_count = Category.objects.filter(name__startswith='Test ').count()
        Category.objects.filter(name__startswith='Test ').delete()
        
        # Eliminar ubicaciones de prueba
        location_count = Location.objects.filter(name__startswith='Test ').count()
        Location.objects.filter(name__startswith='Test ').delete()
        
        self.stdout.write(
            f'Eliminados: {product_count} productos, {category_count} categorías, '
            f'{location_count} ubicaciones, {stock_count} registros de stock, '
            f'{movement_count} movimientos'
        )

    def create_test_data(self):
        """Crea productos de prueba con diferentes configuraciones."""
        self.stdout.write('Creando productos de prueba...')
        
        # 1. Crear ubicaciones de prueba
        locations = self.create_test_locations()
        
        # 2. Crear categorías de prueba
        cat_medicamentos = self.create_category(
            'Test Medicamentos',
            'Categoría de prueba para medicamentos con control de lotes'
        )
        
        cat_equipos = self.create_category(
            'Test Equipamiento',
            'Categoría de prueba para equipos sin control de lotes'
        )
        
        cat_kits = self.create_category(
            'Test Kits/Cajas',
            'Categoría de prueba para productos compuestos'
        )
        
        # 3. Crear productos simples con lotes
        products_with_batches = self.create_products_with_batches(cat_medicamentos)
        
        # 4. Crear productos simples sin lotes
        products_without_batches = self.create_products_without_batches(cat_equipos)
        
        # 5. Crear productos compuestos y sus componentes
        composite_products = self.create_composite_products(cat_kits, cat_medicamentos)
        
        # 6. Crear stock inicial para todos los productos
        all_products = products_with_batches + products_without_batches + composite_products
        self.create_initial_stock(all_products, locations)

    def create_test_locations(self):
        """Crea ubicaciones de prueba."""
        self.stdout.write('Creando ubicaciones de prueba...')
        
        locations_data = [
            {
                'name': 'Test Bodega Central',
                'type': 'bodega',
                'address': 'Av. Central 123 - UBICACIÓN DE PRUEBA'
            },
            {
                'name': 'Test Sede Norte',
                'type': 'sede',
                'address': 'Calle Norte 456 - UBICACIÓN DE PRUEBA'
            },
            {
                'name': 'Test Sede Sur',
                'type': 'sede',
                'address': 'Av. Sur 789 - UBICACIÓN DE PRUEBA'
            }
        ]
        
        locations = []
        for loc_data in locations_data:
            location, created = Location.objects.get_or_create(
                name=loc_data['name'],
                defaults={
                    'type': loc_data['type'],
                    'address': loc_data['address']
                }
            )
            if created:
                self.stdout.write(f'  ✓ Ubicación creada: {loc_data["name"]}')
            locations.append(location)
        
        return locations

    def create_category(self, name, description):
        """Crea una categoría de prueba."""
        category, created = Category.objects.get_or_create(
            name=name,
            defaults={'description': description}
        )
        if created:
            self.stdout.write(f'  ✓ Categoría creada: {name}')
        return category

    def create_products_with_batches(self, category):
        """Crea productos que requieren control de lotes."""
        self.stdout.write('Creando productos con control de lotes...')
        
        products_data = [
            {
                'sku': 'TEST-MED-ANE-001',
                'name': 'Anestesia Lidocaína 2% (Prueba)',
                'description': 'Anestésico local para procedimientos dentales - PRODUCTO DE PRUEBA',
                'unit': 'ampolla',
                'barcode': '7891234567890'
            },
            {
                'sku': 'TEST-MED-ANT-001',
                'name': 'Antibiótico Amoxicilina 500mg (Prueba)',
                'description': 'Antibiótico para infecciones dentales - PRODUCTO DE PRUEBA',
                'unit': 'cápsula',
                'barcode': '7891234567891'
            },
            {
                'sku': 'TEST-MED-ANA-001',
                'name': 'Analgésico Ibuprofeno 600mg (Prueba)',
                'description': 'Analgésico antiinflamatorio - PRODUCTO DE PRUEBA',
                'unit': 'tableta',
                'barcode': '7891234567892'
            }
        ]
        
        products = []
        for product_data in products_data:
            product = Product.objects.create(
                category=category,
                product_type='simple',
                requires_batch_control=True,
                **product_data
            )
            
            # Crear múltiples lotes para cada producto
            self.create_batches_for_product(product)
            products.append(product)
            self.stdout.write(f'  ✓ Producto con lotes: {product.name}')
        
        return products

    def create_products_without_batches(self, category):
        """Crea productos que NO requieren control de lotes."""
        self.stdout.write('Creando productos sin control de lotes...')
        
        products_data = [
            {
                'sku': 'TEST-EQU-FOR-001',
                'name': 'Fórceps Dental Estándar (Prueba)',
                'description': 'Fórceps para extracciones dentales - PRODUCTO DE PRUEBA',
                'unit': 'unidad',
                'barcode': '7891234567893'
            },
            {
                'sku': 'TEST-EQU-ESP-001',
                'name': 'Espejo Dental Plano (Prueba)',
                'description': 'Espejo para examinación dental - PRODUCTO DE PRUEBA',
                'unit': 'unidad',
                'barcode': '7891234567894'
            },
            {
                'sku': 'TEST-EQU-SON-001',
                'name': 'Sonda Periodontal (Prueba)',
                'description': 'Sonda para medición periodontal - PRODUCTO DE PRUEBA',
                'unit': 'unidad',
                'barcode': '7891234567895'
            }
        ]
        
        products = []
        for product_data in products_data:
            product = Product.objects.create(
                category=category,
                product_type='simple',
                requires_batch_control=False,
                **product_data
            )
            products.append(product)
            self.stdout.write(f'  ✓ Producto sin lotes: {product.name}')
        
        return products

    def create_composite_products(self, kit_category, component_category):
        """Crea productos compuestos y sus componentes."""
        self.stdout.write('Creando productos compuestos...')
        
        # 1. Crear componentes primero
        component_products = []
        
        components_data = [
            {
                'sku': 'TEST-COM-IBU-001',
                'name': 'Blister Ibuprofeno 10 tabletas (Prueba)',
                'description': 'Blister individual de ibuprofeno - PRODUCTO DE PRUEBA',
                'unit': 'blister',
                'barcode': '7891234567896'
            },
            {
                'sku': 'TEST-COM-AMO-001',
                'name': 'Blister Amoxicilina 10 cápsulas (Prueba)',
                'description': 'Blister individual de amoxicilina - PRODUCTO DE PRUEBA',
                'unit': 'blister',
                'barcode': '7891234567897'
            },
            {
                'sku': 'TEST-COM-JER-001',
                'name': 'Jeringa Desechable 3ml (Prueba)',
                'description': 'Jeringa estéril desechable - PRODUCTO DE PRUEBA',
                'unit': 'unidad',
                'barcode': '7891234567898'
            }
        ]
        
        for comp_data in components_data:
            component = Product.objects.create(
                category=component_category,
                product_type='component',
                requires_batch_control=True,  # Los componentes también pueden requerir lotes
                **comp_data
            )
            component_products.append(component)
            
            # Crear lotes para los componentes
            self.create_batches_for_product(component)
            self.stdout.write(f'  ✓ Componente: {component.name}')
        
        # 2. Crear productos compuestos
        composite_data = [
            {
                'sku': 'TEST-KIT-IBU-001',
                'name': 'Caja Ibuprofeno 5 Blisters (Prueba)',
                'description': 'Caja conteniendo 5 blisters de ibuprofeno - PRODUCTO DE PRUEBA',
                'unit': 'caja',
                'barcode': '7891234567899',
                'components': [
                    {'product': component_products[0], 'quantity': 5}  # 5 blisters por caja
                ]
            },
            {
                'sku': 'TEST-KIT-AMO-001',
                'name': 'Caja Amoxicilina 3 Blisters (Prueba)',
                'description': 'Caja conteniendo 3 blisters de amoxicilina - PRODUCTO DE PRUEBA',
                'unit': 'caja',
                'barcode': '7891234567900',
                'components': [
                    {'product': component_products[1], 'quantity': 3}  # 3 blisters por caja
                ]
            },
            {
                'sku': 'TEST-KIT-MED-001',
                'name': 'Kit Procedimiento Básico (Prueba)',
                'description': 'Kit completo para procedimientos básicos - PRODUCTO DE PRUEBA',
                'unit': 'kit',
                'barcode': '7891234567901',
                'components': [
                    {'product': component_products[0], 'quantity': 2},  # 2 blisters ibuprofeno
                    {'product': component_products[1], 'quantity': 1},  # 1 blister amoxicilina
                    {'product': component_products[2], 'quantity': 5}   # 5 jeringas
                ]
            }
        ]
        
        composite_products = []
        for comp_data in composite_data:
            components = comp_data.pop('components')
            
            composite_product = Product.objects.create(
                category=kit_category,
                product_type='composite',
                requires_batch_control=False,  # Los compuestos generalmente no tienen lotes propios
                **comp_data
            )
            
            # Crear las relaciones de componentes
            for comp_info in components:
                ProductComponent.objects.create(
                    composite_product=composite_product,
                    component_product=comp_info['product'],
                    quantity=comp_info['quantity']
                )
            
            composite_products.append(composite_product)
            self.stdout.write(f'  ✓ Producto compuesto: {composite_product.name}')
        
        # Retornar todos los productos (componentes + compuestos)
        return component_products + composite_products

    def create_batches_for_product(self, product):
        """Crea múltiples lotes para un producto."""
        if not product.requires_batch_control:
            return
        
        # Crear 3-4 lotes con diferentes fechas de vencimiento
        base_date = date.today()
        
        batches_data = [
            {
                'batch_number': f'LOT-{product.sku[-3:]}-2024A',
                'manufacturing_date': base_date - timedelta(days=30),
                'expiry_date': base_date + timedelta(days=365),  # 1 año
                'supplier_reference': 'PROV-001-2024',
                'notes': 'Lote de prueba - Stock disponible'
            },
            {
                'batch_number': f'LOT-{product.sku[-3:]}-2024B',
                'manufacturing_date': base_date - timedelta(days=15),
                'expiry_date': base_date + timedelta(days=730),  # 2 años
                'supplier_reference': 'PROV-002-2024',
                'notes': 'Lote de prueba - Fecha de vencimiento lejana'
            },
            {
                'batch_number': f'LOT-{product.sku[-3:]}-2023A',
                'manufacturing_date': base_date - timedelta(days=120),
                'expiry_date': base_date + timedelta(days=90),   # Próximo a vencer
                'supplier_reference': 'PROV-001-2023',
                'notes': 'Lote de prueba - Próximo a vencer'
            },
            {
                'batch_number': f'LOT-{product.sku[-3:]}-2023B',
                'manufacturing_date': base_date - timedelta(days=180),
                'expiry_date': base_date - timedelta(days=5),    # Ya expirado
                'supplier_reference': 'PROV-003-2023',
                'notes': 'Lote de prueba - EXPIRADO'
            }
        ]
        
        for batch_data in batches_data:
            ProductBatch.objects.create(
                product=product,
                **batch_data
            )

    def create_initial_stock(self, products, locations):
        """Crea stock inicial para los productos en las ubicaciones."""
        self.stdout.write('Creando stock inicial...')
        
        for product in products:
            for location in locations:
                if product.requires_batch_control:
                    # Para productos con lotes, crear stock para cada lote activo
                    active_batches = product.batches.filter(expiry_date__gte=date.today())
                    for batch in active_batches:
                        # Cantidad aleatoria entre 10 y 100
                        quantity = random.randint(10, 100)
                        
                        # Crear registro de stock
                        stock, created = InventoryStock.objects.get_or_create(
                            product=product,
                            location=location,
                            batch=batch,
                            defaults={'quantity': quantity}
                        )
                        
                        if created:
                            # No crear movimientos automáticamente, solo actualizar el stock
                            # Los movimientos se crean automáticamente en el modelo InventoryMovement
                            pass
                            
                            self.stdout.write(
                                f'  ✓ Stock creado: {product.name} - {location.name} - '
                                f'Lote {batch.batch_number}: {quantity} {product.unit}'
                            )
                else:
                    # Para productos sin lotes, crear stock directo
                    quantity = random.randint(20, 200)
                    
                    stock, created = InventoryStock.objects.get_or_create(
                        product=product,
                        location=location,
                        batch=None,
                        defaults={'quantity': quantity}
                    )
                    
                    if created:
                        # No crear movimientos automáticamente, solo actualizar el stock
                        pass
                        
                        self.stdout.write(
                            f'  ✓ Stock creado: {product.name} - {location.name}: '
                            f'{quantity} {product.unit}'
                        ) 