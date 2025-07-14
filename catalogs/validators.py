import re
from django.core.exceptions import ValidationError

class SKUValidator:
    """
    Validador para el sistema de SKU de Unidental.
    Formato: [CATEGORIA]-[SUBCATEGORIA]-[TIPO]-[SECUENCIAL]
    Ejemplo: LAB-ART-BIO-001
    Ahora valida contra los modelos de la base de datos.
    Acepta tanto 3 como 4 dígitos en el secuencial por compatibilidad con datos legacy.
    """
    
    def __call__(self, value):
        """
        Valida que el SKU siga el formato correcto y que sus componentes existan en la BD.
        Acepta secuenciales de 3 o 4 dígitos por compatibilidad.
        """
        from .models import SkuCategory, SkuSubCategory, SkuType

        if not value:
            raise ValidationError("El SKU es obligatorio.")
        
        # Patrón actualizado para aceptar 3 o 4 dígitos en el secuencial
        pattern = r'^[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}-\d{3,4}$'
        
        if not re.match(pattern, value):
            raise ValidationError(
                "El SKU debe seguir el formato: CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL "
                "(ej: LAB-ART-BIO-001 o LAB-ART-BIO-1001)."
            )
        
        # Dividir el SKU en partes
        cat_code, sub_code, type_code, _ = value.split('-')
        
        try:
            # Validar que los componentes existen en la base de datos
            sku_cat = SkuCategory.objects.get(code=cat_code)
            sku_sub = SkuSubCategory.objects.get(category=sku_cat, code=sub_code)
            SkuType.objects.get(subcategory=sku_sub, code=type_code)
        except SkuCategory.DoesNotExist:
            raise ValidationError(f"El código de categoría de SKU '{cat_code}' no existe.")
        except SkuSubCategory.DoesNotExist:
            raise ValidationError(f"El código de subcategoría '{sub_code}' no existe para la categoría '{cat_code}'.")
        except SkuType.DoesNotExist:
            raise ValidationError(f"El código de tipo '{type_code}' no existe para la subcategoría '{cat_code}-{sub_code}'.")
    
    @classmethod
    def get_sku_structure_info(cls):
        """
        Devuelve la información completa de la estructura de SKUs desde la BD.
        """
        # Esta función ahora podría ser un endpoint de API que serialice los modelos
        # para mostrar las opciones disponibles en el frontend.
        return {
            'formato': 'CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL',
            'ejemplo': 'LAB-ART-BIO-001',
            'descripcion': 'Sistema basado en la base de datos de componentes de SKU.'
        }
    
    @classmethod
    def generate_next_sku(cls, base_sku, existing_skus=[]):
        """
        Genera el siguiente SKU secuencial para una base dada.
        SOLO considera SKUs de 3 dígitos para el cálculo del consecutivo.
        Los SKUs de 4 dígitos se ignoran por ser datos legacy incorrectos.
        Ej: base_sku='LAB-ART-BIO', existing_skus={'LAB-ART-BIO-001'}
        """
        from catalogs.models import Product
        import re
        
        # Encontrar el secuencial más alto SOLO de SKUs con 3 dígitos
        highest_seq = 0
        
        # Buscar en la base de datos SKUs que coincidan exactamente con el patrón
        # Usar un filtro más específico para evitar coincidencias parciales
        pattern = f"{base_sku}-"
        relevant_skus = Product.objects.filter(sku__startswith=pattern).values_list('sku', flat=True)
        all_relevant_skus = set(relevant_skus) | set(existing_skus)

        # Patrón para validar SKUs de exactamente 3 dígitos
        three_digit_pattern = re.compile(r'^' + re.escape(base_sku) + r'-\d{3}$')

        for sku in all_relevant_skus:
            try:
                # Verificar que el SKU tiene exactamente el formato esperado Y tiene 3 dígitos
                parts = sku.split('-')
                if len(parts) == 4 and sku.startswith(pattern) and three_digit_pattern.match(sku):
                    seq_str = parts[-1]  # Último elemento debería ser el número secuencial
                    # Solo procesar si es exactamente de 3 dígitos
                    if len(seq_str) == 3:
                        seq = int(seq_str)
                        if seq > highest_seq:
                            highest_seq = seq
            except (ValueError, IndexError):
                continue
        
        # El nuevo secuencial es el más alto + 1
        new_seq = highest_seq + 1
        
        # Formatear a 3 dígitos con ceros a la izquierda
        return f"{base_sku}-{new_seq:03d}"

def validate_sku(value):
    """
    Función de validación para usar en los campos del modelo de Django.
    """
    validator = SKUValidator()
    validator(value) 