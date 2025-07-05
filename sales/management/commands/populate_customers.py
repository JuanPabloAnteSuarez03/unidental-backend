import csv
import re
import os
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.encoding import force_str
from sales.models import Customer


class Command(BaseCommand):
    help = 'Importa clientes desde el archivo CSV de UNIDENTAL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='UNIDENTAL (1) - BASE DATOS  .csv',
            help='Ruta del archivo CSV con los datos de clientes'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Elimina todos los clientes existentes antes de importar'
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
            self._clear_customers()

        # Procesar archivo CSV
        try:
            with transaction.atomic():
                customers_data = self._read_csv_file(csv_file)
                if dry_run:
                    self._simulate_import(customers_data)
                    # Hacer rollback en simulación
                    raise Exception("Simulación completada")
                else:
                    self._import_customers(customers_data)
        except Exception as e:
            if "Simulación completada" in str(e):
                self.stdout.write("✅ Simulación completada exitosamente")
            else:
                raise e

    def _clear_customers(self):
        """Elimina todos los clientes existentes."""
        count = Customer.objects.count()
        if count > 0:
            self.stdout.write(f"🗑️  Eliminando {count} clientes existentes...")
            Customer.objects.all().delete()
            self.stdout.write("✅ Clientes eliminados")

    def _read_csv_file(self, csv_file):
        """Lee y procesa el archivo CSV."""
        customers_data = []
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            # Detectar si la primera línea es encabezado
            first_line = file.readline().strip()
            file.seek(0)
            
            # El CSV no tiene encabezados, empezar desde la primera línea
            reader = csv.reader(file)
            
            for row_num, row in enumerate(reader, 1):
                if len(row) < 4:  # Mínimo: nombre, teléfono, cumpleaños, dirección
                    continue
                
                try:
                    customer_data = self._parse_customer_row(row, row_num)
                    if customer_data:
                        customers_data.append(customer_data)
                except Exception as e:
                    self.stdout.write(f"⚠️  Error en fila {row_num}: {e}")
                    continue
        
        self.stdout.write(f"📊 Procesadas {len(customers_data)} filas válidas")
        return customers_data

    def _parse_customer_row(self, row, row_num):
        """Parsea una fila del CSV y extrae los datos del cliente."""
        if len(row) < 4:
            return None
        
        # Mapeo de columnas según el CSV
        # 0: Nombre, 1: Teléfono, 2: Cumpleaños, 3: Dirección, 4: Contacto emergencia
        name = self._clean_text(row[0])
        phone = self._clean_phone(row[1])
        birthday_str = self._clean_text(row[2])
        address = self._clean_text(row[3])
        emergency_contact = self._clean_text(row[4]) if len(row) > 4 else None
        
        if not name:
            return None
        
        # Procesar fecha de cumpleaños
        birthday = self._parse_birthday(birthday_str)
        
        return {
            'name': name,
            'phone': phone,
            'birthday': birthday,
            'address': address,
            'emergency_contact': emergency_contact,
            'row_num': row_num
        }

    def _clean_text(self, text):
        """Limpia y normaliza texto."""
        if not text or text.strip() == '':
            return None
        
        # Limpiar espacios extra y caracteres especiales
        text = re.sub(r'\s+', ' ', text.strip())
        return text if text else None

    def _clean_phone(self, phone):
        """Limpia y normaliza números de teléfono."""
        if not phone or phone.strip() == '':
            return None
        
        # Limpiar espacios y caracteres especiales, pero mantener números y algunos símbolos
        phone = re.sub(r'[^\d\s\-\+\(\)\/]', '', phone.strip())
        
        # Limitar longitud para evitar datos demasiado largos
        if len(phone) > 50:
            phone = phone[:50]
        
        return phone if phone else None

    def _parse_birthday(self, birthday_str):
        """Parsea fecha de cumpleaños desde string."""
        if not birthday_str or birthday_str.strip() == '':
            return None
        
        birthday_str = birthday_str.strip().lower()
        
        # Mapeo de meses en español
        month_map = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        
        try:
            # Buscar patrones como "AGOSTO 8", "FEBRERO - 18", etc.
            for month_name, month_num in month_map.items():
                if month_name in birthday_str:
                    # Extraer día
                    day_match = re.search(r'(\d{1,2})', birthday_str)
                    if day_match:
                        day = int(day_match.group(1))
                        if 1 <= day <= 31:
                            # Usar año actual o uno genérico
                            year = 2000  # Año genérico para cumpleaños
                            return date(year, month_num, day)
            
            # Intentar otros formatos de fecha
            # DD/MM/YYYY, DD-MM-YYYY, etc.
            date_patterns = [
                r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})',
                r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2})',
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, birthday_str)
                if match:
                    day, month, year = match.groups()
                    day, month, year = int(day), int(month), int(year)
                    
                    # Ajustar año si es de 2 dígitos
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                    
                    if 1 <= day <= 31 and 1 <= month <= 12:
                        return date(year, month, day)
            
        except (ValueError, TypeError):
            pass
        
        return None

    def _simulate_import(self, customers_data):
        """Simula la importación sin guardar en la base de datos."""
        self.stdout.write("🔍 Simulando importación...")
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for customer_data in customers_data:
            try:
                # Verificar si el cliente ya existe
                existing = Customer.objects.filter(name=customer_data['name']).first()
                
                if existing:
                    updated_count += 1
                    self.stdout.write(f"  📝 Actualizaría: {customer_data['name']}")
                else:
                    created_count += 1
                    self.stdout.write(f"  ✅ Crearía: {customer_data['name']}")
                
            except Exception as e:
                error_count += 1
                self.stdout.write(f"  ❌ Error con {customer_data['name']}: {e}")
        
        self.stdout.write(f"\n📊 Resumen de simulación:")
        self.stdout.write(f"  • Clientes a crear: {created_count}")
        self.stdout.write(f"  • Clientes a actualizar: {updated_count}")
        self.stdout.write(f"  • Errores: {error_count}")

    def _import_customers(self, customers_data):
        """Importa los clientes a la base de datos."""
        self.stdout.write("💾 Importando clientes...")
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for customer_data in customers_data:
            try:
                row_num = customer_data.pop('row_num')
                
                # Crear o actualizar cliente
                customer, created = Customer.objects.update_or_create(
                    name=customer_data['name'],
                    defaults=customer_data
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f"  ✅ Creado: {customer.name}")
                else:
                    updated_count += 1
                    self.stdout.write(f"  📝 Actualizado: {customer.name}")
                
            except Exception as e:
                error_count += 1
                self.stdout.write(f"  ❌ Error con {customer_data.get('name', 'N/A')}: {e}")
        
        self.stdout.write(f"\n📊 Resumen de importación:")
        self.stdout.write(f"  • Clientes creados: {created_count}")
        self.stdout.write(f"  • Clientes actualizados: {updated_count}")
        self.stdout.write(f"  • Errores: {error_count}")
        self.stdout.write(f"  • Total procesados: {created_count + updated_count}") 