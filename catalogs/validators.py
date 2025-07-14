import re
from django.core.exceptions import ValidationError

class SKUValidator:
    """
    Validador para el sistema de SKU de Unidental.
    Formato: [CATEGORIA]-[SUBCATEGORIA]-[TIPO]-[SECUENCIAL]
    Ejemplo: LAB-ART-BIO-001
    Ahora valida contra los modelos de la base de datos.
    """
    
    def __call__(self, value):
        """
        Valida que el SKU siga el formato correcto y que sus componentes existan en la BD.
        """
        from .models import SkuCategory, SkuSubCategory, SkuType

        if not value:
            raise ValidationError("El SKU es obligatorio.")
        
        pattern = r'^[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}-\d{3}$'
        
        if not re.match(pattern, value):
            raise ValidationError(
                "El SKU debe seguir el formato: CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL "
                "(ej: LAB-ART-BIO-001)."
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
        Ej: base_sku='LAB-ART-BIO', existing_skus={'LAB-ART-BIO-001'}
        """
        from catalogs.models import Product
        
        # Encontrar el secuencial más alto para esta base de SKU
        # Primero, buscar en la base de datos
        highest_seq = 0
        
        relevant_skus = Product.objects.filter(sku__startswith=base_sku).values_list('sku', flat=True)
        all_relevant_skus = set(relevant_skus) | set(existing_skus) # Combinar con los SKUs en memoria

        for sku in all_relevant_skus:
            try:
                seq = int(sku.split('-')[-1])
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