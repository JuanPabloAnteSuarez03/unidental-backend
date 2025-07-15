from django.core.management.base import BaseCommand
from django.db import transaction
from catalogs.models import Product, ProductComponent, ProductConversion


class Command(BaseCommand):
    help = 'Configura el sistema de productos independientes con conversiones manuales'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué cambios se harían sin ejecutarlos',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: No se harán cambios reales'))
        
        with transaction.atomic():
            # 1. Crear conversiones basadas en productos compuestos existentes
            self.create_conversions_from_composites(dry_run)
            
            # 2. Cambiar todos los productos a tipo 'simple'
            self.convert_products_to_simple(dry_run)
            
            if dry_run:
                self.stdout.write(self.style.WARNING('No se realizaron cambios (dry-run mode)'))
                # Hacer rollback en dry-run
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS('¡Sistema de productos independientes configurado exitosamente!'))

    def create_conversions_from_composites(self, dry_run):
        """Crea conversiones manuales basadas en los productos compuestos existentes."""
        
        composite_products = Product.objects.filter(
            product_type__in=['boxed_component', 'mixed_kit', 'composite']
        )
        
        conversions_created = 0
        
        for composite in composite_products:
            components = composite.get_components()
            
            for component_rel in components:
                # Crear conversión del producto compuesto al componente
                conversion_data = {
                    'from_product': composite,
                    'to_product': component_rel.component_product,
                    'conversion_rate': component_rel.quantity,
                    'is_reversible': False  # Por defecto no reversible
                }
                
                if not dry_run:
                    conversion, created = ProductConversion.objects.get_or_create(
                        from_product=composite,
                        to_product=component_rel.component_product,
                        defaults={
                            'conversion_rate': component_rel.quantity,
                            'is_reversible': False
                        }
                    )
                    if created:
                        conversions_created += 1
                        self.stdout.write(
                            f"✓ Conversión creada: 1 {composite.name} → {component_rel.quantity} {component_rel.component_product.name}"
                        )
                else:
                    self.stdout.write(
                        f"[DRY-RUN] Crearía conversión: 1 {composite.name} → {component_rel.quantity} {component_rel.component_product.name}"
                    )
                    conversions_created += 1
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'✓ {conversions_created} conversiones creadas desde productos compuestos')
            )
        else:
            self.stdout.write(f'[DRY-RUN] Se crearían {conversions_created} conversiones')

    def convert_products_to_simple(self, dry_run):
        """Convierte todos los productos a tipo 'simple'."""
        
        products_to_update = Product.objects.exclude(product_type='simple')
        count = products_to_update.count()
        
        if count == 0:
            self.stdout.write('✓ Todos los productos ya son de tipo simple')
            return
        
        if not dry_run:
            updated = products_to_update.update(product_type='simple')
            self.stdout.write(
                self.style.SUCCESS(f'✓ {updated} productos convertidos a tipo simple')
            )
            
            # Mostrar algunos ejemplos
            examples = Product.objects.filter(
                pk__in=products_to_update.values_list('pk', flat=True)[:5]
            )
            for product in examples:
                self.stdout.write(f"  - {product.name} ({product.sku})")
            
            if count > 5:
                self.stdout.write(f"  ... y {count - 5} productos más")
        else:
            self.stdout.write(f'[DRY-RUN] Se convertirían {count} productos a tipo simple:')
            for product in products_to_update[:5]:
                self.stdout.write(f"  - {product.name} ({product.sku}) [{product.product_type} → simple]")
            if count > 5:
                self.stdout.write(f"  ... y {count - 5} productos más")

    def show_summary(self):
        """Muestra un resumen del estado actual."""
        total_products = Product.objects.count()
        simple_products = Product.objects.filter(product_type='simple').count()
        composite_products = Product.objects.exclude(product_type='simple').count()
        total_conversions = ProductConversion.objects.count()
        
        self.stdout.write('\n=== RESUMEN DEL SISTEMA ===')
        self.stdout.write(f'Total productos: {total_products}')
        self.stdout.write(f'Productos simples: {simple_products}')
        self.stdout.write(f'Productos compuestos: {composite_products}')
        self.stdout.write(f'Conversiones configuradas: {total_conversions}')
        
        if total_conversions > 0:
            self.stdout.write('\nEjemplos de conversiones:')
            for conversion in ProductConversion.objects.all()[:3]:
                self.stdout.write(f'  - {conversion}')
            if total_conversions > 3:
                self.stdout.write(f'  ... y {total_conversions - 3} conversiones más') 