import csv
import re
import os
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from catalogs.models import Category, Product
from catalogs.validators import SKUValidator


class Command(BaseCommand):
    """
    Comando para importar el inventario completo de UNIDENTAL desde CSV.
    
    Uso: python manage.py import_inventory [archivo.csv]
    """
    help = 'Importa el inventario completo desde el archivo CSV de UNIDENTAL'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            nargs='?',
            default='UNIDENTAL - COMPRAS E INV.txt',
            help='Ruta al archivo CSV (por defecto: UNIDENTAL - COMPRAS E INV.txt)'
        )
        parser.add_argument(
            '--skip-duplicates',
            action='store_true',
            help='Saltar productos que ya existen en lugar de actualizarlos'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin realizar cambios en la base de datos'
        )

    def __init__(self):
        super().__init__()
        self.validator = SKUValidator()
        self.category_mapping = self._create_category_mapping()
        self.created_categories = {}
        self.created_products = 0
        self.updated_products = 0
        self.skipped_products = 0
        self.errors = []

    def _create_category_mapping(self):
        """
        Mapea palabras clave del inventario a categorías del sistema SKU.
        """
        return {
            # Accesorios y Complementos (ACE)
            'abreboca': ('ACE', 'DES', 'PLA'),
            'guantes': ('ACE', 'GUA', 'LAT'),
            'babero': ('ACE', 'BAB', 'DES'),
            'gorro': ('ACE', 'BAB', 'DES'),
            'contenedor': ('ACE', 'CON', 'PLA'),
            'caja': ('ACE', 'CON', 'PLA'),
            
            # Anestesia y Control de Dolor (ANE)
            'anestesia': ('ANE', 'CAR', 'SEP'),
            'lidocaina': ('ANE', 'CAR', 'SEP'),
            'articaina': ('ANE', 'CAR', 'SEP'),
            'mepivacaina': ('ANE', 'CAR', 'SEP'),
            'topico': ('ANE', 'TOP', 'GEL'),
            'aguja': ('ANE', 'AGU', 'MET'),
            
            # Materiales de Restauración (RES)
            'adhesivo': ('RES', 'ADH', 'M3M'),
            'composite': ('RES', 'COM', 'M3M'),
            'resina': ('RES', 'COM', 'KER'),
            'cemento': ('RES', 'CEM', 'GC'),
            'ionomero': ('RES', 'ION', 'GC'),
            'acrilico': ('RES', 'ACR', 'NEW'),
            
            # Materiales de Impresión (IMP)
            'alginato': ('IMP', 'ALG', 'ZHE'),
            'silicona': ('IMP', 'SIL', 'ZHE'),
            'godiva': ('IMP', 'GOD', 'KEL'),
            'cubeta': ('IMP', 'CUB', 'PLA'),
            'adhesivo impresion': ('IMP', 'ADH', 'ZHE'),
            
            # Endodoncia (END)
            'lima': ('END', 'LIM', 'GAT'),
            'hidroxido': ('END', 'HID', 'ANG'),
            'irrigacion': ('END', 'IRR', 'HIP'),
            'obturacion': ('END', 'OBT', 'ANG'),
            'gutapercha': ('END', 'GUT', 'MAQ'),
            
            # Periodoncia y Cirugía (PER)
            'cureta': ('PER', 'CUR', 'HUF'),
            'bisturi': ('PER', 'BIS', 'ACE'),
            'sutura': ('PER', 'SUT', 'VIC'),
            'hemostatico': ('PER', 'HEM', 'COL'),
            'grapa': ('PER', 'GRA', 'MET'),
            
            # Blanqueamiento (BLA)
            'aclaramiento casero': ('BLA', 'CAS', 'ULT'),
            'aclaramiento consultorio': ('BLA', 'CON', 'FGM'),
            'blanqueamiento': ('BLA', 'CAS', 'ULT'),
            'barrera gingival': ('BLA', 'BAR', 'ULT'),
            
            # Profilaxis y Prevención (PRO)
            'piedra': ('PRO', 'PIE', 'POL'),
            'pasta': ('PRO', 'PIE', 'POL'),
            'fluor': ('PRO', 'FLU', 'FGM'),
            'barniz': ('PRO', 'FLU', 'COL'),
            'cepillo': ('PRO', 'CEP', 'ORA'),
            'hilo dental': ('PRO', 'HIL', 'ORA'),
            
            # Laboratorio (LAB)
            'articulador': ('LAB', 'ART', 'BIO'),
            'yeso': ('LAB', 'YEP', 'ELI'),
            'modelo': ('LAB', 'MOD', 'YEP'),
            'fresa': ('LAB', 'FRE', 'NSK'),
            'platina': ('LAB', 'YEP', 'ELI'),
            
            # Desinfección y Esterilización (DES)
            'glutaraldehido': ('DES', 'GUT', 'CID'),
            'hipoclorito': ('DES', 'HIP', 'NAO'),
            'enzimatico': ('DES', 'ENZ', 'END'),
            'bolsa esterilizacion': ('DES', 'BOL', 'CRO'),
            'indicador biologico': ('DES', 'IND', 'M3M'),
            
            # Organización y Oficina (ORG)
            'papel': ('ORG', 'PAP', 'VAR'),
            'limpieza': ('ORG', 'LIM', 'VAR'),
            'organizador': ('ORG', 'ALM', 'VAR'),
            'bolsa': ('ORG', 'BOL', 'PLA'),
            'papeleria': ('ORG', 'PAP', 'VAR'),
            
            # Ortodoncia (ORT)
            'alambre': ('ORT', 'ALA', 'TIT'),
            'cadeneta': ('ORT', 'CAD', 'ELA'),
            'boton': ('ORT', 'BOT', 'MET'),
            'banda': ('ORT', 'BAN', 'M3M'),
            'arco': ('ORT', 'ARC', 'NIT'),
        }

    def _categorize_product(self, product_name):
        """
        Categoriza un producto basándose en su nombre.
        Retorna (categoria, subcategoria, tipo) o None si no se puede categorizar.
        """
        product_name_lower = product_name.lower()
        
        # Buscar coincidencias exactas primero en el mapping
        for keyword, (cat, subcat, tipo) in self.category_mapping.items():
            if keyword in product_name_lower:
                return cat, subcat, tipo
        
        # Reglas especiales más específicas basadas en patrones
        # ANESTESIA
        if any(word in product_name_lower for word in ['anestesia', 'anestesico', 'topica', 'roxicaina', 'garocaina']):
            if any(word in product_name_lower for word in ['carpul', 'cartucho', 'septodont']):
                return 'ANE', 'CAR', 'SEP'
            else:
                return 'ANE', 'AGU', 'MET'
        
        # ACIDOS Y ADHESIVOS
        if any(word in product_name_lower for word in ['acido', 'grabador', 'desmineralizante', 'etch']):
            if 'fluorhidrico' in product_name_lower:
                return 'PRO', 'FLU', 'FGM'
            else:
                return 'RES', 'ADH', 'GEL'
        
        if any(word in product_name_lower for word in ['adhesivo', 'bond', 'ambar']):
            return 'RES', 'ADH', 'M3M'
        
        # ACEITES Y LUBRICANTES
        if any(word in product_name_lower for word in ['aceite', 'lubricante', 'spray']):
            return 'ACE', 'DES', 'LIQ'
        
        # ALGINATOS
        if any(word in product_name_lower for word in ['alginato', 'hidrogum', 'jeltrate', 'kromalgin']):
            return 'IMP', 'ALG', 'ZHE'
        
        # SILICONAS
        if any(word in product_name_lower for word in ['silicona', 'silagum', 'president', 'panasil', 'zhermack']):
            return 'IMP', 'SIL', 'ZHE'
        
        # BLANQUEAMIENTO
        if any(word in product_name_lower for word in ['aclaramiento', 'blanqueamiento', 'whiteness', 'opalescence']):
            if 'casero' in product_name_lower:
                return 'BLA', 'CAS', 'ULT'
            else:
                return 'BLA', 'CON', 'FGM'
        
        # RESINAS
        if any(word in product_name_lower for word in ['resina', 'composite', 'restaurativo', 'brillant', 'charisma']):
            if 'acrilico' in product_name_lower:
                return 'RES', 'ACR', 'NEW'
            else:
                return 'RES', 'COM', 'KER'
        
        # ACRILICOS
        if any(word in product_name_lower for word in ['acrilico', 'termo', 'auto']):
            return 'RES', 'ACR', 'NEW'
        
        # CEMENTOS
        if any(word in product_name_lower for word in ['cemento', 'grossman', 'temporal', 'choice']):
            return 'RES', 'CEM', 'GC'
        
        # IONÓMEROS
        if any(word in product_name_lower for word in ['ionomero', 'vitrebon', 'riva']):
            return 'RES', 'ION', 'GC'
        
        # ENDODONCIA
        if any(word in product_name_lower for word in ['lima', 'flexofile', 'k-file', 'hedstroem']):
            return 'END', 'LIM', 'GAT'
        
        if any(word in product_name_lower for word in ['gutapercha', 'cono', 'obturación']):
            return 'END', 'GUT', 'MAQ'
        
        if any(word in product_name_lower for word in ['hidroxido', 'calcio', 'hidcal', 'dycal']):
            return 'END', 'HID', 'ANG'
        
        # CUBETAS
        if any(word in product_name_lower for word in ['cubeta', 'impresion']):
            return 'IMP', 'CUB', 'PLA'
        
        # FRESAS
        if any(word in product_name_lower for word in ['fresa', 'carburo', 'diamante', 'jota']):
            return 'LAB', 'FRE', 'NSK'
        
        # GUANTES
        if any(word in product_name_lower for word in ['guante', 'latex', 'nitrilo', 'esteril']):
            return 'ACE', 'GUA', 'LAT'
        
        # BABEROS Y GORROS
        if any(word in product_name_lower for word in ['babero', 'gorro', 'tapaboca', 'desechable']):
            return 'ACE', 'BAB', 'DES'
        
        # SUTURA
        if any(word in product_name_lower for word in ['sutura', 'hilo', 'seda', 'vicryl', 'nylon']):
            return 'PER', 'SUT', 'VIC'
        
        # GRAPAS
        if any(word in product_name_lower for word in ['grapa', 'clamp']):
            return 'PER', 'GRA', 'MET'
        
        # CURETAS
        if any(word in product_name_lower for word in ['cureta', 'gracey', 'mc call']):
            return 'PER', 'CUR', 'HUF'
        
        # YESO
        if any(word in product_name_lower for word in ['yeso', 'whipmix', 'modelo']):
            return 'LAB', 'YEP', 'ELI'
        
        # FLUOR
        if any(word in product_name_lower for word in ['fluor', 'fluoruro', 'barniz', 'duraphat']):
            return 'PRO', 'FLU', 'FGM'
        
        # PASTA PROFILÁCTICA
        if any(word in product_name_lower for word in ['pasta', 'profilactica', 'pulir', 'diamantada']):
            return 'PRO', 'PIE', 'POL'
        
        # CEPILLOS
        if any(word in product_name_lower for word in ['cepillo', 'profilaxis']):
            return 'PRO', 'CEP', 'ORA'
        
        # DESINFECCIÓN
        if any(word in product_name_lower for word in ['glutaraldehido', 'glutacides', 'bactixide']):
            return 'DES', 'GUT', 'CID'
        
        if any(word in product_name_lower for word in ['hipoclorito', 'cloro']):
            return 'DES', 'HIP', 'NAO'
        
        if any(word in product_name_lower for word in ['jabon', 'enzimatico']):
            return 'DES', 'ENZ', 'END'
        
        # ALCOHOL - mapear a desinfección enzimática 
        if any(word in product_name_lower for word in ['alcohol', 'anticeptico']):
            return 'DES', 'ENZ', 'END'
        
        # ORTODONCIA
        if any(word in product_name_lower for word in ['alambre', 'arco', 'ortodoncia']):
            return 'ORT', 'ALA', 'TIT'
        
        # BRACKETS - mapear a botones metálicos
        if any(word in product_name_lower for word in ['bracket', 'boton']):
            return 'ORT', 'BOT', 'MET'
        
        if any(word in product_name_lower for word in ['banda', 'matriz']):
            return 'ORT', 'BAN', 'M3M'
        
        # ORGANIZACIÓN Y PAPELERÍA
        if any(word in product_name_lower for word in ['papel', 'articular', 'carpeta', 'lapiz']):
            return 'ORG', 'PAP', 'VAR'
        
        if any(word in product_name_lower for word in ['bolsa', 'esterilizar', 'transparente']):
            return 'ORG', 'BOL', 'PLA'
        
        if any(word in product_name_lower for word in ['caja', 'organizador', 'bandeja']):
            return 'ACE', 'CON', 'PLA'
        
        # Categoría por defecto: Accesorios y Complementos
        return 'ACE', 'CON', 'PLA'

    def _clean_price(self, price_str):
        """
        Limpia y convierte una cadena de precio a Decimal.
        """
        if not price_str or price_str.strip() == '':
            return None
        
        # Remover caracteres no numéricos excepto puntos, comas y signos de dólar
        cleaned = re.sub(r'[^\d.,\$]', '', str(price_str))
        
        # Remover signos de dólar
        cleaned = cleaned.replace('$', '')
        
        # Convertir comas por puntos para decimales
        if ',' in cleaned and '.' in cleaned:
            # Si tiene ambos, asumir que la coma es separador de miles
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Si solo tiene coma, puede ser decimal (europeo) o miles
            parts = cleaned.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Probablemente decimal
                cleaned = cleaned.replace(',', '.')
            else:
                # Probablemente separador de miles
                cleaned = cleaned.replace(',', '')
        
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None

    def _get_or_create_category(self, name):
        """
        Obtiene o crea una categoría por nombre.
        """
        if name in self.created_categories:
            return self.created_categories[name]
        
        category, created = Category.objects.get_or_create(
            name=name,
            defaults={'description': f'Categoría generada automáticamente para {name}'}
        )
        
        self.created_categories[name] = category
        
        if created:
            self.stdout.write(f"  ✓ Categoría creada: {name}")
        
        return category

    def _generate_sku(self, categoria, subcategoria, tipo):
        """
        Genera un SKU único para la combinación dada.
        """
        existing_skus = list(Product.objects.values_list('sku', flat=True))
        return self.validator.generate_next_sku(categoria, subcategoria, tipo, existing_skus)

    def _parse_csv_row(self, row):
        """
        Parsea una fila del CSV y extrae los datos relevantes.
        """
        if len(row) < 12:
            return None
        
        product_name = row[0].strip()
        if not product_name or product_name.startswith('NO USAR') or product_name == 'referencias':
            return None
        
        referencias = row[1].strip() if len(row) > 1 else ''
        proveedor = row[6].strip() if len(row) > 6 else ''
        inventario_sur = row[7].strip() if len(row) > 7 else ''
        inventario_norte = row[8].strip() if len(row) > 8 else ''
        precio_compra_str = row[10].strip() if len(row) > 10 else ''
        precio_venta_str = row[11].strip() if len(row) > 11 else ''
        
        # Limpiar precios
        precio_compra = self._clean_price(precio_compra_str)
        precio_venta = self._clean_price(precio_venta_str)
        
        # Determinar unidad basándose en el nombre del producto
        unit = 'unidad'  # por defecto
        name_lower = product_name.lower()
        if any(word in name_lower for word in ['ml', 'cc', 'litro', 'galon']):
            unit = 'ml'
        elif any(word in name_lower for word in ['kg', 'gr', 'gramos']):
            unit = 'kg'
        elif any(word in name_lower for word in ['caja', 'paquete', 'sobre']):
            unit = 'caja'
        elif any(word in name_lower for word in ['metro', 'cm']):
            unit = 'metro'
        
        # Crear descripción combinando referencias y proveedor
        description_parts = []
        if referencias:
            description_parts.append(f"Referencias: {referencias}")
        if proveedor:
            description_parts.append(f"Proveedor: {proveedor}")
        if inventario_sur or inventario_norte:
            description_parts.append(f"Stock Sur: {inventario_sur}, Norte: {inventario_norte}")
        
        description = '. '.join(description_parts) if description_parts else product_name
        
        return {
            'name': product_name,
            'description': description,
            'unit': unit,
            'precio_compra': precio_compra,
            'precio_venta': precio_venta,
            'proveedor': proveedor
        }

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        skip_duplicates = options['skip_duplicates']
        dry_run = options['dry_run']
        
        # Verificar que el archivo existe
        if not os.path.exists(csv_file):
            raise CommandError(f'El archivo {csv_file} no existe.')
        
        self.stdout.write(f"Iniciando importación desde: {csv_file}")
        self.stdout.write(f"Modo: {'DRY RUN (sin cambios)' if dry_run else 'IMPORTACIÓN REAL'}")
        self.stdout.write("-" * 60)
        
        # Crear categoría por defecto
        if not dry_run:
            default_category = self._get_or_create_category("Productos Generales")
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                # Detectar el delimitador automáticamente
                sample = file.read(1024)
                file.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.reader(file, delimiter=delimiter)
                
                with transaction.atomic():
                    for row_num, row in enumerate(reader, 1):
                        if row_num == 1:  # Saltar header
                            continue
                        
                        try:
                            data = self._parse_csv_row(row)
                            if not data:
                                continue
                            
                            # Categorizar producto
                            cat_info = self._categorize_product(data['name'])
                            if cat_info:
                                categoria, subcategoria, tipo = cat_info
                                sku = self._generate_sku(categoria, subcategoria, tipo)
                                
                                # Crear nombre de categoría legible
                                categoria_name = self.validator.CATEGORIAS.get(categoria, categoria)
                                category = self._get_or_create_category(categoria_name) if not dry_run else None
                            else:
                                self.errors.append(f"Línea {row_num}: No se pudo categorizar '{data['name']}'")
                                continue
                            
                            if dry_run:
                                self.stdout.write(
                                    f"  {row_num:4d}: {data['name'][:50]:<50} -> {sku} ({categoria_name})"
                                )
                                self.created_products += 1
                                continue
                            
                            # Verificar si el producto ya existe por nombre
                            existing_product = Product.objects.filter(name=data['name']).first()
                            
                            if existing_product:
                                if skip_duplicates:
                                    self.skipped_products += 1
                                    continue
                                else:
                                    # Actualizar producto existente
                                    existing_product.description = data['description']
                                    existing_product.unit = data['unit']
                                    existing_product.category = category
                                    existing_product.save()
                                    self.updated_products += 1
                                    
                                    self.stdout.write(
                                        f"  ↻ Actualizado: {data['name'][:50]:<50} -> {existing_product.sku}"
                                    )
                            else:
                                # Crear nuevo producto
                                product = Product.objects.create(
                                    sku=sku,
                                    name=data['name'],
                                    description=data['description'],
                                    unit=data['unit'],
                                    category=category
                                )
                                self.created_products += 1
                                
                                self.stdout.write(
                                    f"  ✓ Creado: {data['name'][:50]:<50} -> {sku}"
                                )
                        
                        except Exception as e:
                            self.errors.append(f"Línea {row_num}: Error procesando '{row[0] if row else 'fila vacía'}': {str(e)}")
                            continue
                    
                    if dry_run:
                        # En dry run, hacer rollback explícito
                        transaction.set_rollback(True)
        
        except Exception as e:
            raise CommandError(f'Error leyendo el archivo CSV: {str(e)}')
        
        # Mostrar resumen
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("RESUMEN DE IMPORTACIÓN")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Productos creados: {self.created_products}")
        self.stdout.write(f"Productos actualizados: {self.updated_products}")
        self.stdout.write(f"Productos omitidos: {self.skipped_products}")
        self.stdout.write(f"Categorías creadas: {len(self.created_categories)}")
        self.stdout.write(f"Errores encontrados: {len(self.errors)}")
        
        if self.errors:
            self.stdout.write("\nERRORES:")
            for error in self.errors[:10]:  # Mostrar solo los primeros 10 errores
                self.stdout.write(f"  - {error}")
            if len(self.errors) > 10:
                self.stdout.write(f"  ... y {len(self.errors) - 10} errores más")
        
        if dry_run:
            self.stdout.write("\n⚠️  DRY RUN: No se realizaron cambios en la base de datos")
        else:
            self.stdout.write("\n🎉 Importación completada exitosamente!") 