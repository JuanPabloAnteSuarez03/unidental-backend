import csv
import re
import os
from decimal import Decimal, InvalidOperation
from datetime import date, timedelta, datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_delete

# Import all models
from catalogs.models import Category, Product, ProductBatch
from catalogs.validators import SKUValidator
from suppliers.models import Supplier, PurchaseOption
from inventory.models import Location, InventoryStock, InventoryMovement
from sales.models import Customer, Sale, SaleItem, ReturnItem, Return, update_inventory_on_return_item_delete, update_return_total
from credits.models import CreditAccount, CreditPayment
from purchases.models import PurchaseOrder, PurchaseOrderItem


class Command(BaseCommand):
    """
    Comando para poblar TODA la base de datos de UNIDENTAL desde el CSV.
    
    Uso: python manage.py populate_database [archivo.csv]
    """
    help = 'Pobla toda la base de datos desde el archivo CSV de UNIDENTAL de forma optimizada'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            nargs='?',
            default='UNIDENTAL - COMPRAS E INV (1).csv',
            help='Ruta al archivo CSV (por defecto: UNIDENTAL - COMPRAS E INV (1).csv)'
        )
        parser.add_argument(
            '--clear-data',
            action='store_true',
            help='Limpiar toda la base de datos antes de importar'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular la ejecución sin aplicar cambios en la base de datos'
        )
        parser.add_argument(
            '--orders-only',
            action='store_true',
            help='Crear únicamente órdenes de compra e ítems basados en las opciones de compra existentes'
        )
        # Se elimina la opción de datos de demostración para este script
        # por la complejidad que añade al procesamiento en lotes.

    def __init__(self):
        super().__init__()
        # Asegurar que stdout use UTF-8 para evitar UnicodeEncodeError en Windows
        import sys
        try:
            if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            # Si falla, ignorar y continuar. Los caracteres no representables se reemplazarán.
            pass
        self.validator = SKUValidator()
        self.category_mapping = self._create_category_mapping()
        
        # Contadores para estadísticas
        self.stats = {
            'products_processed': 0,
            'products_created': 0,
            'batches_created': 0,
            'suppliers_created': 0,
            'purchase_options_created': 0,
            'purchase_orders_created': 0,
            'purchase_order_items_created': 0,
            'inventory_stock_created': 0,
            'inventory_movements_created': 0,
        }
        self.errors = []
        self.supplier_cache = {}
        self.category_cache = {}
        self.location_cache = {}

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
            'impresion': ('IMP', 'ALG', 'ZHE'),
            
            # Endodoncia (END)
            'lima': ('END', 'LIM', 'GAT'),
            'hidroxido': ('END', 'HID', 'ANG'),
            'irrigacion': ('END', 'IRR', 'HIP'),
            'obturacion': ('END', 'OBT', 'ANG'),
            'gutapercha': ('END', 'GUT', 'MAQ'),
            'endodoncia': ('END', 'LIM', 'GAT'),
            
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
            'aclaramiento': ('BLA', 'CON', 'FGM'),
            
            # Profilaxis y Prevención (PRO)
            'piedra': ('PRO', 'PIE', 'POL'),
            'pasta': ('PRO', 'PIE', 'POL'),
            'fluor': ('PRO', 'FLU', 'FGM'),
            'barniz': ('PRO', 'FLU', 'COL'),
            'cepillo': ('PRO', 'CEP', 'ORA'),
            'hilo dental': ('PRO', 'HIL', 'ORA'),
            'profilaxis': ('PRO', 'PIE', 'POL'),
            
            # Laboratorio (LAB)
            'articulador': ('LAB', 'ART', 'BIO'),
            'yeso': ('LAB', 'YEP', 'ELI'),
            'modelo': ('LAB', 'MOD', 'YEP'),
            'fresa': ('LAB', 'FRE', 'NSK'),
            'platina': ('LAB', 'YEP', 'ELI'),
            'laboratorio': ('LAB', 'ART', 'BIO'),
            
            # Desinfección y Esterilización (DES)
            'glutaraldehido': ('DES', 'GUT', 'CID'),
            'hipoclorito': ('DES', 'HIP', 'NAO'),
            'enzimatico': ('DES', 'ENZ', 'END'),
            'bolsa esterilizacion': ('DES', 'BOL', 'CRO'),
            'indicador biologico': ('DES', 'IND', 'M3M'),
            'desinfeccion': ('DES', 'GUT', 'CID'),
            'alcohol': ('DES', 'HIP', 'VAR'),
            
            # Organización y Oficina (ORG)
            'papel': ('ORG', 'PAP', 'VAR'),
            'limpieza': ('ORG', 'LIM', 'VAR'),
            'organizador': ('ORG', 'ALM', 'VAR'),
            'bolsa': ('ORG', 'BOL', 'PLA'),
            'papeleria': ('ORG', 'PAP', 'VAR'),
            'aceite': ('ORG', 'LIM', 'VAR'),
            
            # Ortodoncia (ORT)
            'alambre': ('ORT', 'ALA', 'TIT'),
            'cadeneta': ('ORT', 'CAD', 'ELA'),
            'boton': ('ORT', 'BOT', 'MET'),
            'banda': ('ORT', 'BAN', 'M3M'),
            'arco': ('ORT', 'ARC', 'NIT'),
            'ortodoncia': ('ORT', 'ALA', 'TIT'),
        }

    def _categorize_product(self, product_name):
        """
        Categoriza un producto basándose en su nombre.
        """
        name_lower = product_name.lower()
        
        # Buscar coincidencias en el mapeo
        for keyword, (categoria, subcategoria, tipo) in self.category_mapping.items():
            if keyword in name_lower:
                return categoria, subcategoria, tipo
        
        # Categorización por defecto basada en palabras clave generales
        if any(word in name_lower for word in ['dental', 'diente', 'oral']):
            return 'PRO', 'PIE', 'GEN'
        elif any(word in name_lower for word in ['medico', 'clinico', 'hospital']):
            return 'ACE', 'INS', 'MED'
        else:
            return 'ORG', 'VAR', 'GEN'

    def _parse_date(self, date_str):
        """
        Convierte una cadena de fecha a un objeto date.
        Intenta varios formatos comunes.
        """
        if not date_str:
            return None
        
        # Formatos con día, mes y año
        formats_with_day = [
            '%d/%m/%Y',  # 24/05/2025
            '%d-%m-%Y',  # 24-05-2025
            '%Y-%m-%d',  # 2025-05-24
            '%d/%m/%y',  # 24/05/25
        ]
        
        for fmt in formats_with_day:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        # Formatos solo con mes y año (asumir último día del mes)
        formats_month_year = [
            '%m-%Y',     # 03-2025
            '%m/%Y',     # 03/2025
        ]
        
        for fmt in formats_month_year:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Ir al primer día del siguiente mes y restar un día
                if dt.month == 12:
                    next_month_first_day = date(dt.year + 1, 1, 1)
                else:
                    next_month_first_day = date(dt.year, dt.month + 1, 1)
                return next_month_first_day - timedelta(days=1)
            except ValueError:
                continue
        
        self.errors.append(f"Formato de fecha no reconocido para '{date_str}'")
        return None

    def _clean_price(self, price_str):
        """Limpia y convierte un precio a Decimal manejando puntos y comas como separadores."""
        if not price_str:
            return None

        txt = str(price_str).strip()
        if txt == '':
            return None

        # Buscar patrones de precio usando regex - tomar el primero
        price_patterns = [
            r'\$?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',  # Precio con separadores de miles
            r'\$?(\d+(?:[.,]\d{2})?)',  # Precio simple con decimales opcionales
            r'\$?(\d+)'  # Solo números
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, txt)
            if matches:
                # Tomar solo el primer precio encontrado
                price_match = matches[0]
                
                # Limpiar el precio encontrado
                clean_txt = price_match.strip()
                
                # Manejar separadores
                if '.' in clean_txt and ',' in clean_txt:
                    clean_txt = clean_txt.replace('.', '')
                    clean_txt = clean_txt.replace(',', '.')
                elif ',' in clean_txt and '.' not in clean_txt:
                    parts = clean_txt.split(',')
                    if len(parts[-1]) == 2:
                        clean_txt = clean_txt.replace(',', '.')
                    else:
                        clean_txt = clean_txt.replace(',', '')
                elif '.' in clean_txt and ',' not in clean_txt:
                    parts = clean_txt.split('.')
                    if len(parts[-1]) == 3 and len(parts) > 1:
                        clean_txt = clean_txt.replace('.', '')

                try:
                    price = Decimal(clean_txt)
                    # Validar que el precio no sea demasiado grande
                    if price >= Decimal('10000000000'):  # 10^10 = límite máximo
                        self.errors.append(f"Precio '{price_str}' ({price}) es demasiado grande y fue ignorado")
                        return None
                    return price
                except (InvalidOperation, ValueError):
                    continue
        
        # Si no se encontró ningún patrón válido
        return None

    def _clean_stock_quantity(self, stock_str, row_num_for_error):
        """
        Limpia y convierte una cadena de stock a entero, con validación de tamaño.
        """
        if not stock_str or stock_str.strip() == '':
            return 0
        
        cleaned = re.sub(r'[^\d]', '', str(stock_str))
        if not cleaned:
            return 0

        # Evitar 'integer out of range' en PostgreSQL (límite de 2,147,483,647)
        # Un número de 10 dígitos o más es sospechoso y probablemente no es una cantidad de stock.
        if len(cleaned) > 9:
            self.errors.append(
                f"Línea {row_num_for_error}: Cantidad de stock '{stock_str}' ({cleaned}) "
                f"parece ser un número inválido o demasiado grande y fue ignorada (establecida a 0)."
            )
            return 0
        
        try:
            return int(cleaned)
        except ValueError:
            # Esto no debería ocurrir gracias al regex, pero es una salvaguarda.
            self.errors.append(
                f"Línea {row_num_for_error}: No se pudo convertir la cantidad de stock '{stock_str}' a un número."
            )
            return 0

    def _extract_supplier_name(self, supplier_str):
        """
        Extrae y normaliza el nombre del proveedor del string del CSV.
        Ahora busca coincidencias con proveedores existentes primero.
        """
        if not supplier_str or supplier_str.strip() in ['', 'N/A', 'NO APLICA']:
            return None

        supplier_str = supplier_str.strip().upper()
        
        # Palabras a excluir del procesamiento
        exclude_words = {'Y', 'LA', 'EL', 'DE', 'DEL', 'LAS', 'LOS', 'CON', 'PARA', 'POR', 'EN'}
        
        # Primero, buscar coincidencia exacta con proveedores existentes
        for existing_supplier in self.supplier_cache.values():
            if existing_supplier.name.upper() == supplier_str:
                return existing_supplier.name
        
        # Buscar coincidencias parciales con proveedores existentes
        supplier_match = self._find_best_supplier_match(supplier_str)
        if supplier_match:
            return supplier_match
        
        # Si no hay coincidencia, extraer el primer nombre significativo como antes
        supplier_parts = supplier_str.split()
        main_supplier = None
        
        for part in supplier_parts:
            if len(part) > 2 and part not in exclude_words:
                main_supplier = part
                break
        
        return main_supplier if main_supplier else supplier_str[:20].upper()

    def _find_best_supplier_match(self, supplier_str):
        """
        Encuentra la mejor coincidencia entre proveedores existentes usando diferentes estrategias.
        """
        supplier_str_clean = supplier_str.upper()
        
        # Lista de proveedores existentes para comparar
        existing_suppliers = list(self.supplier_cache.keys())
        
        # Estrategia 1: Coincidencia por contenido (el proveedor existente está contenido en el string)
        for existing in existing_suppliers:
            if existing.upper() in supplier_str_clean:
                return existing
        
        # Estrategia 2: Coincidencia inversa (el string está contenido en el proveedor existente)
        for existing in existing_suppliers:
            if supplier_str_clean in existing.upper():
                return existing
        
        # Estrategia 3: Coincidencia por palabras clave
        supplier_words = set(supplier_str_clean.split())
        best_match = None
        best_score = 0
        
        for existing in existing_suppliers:
            existing_words = set(existing.upper().split())
            common_words = supplier_words.intersection(existing_words)
            
            # Calcular puntuación de coincidencia
            if common_words:
                score = len(common_words) / len(existing_words.union(supplier_words))
                if score > best_score and score > 0.3:  # Umbral mínimo del 30%
                    best_score = score
                    best_match = existing
        
        # Estrategia 4: Mapeo manual para casos específicos conocidos
        manual_mappings = {
            'CENTRO': 'CENTRO 40mil',  # Si aparece solo "CENTRO", usar "CENTRO 40mil"
            'DENTAL': 'DENTAL MARKET',  # Si aparece solo "DENTAL", usar "DENTAL MARKET"
            'CRISTALERIA': 'CENTRO CRISTALERIA LA 13',
            'DROGERIA': 'DROGUERIA SAN JORGE',
            'DROGUERIA': 'DROGUERIA SAN JORGE',
        }
        
        for key, mapped_supplier in manual_mappings.items():
            if key in supplier_str_clean and mapped_supplier in self.supplier_cache:
                return mapped_supplier
        
        return best_match

    def _clear_database(self):
        """
        Limpia toda la base de datos (excepto usuarios admin).
        """
        self.stdout.write("🗑️  Limpiando base de datos...")
        with transaction.atomic():
            # Desconectar señales que actualizan inventario y totales
            post_delete.disconnect(update_inventory_on_return_item_delete, sender=ReturnItem)
            post_delete.disconnect(update_return_total, sender=ReturnItem)
            try:
                # Eliminar devoluciones primero
                ReturnItem.objects.all().delete()
                Return.objects.all().delete()

                # Ahora se pueden eliminar los items y ventas sin restricciones
                SaleItem.objects.all().delete()
                Sale.objects.all().delete()
                Customer.objects.all().delete()
                InventoryMovement.objects.all().delete()
                InventoryStock.objects.all().delete()
                from purchases.models import PurchaseOrderItem, PurchaseOrder
                PurchaseOrderItem.objects.all().delete()
                PurchaseOrder.objects.all().delete()
                PurchaseOption.objects.all().delete()
                ProductBatch.objects.all().delete()
                Product.objects.all().delete()
                Category.objects.all().delete()
                Supplier.objects.all().delete()
                Location.objects.all().delete()
                CreditPayment.objects.all().delete()
                CreditAccount.objects.all().delete()
            finally:
                # Reconectar señales
                post_delete.connect(update_inventory_on_return_item_delete, sender=ReturnItem)
                post_delete.connect(update_return_total, sender=ReturnItem)
        self.stdout.write("✅ Base de datos limpiada")

    def _preload_caches(self):
        """Carga en memoria datos existentes para evitar consultas repetitivas."""
        self.stdout.write("🔍 Precargando datos existentes en caché...")
        self.supplier_cache = {s.name: s for s in Supplier.objects.all()}
        self.category_cache = {c.name: c for c in Category.objects.all()}
        self.location_cache = {l.name: l for l in Location.objects.all()}
        
        # Crear ubicaciones si no existen
        for name, loc_type in [('Sede Sur', 'sede'), ('Sede Norte', 'sede')]:
            if name not in self.location_cache:
                location = Location.objects.create(name=name, type=loc_type, address=f"Dirección de {name}")
                self.location_cache[name] = location
                self.stdout.write(f"  ✓ Ubicación creada: {name}")

    def _create_purchase_orders_only(self):
        """Genera órdenes de compra únicamente usando las PurchaseOptions existentes."""
        self.stdout.write("📝 Generando órdenes de compra solo a partir de opciones de compra existentes…")
        
        purchase_options = PurchaseOption.objects.select_related('product', 'supplier').filter(
            # Solo opciones que no tienen items todavía
            id__in=PurchaseOption.objects.exclude(
                id__in=PurchaseOrderItem.objects.values_list('purchase_option_id', flat=True)
            )
        )
        
        if not purchase_options.exists():
            self.stdout.write("ℹ️  No hay opciones de compra sin órdenes asociadas.")
            return
        
        # Asegurar que existan ubicaciones destino
        if not self.location_cache:
            self._preload_caches()
        dest = self.location_cache.get('Sede Sur') or self.location_cache.get('Sede Norte')
        if not dest:
            if self.location_cache:
                dest = next(iter(self.location_cache.values()))
            else:
                dest = Location.objects.create(name='Sede Principal', type='sede', address='Dirección Principal')
                self.location_cache[dest.name] = dest
        
        # Agrupar por proveedor
        orders_by_supplier = {}
        from django.db.models import Sum
        
        for po in purchase_options:
            if po.supplier_id not in orders_by_supplier:
                orders_by_supplier[po.supplier_id] = {
                    'supplier': po.supplier,
                    'items': []
                }
            
            # Calcular cantidad según stock existente
            total_qty = InventoryStock.objects.filter(product=po.product).aggregate(total=Sum('quantity'))['total'] or 1
            orders_by_supplier[po.supplier_id]['items'].append({
                'purchase_option': po,
                'quantity': max(total_qty, 1)
            })
        
        # Crear órdenes en lote
        orders_to_create = []
        for supplier_id, order_data in orders_by_supplier.items():
            order = PurchaseOrder(
                supplier=order_data['supplier'],
                destination=dest,
                order_date=date.today(),
                status='pending',  # pendiente para poder agregar ítems
                notes='Orden generada por --orders-only'
            )
            orders_to_create.append(order)
        
        self.stdout.write(f"📋 Creando {len(orders_to_create)} órdenes de compra...")
        created_orders = PurchaseOrder.objects.bulk_create(orders_to_create)
        
        # Crear mapa de órdenes por supplier_id
        order_map = {order.supplier_id: order for order in created_orders}
        
        # Crear items en lote
        items_to_create = []
        for supplier_id, order_data in orders_by_supplier.items():
            order = order_map.get(supplier_id)
            if order:
                for item_data in order_data['items']:
                    item = PurchaseOrderItem(
                        order=order,
                        purchase_option=item_data['purchase_option'],
                        quantity_requested=item_data['quantity'],
                        unit_price=item_data['purchase_option'].purchase_price
                    )
                    items_to_create.append(item)
        
        self.stdout.write(f"🛒 Creando {len(items_to_create)} items de órdenes...")
        PurchaseOrderItem.objects.bulk_create(items_to_create, batch_size=500)
        
        # Marcar todas las órdenes como recibidas
        self.stdout.write("✅ Marcando órdenes como recibidas...")
        for order in created_orders:
            order.mark_as_received()
        
        self.stats['purchase_orders_created'] = len(created_orders)
        self.stats['purchase_order_items_created'] = len(items_to_create)

    def handle(self, *args, **options):
        """
        Punto de entrada para el comando.
        """
        csv_file_path = options['csv_file']
        clear_data_flag = options['clear_data']
        dry_run_flag = options.get('dry_run')
        orders_only_flag = options.get('orders_only')
        
        if not os.path.exists(csv_file_path):
            raise CommandError(f"El archivo '{csv_file_path}' no existe.")

        if clear_data_flag:
            self.stdout.write(self.style.WARNING('Limpiando la base de datos...'))
            if dry_run_flag:
                with transaction.atomic():
                    self._clear_database()
                    transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('DRY RUN: Limpieza simulada sin cambios persistentes.'))
            else:
                self._clear_database()
                self.stdout.write(self.style.SUCCESS('Base de datos limpiada.'))

        self.stdout.write(self.style.SUCCESS(
            f"Iniciando la importación desde {csv_file_path} ({'DRY RUN' if dry_run_flag else 'EJECUCIÓN REAL'})"))

        self._preload_caches()

        if orders_only_flag:
            self._create_purchase_orders_only()
            self._show_summary()
            return

        # Fase 1: Leer el CSV y preparar objetos en memoria
        products_to_create = []
        data_for_related_objects = []
        
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader)  # Saltar header
            
            existing_skus = set(Product.objects.values_list('sku', flat=True))
            
            for row_num, row in enumerate(reader, 1):
                try:
                    if len(row) < 12:
                        continue
                    
                    product_name = row[0].strip()
                    if not product_name or product_name.startswith('NO USAR'): continue
                    
                    # Extraer referencias para la descripción
                    referencias = row[1].strip() if len(row) > 1 else ''
                    
                    cat_info = self._categorize_product(product_name)
                    sku = self.validator.generate_next_sku(cat_info[0], cat_info[1], cat_info[2], existing_skus)
                    existing_skus.add(sku)
                    
                    fecha_vencimiento = self._parse_date(row[9].strip())
                    requires_batch = fecha_vencimiento is not None

                    sale_price_val = self._clean_price(row[11].strip()) if len(row) > 11 else None
                    
                    # Crear descripción con referencias si están disponibles
                    description = ""
                    if referencias and referencias.lower() != 'referencias':
                        description = referencias
                    cat_name = self.validator.CATEGORIAS.get(cat_info[0], cat_info[0])
                    if cat_name not in self.category_cache:
                        category = Category.objects.create(name=cat_name, description=f"Categoría {cat_name}")
                        self.category_cache[cat_name] = category
                    
                    product = Product(
                        sku=sku,
                        name=product_name,
                        description=description,
                        unit='unidad', # Simplificado para el script
                        category_id=self.category_cache[cat_name].id,
                        requires_batch_control=requires_batch,
                        sale_price=sale_price_val
                    )
                    products_to_create.append(product)
                    
                    # Guardar datos adicionales para las siguientes fases
                    data_for_related_objects.append({
                        'sku': sku,
                        'product_obj': product,
                        'fecha_vencimiento': fecha_vencimiento,
                        'supplier_name': self._extract_supplier_name(row[6].strip()),
                        'precio_compra': self._clean_price(row[10].strip()),
                        'precio_venta': sale_price_val,
                        'stock_sur': self._clean_stock_quantity(row[7].strip(), row_num),
                        'stock_norte': self._clean_stock_quantity(row[8].strip(), row_num),
                    })
                    
                    if row_num % 500 == 0:
                        self.stdout.write(f"  - {row_num} filas leídas del CSV...")

                except Exception as e:
                    self.errors.append(f"Línea {row_num}: Error procesando '{row[0]}': {e}")
        
        self.stdout.write(f"ℹ️  {len(products_to_create)} productos listos para ser creados.")

        # Fase 2: Creación masiva
        try:
            with transaction.atomic():
                # Crear Productos
                self.stdout.write("\n📦 Creando productos en masa...")
                Product.objects.bulk_create(products_to_create, batch_size=500)
                self.stats['products_created'] = len(products_to_create)
                
                # Mapear productos creados por SKU para fácil acceso
                product_map = {p.sku: p for p in Product.objects.all()}
                
                # Preparar objetos relacionados
                batches_to_create = []
                purchase_options_to_create = []
                stocks_to_create = []
                
                self.stdout.write("📋 Preparando lotes, compras y stock...")
                
                # Crear proveedores que no existen en caché
                for data in data_for_related_objects:
                    s_name = data['supplier_name']
                    if s_name and s_name not in self.supplier_cache:
                        supplier = Supplier.objects.create(name=s_name, contact_name=f"Contacto {s_name}")
                        self.supplier_cache[s_name] = supplier
                        self.stats['suppliers_created'] += 1

                for data in data_for_related_objects:
                    product = product_map.get(data['sku'])
                    if not product: continue
                    
                    # Preparar Lotes (Batches)
                    if product.requires_batch_control:
                        batch = ProductBatch(
                            product_id=product.id,
                            batch_number=f"LOTE-{product.sku}-{data['fecha_vencimiento'].strftime('%Y%m%d')}",
                            expiry_date=data['fecha_vencimiento']
                        )
                        batches_to_create.append(batch)
                        data['batch_obj'] = batch

                    # Preparar Opciones de Compra
                    s_name = data['supplier_name']
                    if s_name and data['precio_compra']:
                        supplier = self.supplier_cache.get(s_name)
                        if supplier:
                            po = PurchaseOption(
                                product_id=product.id,
                                supplier_id=supplier.id,
                                purchase_price=data['precio_compra'],
                                valid_from=date.today(),
                                valid_to=date.today() + timedelta(days=365)
                            )
                            purchase_options_to_create.append(po)

                # Crear Lotes
                self.stdout.write(f"🏭 Creando {len(batches_to_create)} lotes en masa...")
                ProductBatch.objects.bulk_create(batches_to_create, batch_size=500)
                self.stats['batches_created'] = len(batches_to_create)
                
                # Mapear lotes por producto para stock
                batch_map = {b.product_id: b for b in ProductBatch.objects.select_related('product').all()}
                
                # Preparar Stock
                for data in data_for_related_objects:
                    product = product_map.get(data['sku'])
                    if not product: continue
                    
                    batch_for_stock = batch_map.get(product.id) if product.requires_batch_control else None
                    
                    if data['stock_sur'] > 0:
                        stocks_to_create.append(InventoryStock(
                            product_id=product.id,
                            location_id=self.location_cache['Sede Sur'].id,
                            batch_id=batch_for_stock.id if batch_for_stock else None,
                            quantity=data['stock_sur']
                        ))
                    if data['stock_norte'] > 0:
                        stocks_to_create.append(InventoryStock(
                            product_id=product.id,
                            location_id=self.location_cache['Sede Norte'].id,
                            batch_id=batch_for_stock.id if batch_for_stock else None,
                            quantity=data['stock_norte']
                        ))

                # Crear Opciones de Compra
                self.stdout.write(f"💰 Creando {len(purchase_options_to_create)} opciones de compra...")
                PurchaseOption.objects.bulk_create(purchase_options_to_create, batch_size=500)
                self.stats['purchase_options_created'] = len(purchase_options_to_create)

                # Crear Stock de Inventario
                self.stdout.write(f"📊 Creando {len(stocks_to_create)} registros de stock...")
                InventoryStock.objects.bulk_create(stocks_to_create, batch_size=500)
                self.stats['inventory_stock_created'] = len(stocks_to_create)

                # -------------------------------------------------------------
                # Crear Órdenes de Compra e Ítems (OPTIMIZADO)
                # -------------------------------------------------------------
                self.stdout.write("📝 Preparando órdenes de compra y sus items...")
                
                # Agrupar por proveedor para crear una orden por proveedor
                orders_by_supplier = {}
                purchase_option_lookup = { (po.product_id, po.supplier_id): po for po in PurchaseOption.objects.all() }
                
                for data in data_for_related_objects:
                    product = product_map.get(data['sku'])
                    supplier = self.supplier_cache.get(data['supplier_name']) if data['supplier_name'] else None
                    if not product or not supplier or not data['precio_compra']:
                        continue

                    # Definir ubicación destino según dónde hay stock (o por defecto Sede Sur)
                    if data['stock_sur'] > 0 and 'Sede Sur' in self.location_cache:
                        dest = self.location_cache['Sede Sur']
                    elif data['stock_norte'] > 0 and 'Sede Norte' in self.location_cache:
                        dest = self.location_cache['Sede Norte']
                    else:
                        dest = next(iter(self.location_cache.values()))  # Cualquiera disponible

                    # Agrupar por proveedor y destino
                    key = (supplier.id, dest.id)
                    if key not in orders_by_supplier:
                        orders_by_supplier[key] = {
                            'supplier': supplier,
                            'destination': dest,
                            'items': []
                        }
                    
                    po_key = (product.id, supplier.id)
                    po_model = purchase_option_lookup.get(po_key)
                    if po_model:
                        quantity = max(data['stock_sur'] + data['stock_norte'], 1)
                        orders_by_supplier[key]['items'].append({
                            'purchase_option': po_model,
                            'quantity': quantity
                        })

                # Crear órdenes en lotes
                orders_to_create = []
                for (supplier_id, dest_id), order_data in orders_by_supplier.items():
                    order = PurchaseOrder(
                        supplier_id=supplier_id,
                        destination_id=dest_id,
                        order_date=date.today(),
                        status='pending',  # Debe ser pendiente para poder agregar ítems
                        notes='Orden generada automáticamente por el script de población'
                    )
                    orders_to_create.append(order)

                self.stdout.write(f"📋 Creando {len(orders_to_create)} órdenes de compra en lote...")
                created_orders = PurchaseOrder.objects.bulk_create(orders_to_create)
                self.stats['purchase_orders_created'] = len(created_orders)

                # Crear mapa de órdenes por (supplier_id, destination_id)
                order_map = {}
                for order in created_orders:
                    key = (order.supplier_id, order.destination_id)
                    order_map[key] = order

                # Crear items en lotes
                items_to_create = []
                for (supplier_id, dest_id), order_data in orders_by_supplier.items():
                    order = order_map.get((supplier_id, dest_id))
                    if order:
                        for item_data in order_data['items']:
                            item = PurchaseOrderItem(
                                order_id=order.id,
                                purchase_option_id=item_data['purchase_option'].id,
                                quantity_requested=item_data['quantity'],
                                unit_price=item_data['purchase_option'].purchase_price
                            )
                            items_to_create.append(item)

                self.stdout.write(f"🛒 Creando {len(items_to_create)} items de órdenes en lote...")
                PurchaseOrderItem.objects.bulk_create(items_to_create, batch_size=500)
                self.stats['purchase_order_items_created'] = len(items_to_create)

                # Marcar órdenes como recibidas en lote
                self.stdout.write("✅ Marcando órdenes como recibidas...")
                for order in created_orders:
                    order.mark_as_received()

                if dry_run_flag:
                    transaction.set_rollback(True)
                    self.stdout.write("⚠️  DRY RUN: transacción revertida, no se aplicaron cambios.")
                else:
                    self.stdout.write("✅ Transacción completada exitosamente.")

        except Exception as e:
            raise CommandError(f'Error durante la creación masiva: {e}')
        
        self._show_summary()
        if dry_run_flag:
            self.stdout.write(self.style.WARNING("DRY RUN finalizado: no se modificó la base de datos."))

    def _show_summary(self):
        """Muestra el resumen final de la población."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("🎉 RESUMEN DE POBLACIÓN OPTIMIZADA")
        self.stdout.write("=" * 80)
        
        self.stdout.write(f"📦 Productos creados: {self.stats['products_created']}")
        self.stdout.write(f"🏭 Lotes de producto creados: {self.stats['batches_created']}")
        self.stdout.write(f"🏢 Proveedores creados: {self.stats['suppliers_created']}")
        self.stdout.write(f"💰 Opciones de compra creadas: {self.stats['purchase_options_created']}")
        self.stdout.write(f"📑 Órdenes de compra creadas: {self.stats['purchase_orders_created']}")
        self.stdout.write(f"🛒 Ítems de órdenes creados: {self.stats['purchase_order_items_created']}")
        self.stdout.write(f"📊 Stocks de inventario creados: {self.stats['inventory_stock_created']}")
        
        if self.errors:
            self.stdout.write(f"\n⚠️  Errores encontrados durante la lectura: {len(self.errors)}")
            for error in self.errors[:10]:
                self.stdout.write(f"  • {error}")
            if len(self.errors) > 10:
                self.stdout.write(f"  ... y {len(self.errors) - 10} más.")
        
        self.stdout.write("\n🚀 ¡Base de datos poblada exitosamente con el script rápido!")
