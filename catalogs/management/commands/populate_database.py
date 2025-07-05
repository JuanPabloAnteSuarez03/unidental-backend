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
from sales.models import Customer, Sale, SaleItem, Return, ReturnItem, update_inventory_on_return_item_delete, update_return_total
from credits.models import CreditAccount, CreditPayment
from purchases.models import PurchaseOrder, PurchaseOrderItem


class Command(BaseCommand):
    """
    Comando para poblar TODA la base de datos de UNIDENTAL desde el CSV.
    
    Uso: python manage.py populate_database [archivo.csv]
    """
    help = 'Pobla toda la base de datos desde el archivo CSV de UNIDENTAL'

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
            '--create-demo-data',
            action='store_true',
            help='Crear datos de demostración adicionales (clientes, ventas, créditos)'
        )
        parser.add_argument(
            '--only-missing',
            action='store_true',
            help='Solo procesar productos que no existen en la base de datos'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin realizar cambios en la base de datos'
        )
        parser.add_argument(
            '--orders-only',
            action='store_true',
            help='Crear únicamente órdenes de compra e ítems a partir de opciones existentes (sin modificar otras entidades)'
        )

    def __init__(self):
        super().__init__()
        # Asegurar salida UTF-8 para evitar errores de consola en Windows
        import sys
        try:
            if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
        self.validator = SKUValidator()
        self.category_mapping = self._create_category_mapping()
        
        # Contadores para estadísticas
        self.stats = {
            'categories': 0,
            'products': 0,
            'suppliers': 0,
            'locations': 0,
            'purchase_options': 0,
            'purchase_orders': 0,
            'purchase_order_items': 0,
            'inventory_stock': 0,
            'inventory_movements': 0,
            'customers': 0,
            'sales': 0,
            'credits': 0,
            'product_batches': 0,
            'skipped_existing': 0,
        }
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
        
        formats_to_try = [
            '%d/%m/%Y',  # 24/05/2025
            '%d-%m-%Y',  # 24-05-2025
            '%Y-%m-%d',  # 2025-05-24
            '%d/%m/%y',  # 24/05/25
        ]
        
        for fmt in formats_to_try:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        # Si no se pudo parsear, registrar el error
        self.errors.append(f"Formato de fecha no reconocido para '{date_str}'")
        return None

    def _clean_price(self, price_str):
        """Limpia y convierte un precio con posibles separadores de miles/decimales a Decimal."""
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
                        return None
                    return price
                except (InvalidOperation, ValueError):
                    continue
        
        # Si no se encontró ningún patrón válido
        return None

    def _clean_stock_quantity(self, stock_str):
        """
        Limpia y convierte una cadena de stock a entero.
        """
        if not stock_str or stock_str.strip() == '':
            return 0
        
        # Remover caracteres no numéricos
        cleaned = re.sub(r'[^\d]', '', str(stock_str))
        
        try:
            return int(cleaned) if cleaned else 0
        except ValueError:
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
        existing_suppliers = Supplier.objects.all()
        for existing_supplier in existing_suppliers:
            if existing_supplier.name.upper() == supplier_str:
                return existing_supplier.name
        
        # Buscar coincidencias parciales con proveedores existentes
        supplier_match = self._find_best_supplier_match(supplier_str, existing_suppliers)
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

    def _find_best_supplier_match(self, supplier_str, existing_suppliers):
        """
        Encuentra la mejor coincidencia entre proveedores existentes usando diferentes estrategias.
        """
        supplier_str_clean = supplier_str.upper()
        
        # Lista de nombres de proveedores existentes para comparar
        existing_names = [s.name for s in existing_suppliers]
        
        # Estrategia 1: Coincidencia por contenido (el proveedor existente está contenido en el string)
        for existing in existing_names:
            if existing.upper() in supplier_str_clean:
                return existing
        
        # Estrategia 2: Coincidencia inversa (el string está contenido en el proveedor existente)
        for existing in existing_names:
            if supplier_str_clean in existing.upper():
                return existing
        
        # Estrategia 3: Coincidencia por palabras clave
        supplier_words = set(supplier_str_clean.split())
        best_match = None
        best_score = 0
        
        for existing in existing_names:
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
        
        # Verificar si los proveedores del mapeo manual existen
        existing_names_set = set(existing_names)
        for key, mapped_supplier in manual_mappings.items():
            if key in supplier_str_clean and mapped_supplier in existing_names_set:
                return mapped_supplier
        
        return best_match

    def _get_or_create_category(self, name):
        """
        Obtiene o crea una categoría por nombre.
        """
        category, created = Category.objects.get_or_create(
            name=name,
            defaults={'description': f'Categoría generada automáticamente para {name}'}
        )
        
        if created:
            self.stats['categories'] += 1
            self.stdout.write(f"  ✓ Categoría creada: {name}")
        
        return category

    def _generate_sku(self, categoria, subcategoria, tipo):
        """
        Genera un SKU único para la combinación dada.
        """
        existing_skus = list(Product.objects.values_list('sku', flat=True))
        return self.validator.generate_next_sku(categoria, subcategoria, tipo, existing_skus)

    def _get_or_create_supplier(self, supplier_name):
        """
        Obtiene o crea un proveedor por nombre.
        """
        if not supplier_name:
            return None
            
        supplier, created = Supplier.objects.get_or_create(
            name=supplier_name,
            defaults={
                'contact_name': f'Contacto {supplier_name}',
                'email': f'contacto@{supplier_name.lower().replace(" ", "")}.com'
            }
        )
        
        if created:
            self.stats['suppliers'] += 1
            self.stdout.write(f"  ✓ Proveedor creado: {supplier_name}")
        
        return supplier

    def _clear_database(self):
        """
        Limpia toda la base de datos (excepto usuarios admin).
        """
        self.stdout.write("🗑️  Limpiando base de datos...")
        
        # Desactivar señales que manipulan inventario durante la eliminación
        post_delete.disconnect(update_inventory_on_return_item_delete, sender=ReturnItem)
        post_delete.disconnect(update_return_total, sender=ReturnItem)
        try:
            ReturnItem.objects.all().delete()
            Return.objects.all().delete()

            CreditPayment.objects.all().delete()
            CreditAccount.objects.all().delete()

            SaleItem.objects.all().delete()
            Sale.objects.all().delete()
            Customer.objects.all().delete()

            InventoryMovement.objects.all().delete()
            InventoryStock.objects.all().delete()

            from purchases.models import PurchaseOrderItem, PurchaseOrder
            PurchaseOrderItem.objects.all().delete()
            PurchaseOrder.objects.all().delete()

            PurchaseOption.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Supplier.objects.all().delete()
            Location.objects.all().delete()
        finally:
            post_delete.connect(update_inventory_on_return_item_delete, sender=ReturnItem)
            post_delete.connect(update_return_total, sender=ReturnItem)
        
        self.stdout.write("✅ Base de datos limpiada")

    def _create_locations(self):
        """
        Crea las ubicaciones básicas: Sede Sur y Sede Norte.
        """
        locations = [
            ('Sede Sur', 'sede', 'Sede principal ubicada en el sur de la ciudad'),
            ('Sede Norte', 'sede', 'Sede secundaria ubicada en el norte de la ciudad'),
        ]
        
        created_locations = {}
        for name, location_type, address in locations:
            location, created = Location.objects.get_or_create(
                name=name,
                defaults={'type': location_type, 'address': address}
            )
            
            if created:
                self.stats['locations'] += 1
                self.stdout.write(f"  ✓ Ubicación creada: {name}")
            
            created_locations[name] = location
        
        return created_locations

    def _create_admin_user(self):
        """
        Crea un usuario administrador si no existe.
        """
        admin_user, created = User.objects.get_or_create(
            username='admin_unidental',
            defaults={
                'email': 'admin@unidental.com',
                'first_name': 'Admin',
                'last_name': 'Unidental',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        
        if created:
            admin_user.set_password('admin123')  # Cambiar en producción
            admin_user.save()
            self.stdout.write("  ✓ Usuario administrador creado")
        
        return admin_user

    def _parse_csv_row(self, row):
        """
        Parsea una fila del CSV y extrae los datos relevantes.
        """
        if len(row) < 12:
            return None
        
        product_name = row[0].strip()
        if not product_name or product_name.startswith('NO USAR') or product_name == 'referencias':
            return None
        
        # Ajustar índices para nuevo CSV: se añadieron columnas vacías entre referencias y datos clave
        # Estructura relevante (0-based):
        # 0: nombre, 1: referencias, 2-5: vacías, 6: proveedor,
        # 7: inventario sur, 8: inventario norte, 9: fecha vencimiento, 10: precio compra,
        # 11: precio venta

        referencias = row[1].strip() if len(row) > 1 else ''
        proveedor = row[6].strip() if len(row) > 6 else ''
        inventario_sur = row[7].strip() if len(row) > 7 else ''
        inventario_norte = row[8].strip() if len(row) > 8 else ''
        fecha_vencimiento_str = row[9].strip() if len(row) > 9 else ''
        precio_compra_str = row[10].strip() if len(row) > 10 else ''
        precio_venta_str = row[11].strip() if len(row) > 11 else ''
        
        # Limpiar datos
        precio_compra = self._clean_price(precio_compra_str)
        precio_venta = self._clean_price(precio_venta_str)
        stock_sur = self._clean_stock_quantity(inventario_sur)
        stock_norte = self._clean_stock_quantity(inventario_norte)
        supplier_name = self._extract_supplier_name(proveedor)
        fecha_vencimiento = self._parse_date(fecha_vencimiento_str)
        
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
        
        # Crear descripción
        description_parts = []
        if referencias and referencias.lower() != 'referencias':
            description_parts.append(referencias)
        if proveedor:
            description_parts.append(f"Proveedor: {proveedor}")
        
        description = '. '.join(description_parts) if description_parts else ""
        
        return {
            'name': product_name,
            'description': description,
            'unit': unit,
            'precio_compra': precio_compra,
            'precio_venta': precio_venta,
            'stock_sur': stock_sur,
            'stock_norte': stock_norte,
            'supplier_name': supplier_name,
            'fecha_vencimiento': fecha_vencimiento
        }

    def _create_demo_customers(self):
        """
        Crea clientes de demostración.
        """
        demo_customers = [
            {
                'name': 'Dr. Carlos Rodríguez',
                'phone': '3001234567',
                'email': 'carlos.rodriguez@gmail.com',
                'notes': 'Odontólogo especialista en endodoncia'
            },
            {
                'name': 'Clínica Dental Sonrisas',
                'phone': '3019876543',
                'email': 'contacto@sonrisas.com',
                'notes': 'Clínica dental familiar'
            },
            {
                'name': 'Dra. María Pérez',
                'phone': '3105555555',
                'email': 'maria.perez@outlook.com',
                'notes': 'Ortodoncista'
            },
        ]
        
        created_customers = []
        for customer_data in demo_customers:
            customer, created = Customer.objects.get_or_create(
                name=customer_data['name'],
                defaults=customer_data
            )
            
            if created:
                self.stats['customers'] += 1
                self.stdout.write(f"  ✓ Cliente creado: {customer_data['name']}")
            
            created_customers.append(customer)
        
        return created_customers

    def _create_purchase_orders_only(self):
        """Genera órdenes de compra basadas en las PurchaseOptions almacenadas."""
        self.stdout.write("📝 Creando solo órdenes de compra a partir de opciones existentes…")
        
        # Obtener opciones de compra que no tienen items asociados
        purchase_options = PurchaseOption.objects.select_related('product', 'supplier').filter(
            id__in=PurchaseOption.objects.exclude(
                id__in=PurchaseOrderItem.objects.values_list('purchase_option_id', flat=True)
            )
        )
        
        if not purchase_options.exists():
            self.stdout.write("ℹ️  No hay opciones de compra sin órdenes asociadas.")
            return
            
        # Asegurar ubicaciones
        sede = Location.objects.filter(name__icontains='Sede').first()
        if not sede:
            sede = Location.objects.create(name='Sede Principal', type='sede', address='Dirección Principal')
        
        # Agrupar por proveedor
        orders_by_supplier = {}
        from django.db.models import Sum
        
        for po in purchase_options:
            if po.supplier_id not in orders_by_supplier:
                orders_by_supplier[po.supplier_id] = {
                    'supplier': po.supplier,
                    'items': []
                }
            
            # Calcular cantidad según stock actual del producto
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
                destination=sede,
                order_date=date.today(),
                status='pending',
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
        
        self.stats['purchase_orders'] = len(created_orders)
        self.stats['purchase_order_items'] = len(items_to_create)

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        clear_data = options['clear_data']
        create_demo = options['create_demo_data']
        only_missing = options['only_missing']
        dry_run = options['dry_run']
        orders_only = options.get('orders_only')
        
        # Verificar que el archivo existe
        if not os.path.exists(csv_file):
            raise CommandError(f'El archivo {csv_file} no existe.')
        
        self.stdout.write(f"🚀 Iniciando población completa de la base de datos")
        self.stdout.write(f"📄 Archivo: {csv_file}")
        self.stdout.write(f"🔧 Modo: {'DRY RUN (sin cambios)' if dry_run else 'POBLACIÓN REAL'}")
        if only_missing:
            self.stdout.write(f"⚡ Solo productos faltantes: ACTIVADO")
        self.stdout.write("=" * 80)
        
        try:
            with transaction.atomic():
                # 1. Limpiar base de datos si se solicita
                if clear_data and not dry_run:
                    self._clear_database()
                
                # 2. Crear usuario administrador
                if not dry_run:
                    admin_user = self._create_admin_user()
                
                # 3. Crear ubicaciones básicas
                self.stdout.write("\n📍 Creando ubicaciones...")
                sede_sur, sede_norte = None, None
                if not dry_run:
                    locations = self._create_locations()
                    sede_sur = locations.get('Sede Sur')
                    sede_norte = locations.get('Sede Norte')
                
                # 4. Procesar archivo CSV
                self.stdout.write("\n📦 Procesando productos del CSV...")
                
                # Cache de productos existentes si usamos --only-missing
                existing_products = set()
                if only_missing:
                    existing_products = set(Product.objects.values_list('name', flat=True))
                    self.stdout.write(f"  📋 {len(existing_products)} productos ya existen en la base de datos")
                
                with open(csv_file, 'r', encoding='utf-8') as file:
                    # Detectar delimitador
                    sample = file.read(1024)
                    file.seek(0)
                    sniffer = csv.Sniffer()
                    delimiter = sniffer.sniff(sample).delimiter
                    
                    reader = csv.reader(file, delimiter=delimiter)
                    
                    processed_products = []
                    skipped_existing = 0
                    
                    for row_num, row in enumerate(reader, 1):
                        if row_num == 1:  # Saltar header
                            continue
                        
                        if row_num % 100 == 0:
                            self.stdout.write(f"  - Progreso: {row_num} filas procesadas. Productos creados: {self.stats['products']}. Errores: {len(self.errors)}.")
                        
                        try:
                            data = self._parse_csv_row(row)
                            if not data:
                                continue
                            
                            # Si solo procesamos faltantes, verificar si ya existe
                            if only_missing and data['name'] in existing_products:
                                skipped_existing += 1
                                self.stats['skipped_existing'] += 1
                                if skipped_existing % 100 == 0:
                                    self.stdout.write(f"  ⏭️  {skipped_existing} productos existentes saltados...")
                                continue
                            
                            # Categorizar producto
                            cat_info = self._categorize_product(data['name'])
                            categoria, subcategoria, tipo = cat_info
                            
                            if not dry_run:
                                # Determinar si el producto requiere control de lote
                                requires_batch = data['fecha_vencimiento'] is not None

                                # Crear categoría
                                categoria_name = self.validator.CATEGORIAS.get(categoria, categoria)
                                category = self._get_or_create_category(categoria_name)
                                
                                # Generar SKU
                                sku = self._generate_sku(categoria, subcategoria, tipo)
                                
                                # Crear o actualizar producto
                                product_defaults = {
                                    'name': data['name'],
                                    'description': data['description'],
                                    'unit': data['unit'],
                                    'category': category,
                                    'requires_batch_control': requires_batch,
                                    'sale_price': data['precio_venta']
                                }
                                
                                # Usamos update_or_create para manejar el caso donde el producto
                                # existe pero necesita ser actualizado (ej: requires_batch_control).
                                product, created = Product.objects.update_or_create(
                                    sku=sku,
                                    defaults=product_defaults
                                )
                                
                                if created:
                                    self.stats['products'] += 1
                                
                                # Crear lote si es necesario
                                batch_obj = None
                                if requires_batch:
                                    # Generar un número de lote único
                                    batch_number = f"LOTE-{sku}-{data['fecha_vencimiento'].strftime('%Y%m%d')}"
                                    
                                    batch_obj, batch_created = ProductBatch.objects.get_or_create(
                                        product=product,
                                        batch_number=batch_number,
                                        defaults={'expiry_date': data['fecha_vencimiento']}
                                    )
                                    if batch_created:
                                        self.stats['product_batches'] += 1

                                # Crear proveedor y opción de compra
                                if data['supplier_name'] and data['precio_compra']:
                                    supplier = self._get_or_create_supplier(data['supplier_name'])
                                    
                                    if supplier:
                                        purchase_option, created = PurchaseOption.objects.get_or_create(
                                            product=product,
                                            supplier=supplier,
                                            brand=f"Marca {supplier.name}",
                                            defaults={
                                                'purchase_price': data['precio_compra'],
                                                'valid_from': date.today(),
                                                'valid_to': date.today() + timedelta(days=365)
                                            }
                                        )
                                        
                                        if created:
                                            self.stats['purchase_options'] += 1

                                        # Crear orden de compra e item asociado
                                        try:
                                            dest_location = sede_sur or sede_norte
                                            if not dest_location:
                                                dest_location = Location.objects.first()
                                            order = PurchaseOrder.objects.create(
                                                supplier=supplier,
                                                destination=dest_location,
                                                order_date=date.today(),
                                                status='pending',  # pendiente para poder agregar ítems
                                                notes='Orden generada automáticamente por el script de población'
                                            )
                                            self.stats['purchase_orders'] += 1

                                            quantity = max(data['stock_sur'] + data['stock_norte'], 1)
                                            PurchaseOrderItem.objects.create(
                                                order=order,
                                                purchase_option=purchase_option,
                                                quantity_requested=quantity,
                                                unit_price=purchase_option.purchase_price
                                            )
                                            self.stats['purchase_order_items'] += 1

                                            # Marcar la orden como recibida después de agregar ítems
                                            try:
                                                order.mark_as_received()
                                            except Exception:
                                                pass
                                        except Exception as oe:
                                            self.errors.append(f"Error creando orden de compra para {product.name}: {oe}")
                                
                                # Crear stock inicial
                                if data['stock_sur'] > 0 and sede_sur:
                                    stock, created = InventoryStock.objects.get_or_create(
                                        product=product,
                                        location=sede_sur,
                                        batch=batch_obj,
                                        defaults={'quantity': data['stock_sur']}
                                    )
                                    
                                    if created:
                                        self.stats['inventory_stock'] += 1
                                        
                                        # Crear movimiento inicial
                                        InventoryMovement.objects.create(
                                            product=product,
                                            location=sede_sur,
                                            movement_type='in',
                                            quantity=data['stock_sur'],
                                            user=admin_user,
                                            notes='Stock inicial importado del CSV',
                                            batch=batch_obj
                                        )
                                        self.stats['inventory_movements'] += 1
                                
                                if data['stock_norte'] > 0 and sede_norte:
                                    stock, created = InventoryStock.objects.get_or_create(
                                        product=product,
                                        location=sede_norte,
                                        batch=batch_obj,
                                        defaults={'quantity': data['stock_norte']}
                                    )
                                    
                                    if created:
                                        self.stats['inventory_stock'] += 1
                                        
                                        # Crear movimiento inicial
                                        InventoryMovement.objects.create(
                                            product=product,
                                            location=sede_norte,
                                            movement_type='in',
                                            quantity=data['stock_norte'],
                                            user=admin_user,
                                            notes='Stock inicial importado del CSV',
                                            batch=batch_obj
                                        )
                                        self.stats['inventory_movements'] += 1
                                
                                processed_products.append(product)
                            
                            else:
                                # En dry run, solo mostrar qué se haría
                                if len(processed_products) < 10:  # Mostrar solo los primeros 10
                                    self.stdout.write(f"  📦 {data['name'][:50]} -> {categoria}-{subcategoria}-{tipo}")
                                processed_products.append(data)
                        
                        except Exception as e:
                            self.errors.append(f"Línea {row_num}: Error procesando '{row[0] if row else 'fila vacía'}': {str(e)}")
                            continue
                
                # 5. Crear datos de demostración si se solicita
                if create_demo and not dry_run:
                    self.stdout.write("\n👥 Creando datos de demostración...")
                    demo_customers = self._create_demo_customers()
                    
                    # Crear algunas ventas de ejemplo
                    if processed_products:
                        import random
                        for i, customer in enumerate(demo_customers):
                            # Asignar una sede
                            sale_location = sede_sur if i % 2 == 0 else sede_norte
                            if not sale_location: # Fallback a la primera que exista
                                sale_location = sede_sur or sede_norte

                            if not sale_location:
                                self.errors.append("No se encontró una ubicación (Sede Sur/Norte) para crear la venta de demostración.")
                                continue
                                
                            # Crear venta
                            sale = Sale.objects.create(
                                customer=customer,
                                location=sale_location,
                                sale_type='normal',
                                should_invoice=True,
                                total_gross=Decimal('0'),
                                total_net=Decimal('0')
                            )
                            
                            # Agregar algunos items aleatorios
                            random_products = random.sample(processed_products[:50], min(3, len(processed_products)))
                            total = Decimal('0')
                            
                            for product in random_products:
                                quantity = random.randint(1, 5)
                                price = Decimal(str(random.randint(10000, 100000)))
                                
                                # Si el producto requiere lote, encontrar uno disponible
                                sale_item_batch = None
                                if product.requires_batch_control:
                                    # Buscar un lote con stock disponible para este producto
                                    stock_with_batch = InventoryStock.objects.filter(
                                        product=product,
                                        batch__isnull=False,
                                        quantity__gt=0
                                    ).first()
                                    
                                    if stock_with_batch:
                                        sale_item_batch = stock_with_batch.batch
                                    else:
                                        # Si no hay lote con stock, saltar este producto en la venta demo
                                        continue
                                
                                SaleItem.objects.create(
                                    sale=sale,
                                    product=product,
                                    quantity=quantity,
                                    unit_price=price,
                                    batch=sale_item_batch
                                )
                                
                                total += quantity * price
                            
                            sale.total_gross = total
                            sale.total_net = total
                            sale.save()
                            
                            self.stats['sales'] += 1
                            
                            # Crear crédito para algunas ventas
                            if i % 2 == 0:  # Crear crédito para ventas pares
                                CreditAccount.objects.create(
                                    sale=sale,
                                    original_amount=total,
                                    remaining_amount=total * Decimal('0.7'),  # 70% pendiente
                                    start_date=date.today(),
                                    due_date=date.today() + timedelta(days=30)
                                )
                                self.stats['credits'] += 1
                
                if dry_run:
                    # En dry run, hacer rollback explícito
                    transaction.set_rollback(True)
        
        except Exception as e:
            raise CommandError(f'Error durante la población: {str(e)}')
        
        # Mostrar resumen final
        self._show_summary()

    def _show_summary(self):
        """
        Muestra el resumen final de la población.
        """
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("🎉 RESUMEN DE POBLACIÓN COMPLETA")
        self.stdout.write("=" * 80)
        
        self.stdout.write(f"📂 Categorías creadas: {self.stats['categories']}")
        self.stdout.write(f"📦 Productos creados: {self.stats['products']}")
        self.stdout.write(f"🏭 Lotes de producto creados: {self.stats['product_batches']}")
        self.stdout.write(f"🏢 Proveedores creados: {self.stats['suppliers']}")
        self.stdout.write(f"📍 Ubicaciones creadas: {self.stats['locations']}")
        self.stdout.write(f"💰 Opciones de compra creadas: {self.stats['purchase_options']}")
        self.stdout.write(f"📑 Órdenes de compra creadas: {self.stats['purchase_orders']}")
        self.stdout.write(f"🛒 Ítems de órdenes creados: {self.stats['purchase_order_items']}")
        self.stdout.write(f"📊 Stocks de inventario creados: {self.stats['inventory_stock']}")
        self.stdout.write(f"📈 Movimientos de inventario creados: {self.stats['inventory_movements']}")
        self.stdout.write(f"👥 Clientes creados: {self.stats['customers']}")
        self.stdout.write(f"🛒 Ventas creadas: {self.stats['sales']}")
        self.stdout.write(f"💳 Cuentas de crédito creadas: {self.stats['credits']}")
        
        if self.stats['skipped_existing'] > 0:
            self.stdout.write(f"⏭️  Productos existentes saltados: {self.stats['skipped_existing']}")
        
        if self.errors:
            self.stdout.write(f"\n⚠️  Errores encontrados: {len(self.errors)}")
            for error in self.errors[:10]:  # Mostrar solo los primeros 10 errores
                self.stdout.write(f"  • {error}")
            if len(self.errors) > 10:
                self.stdout.write(f"  ... y {len(self.errors) - 10} errores más")
        
        total_records = sum(self.stats.values())
        self.stdout.write(f"\n✅ TOTAL DE REGISTROS CREADOS: {total_records}")
        self.stdout.write("🚀 ¡Base de datos poblada exitosamente!") 