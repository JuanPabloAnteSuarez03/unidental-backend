import csv
import re
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from suppliers.models import Supplier


class Command(BaseCommand):
    help = 'Importa proveedores desde el archivo CSV de UNIDENTAL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='UNIDENTAL (1) - PROVEEDORES 2024.csv',
            help='Ruta del archivo CSV con los datos de proveedores'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Elimina todos los proveedores existentes antes de importar'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecuta una simulación sin guardar cambios en la base de datos'
        )

    def handle(self, *args, **options):
        csv_file = options['file']
        clean_existing = options['clean']
        dry_run = options['dry_run']

        # Configurar stdout para UTF-8 en Windows
        import sys
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')

        if dry_run:
            self.stdout.write("🔍 MODO SIMULACIÓN - No se guardarán cambios")

        # Verificar que el archivo existe
        if not os.path.exists(csv_file):
            raise CommandError(f'El archivo {csv_file} no existe.')

        self.stdout.write(f"📁 Procesando archivo: {csv_file}")

        # Limpiar base de datos si se solicita
        if clean_existing and not dry_run:
            self._clear_suppliers()

        # Procesar archivo CSV
        try:
            with transaction.atomic():
                suppliers_data = self._read_csv_file(csv_file)
                if dry_run:
                    self._simulate_import(suppliers_data)
                    # Hacer rollback en simulación
                    raise Exception("Simulación completada")
                else:
                    self._import_suppliers(suppliers_data)
        except Exception as e:
            if "Simulación completada" in str(e):
                self.stdout.write("✅ Simulación completada exitosamente")
            else:
                raise e

    def _clear_suppliers(self):
        """Elimina todos los proveedores existentes."""
        count = Supplier.objects.count()
        if count > 0:
            self.stdout.write(f"🗑️  Eliminando {count} proveedores existentes...")
            Supplier.objects.all().delete()
            self.stdout.write("✅ Proveedores eliminados")

    def _read_csv_file(self, csv_file):
        """Lee y procesa el archivo CSV."""
        suppliers_data = []
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            
            for row_num, row in enumerate(reader, 1):
                if len(row) < 1:  # Mínimo: nombre del proveedor
                    continue
                
                # Saltar filas vacías o que parecen encabezados
                if not row[0] or row[0].strip() == '' or row[0].strip().upper() in ['A', 'PROVEEDOR', 'NOMBRE']:
                    continue
                
                try:
                    supplier_data = self._parse_supplier_row(row, row_num)
                    if supplier_data:
                        suppliers_data.append(supplier_data)
                except Exception as e:
                    self.stdout.write(f"⚠️  Error en fila {row_num}: {e}")
                    continue
        
        self.stdout.write(f"📊 Procesadas {len(suppliers_data)} filas válidas")
        return suppliers_data

    def _parse_supplier_row(self, row, row_num):
        """Parsea una fila del CSV y extrae los datos del proveedor."""
        if len(row) < 1:
            return None
        
        # Mapeo de columnas según el CSV
        # 0: Nombre del proveedor, 1: Contacto/representante
        name = self._clean_text(row[0])
        contact_name = self._clean_text(row[1]) if len(row) > 1 else None
        
        if not name:
            return None
        
        return {
            'name': name,
            'contact_name': contact_name,
            'row_num': row_num
        }

    def _clean_text(self, text):
        """Limpia y normaliza texto."""
        if not text or text.strip() == '':
            return None
        
        # Limpiar espacios extra
        text = re.sub(r'\s+', ' ', text.strip())
        return text if text else None

    def _simulate_import(self, suppliers_data):
        """Simula la importación sin guardar en la base de datos."""
        self.stdout.write("🔍 Simulando importación...")
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for supplier_data in suppliers_data:
            try:
                # Verificar si el proveedor ya existe
                existing = Supplier.objects.filter(name=supplier_data['name']).first()
                
                if existing:
                    updated_count += 1
                    self.stdout.write(f"  📝 Actualizaría: {supplier_data['name']}")
                else:
                    created_count += 1
                    self.stdout.write(f"  ✅ Crearía: {supplier_data['name']}")
                
            except Exception as e:
                error_count += 1
                self.stdout.write(f"  ❌ Error con {supplier_data['name']}: {e}")
        
        self.stdout.write(f"\n📊 Resumen de simulación:")
        self.stdout.write(f"  • Proveedores a crear: {created_count}")
        self.stdout.write(f"  • Proveedores a actualizar: {updated_count}")
        self.stdout.write(f"  • Errores: {error_count}")

    def _import_suppliers(self, suppliers_data):
        """Importa los proveedores a la base de datos."""
        self.stdout.write("💾 Importando proveedores...")
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for supplier_data in suppliers_data:
            try:
                row_num = supplier_data.pop('row_num')
                
                # Crear o actualizar proveedor
                supplier, created = Supplier.objects.update_or_create(
                    name=supplier_data['name'],
                    defaults=supplier_data
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f"  ✅ Creado: {supplier.name}")
                else:
                    updated_count += 1
                    self.stdout.write(f"  📝 Actualizado: {supplier.name}")
                
            except Exception as e:
                error_count += 1
                self.stdout.write(f"  ❌ Error con {supplier_data.get('name', 'N/A')}: {e}")
        
        self.stdout.write(f"\n📊 Resumen de importación:")
        self.stdout.write(f"  • Proveedores creados: {created_count}")
        self.stdout.write(f"  • Proveedores actualizados: {updated_count}")
        self.stdout.write(f"  • Errores: {error_count}")
        self.stdout.write(f"  • Total procesados: {created_count + updated_count}") 