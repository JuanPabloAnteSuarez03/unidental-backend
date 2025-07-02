import csv
import re
from decimal import Decimal, InvalidOperation

def clean_price(price_str):
    """Función de limpieza de precios mejorada"""
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
                return price, clean_txt
            except (InvalidOperation, ValueError):
                continue
    
    # Si no se encontró ningún patrón válido
    return None, txt

# Leer CSV y analizar precios de venta
csv_file = "UNIDENTAL - COMPRAS E INV (1).csv"
problematic_prices = []
valid_prices = []
large_prices = []

with open(csv_file, 'r', encoding='utf-8') as file:
    reader = csv.reader(file)
    next(reader)  # Saltar header
    
    for row_num, row in enumerate(reader, 1):
        if len(row) < 12:
            continue
            
        product_name = row[0].strip()
        if not product_name or product_name.startswith('NO USAR'):
            continue
            
        precio_venta_str = row[11].strip() if len(row) > 11 else ''
        
        if precio_venta_str:
            result = clean_price(precio_venta_str)
            if result[0] is None:
                problematic_prices.append((row_num, product_name, precio_venta_str, result[1]))
            else:
                price = result[0]
                if price >= Decimal('10000000000'):
                    large_prices.append((row_num, product_name, precio_venta_str, price))
                else:
                    valid_prices.append((row_num, product_name, precio_venta_str, price))

print(f"=== DIAGNÓSTICO DE PRECIOS DE VENTA ===")
print(f"Precios válidos: {len(valid_prices)}")
print(f"Precios demasiado grandes: {len(large_prices)}")
print(f"Precios problemáticos (no se pudieron parsear): {len(problematic_prices)}")

print(f"\n=== PRECIOS DEMASIADO GRANDES ===")
for row_num, name, original, price in large_prices[:10]:
    print(f"Línea {row_num}: {name[:50]} | Original: '{original}' | Parseado: {price}")

print(f"\n=== PRECIOS PROBLEMÁTICOS ===")
for row_num, name, original, processed in problematic_prices[:10]:
    print(f"Línea {row_num}: {name[:50]} | Original: '{original}' | Procesado: '{processed}'")

print(f"\n=== MUESTRA DE PRECIOS VÁLIDOS ===")
for row_num, name, original, price in valid_prices[:5]:
    print(f"Línea {row_num}: {name[:50]} | Original: '{original}' | Parseado: {price}") 