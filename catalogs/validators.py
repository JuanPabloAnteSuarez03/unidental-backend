import re
from django.core.exceptions import ValidationError

class SKUValidator:
    """
    Validador para el sistema de SKU de Unidental.
    Formato: [CATEGORIA]-[SUBCATEGORIA]-[TIPO]-[SECUENCIAL]
    Ejemplo: LAB-ART-BIO-001
    Basado en análisis del inventario real de UNIDENTAL.
    """
    
    # Definición de categorías válidas basadas en el inventario real
    CATEGORIAS = {
        'ACE': 'Accesorios y Complementos',
        'ANE': 'Anestesia y Control de Dolor', 
        'RES': 'Materiales de Restauración',
        'IMP': 'Materiales de Impresión',
        'END': 'Endodoncia',
        'PER': 'Periodoncia y Cirugía',
        'BLA': 'Blanqueamiento',
        'PRO': 'Profilaxis y Prevención',
        'LAB': 'Laboratorio',
        'DES': 'Desinfección y Esterilización',
        'ORG': 'Organización y Oficina',
        'ORT': 'Ortodoncia'
    }
    
    # Subcategorías por categoría basadas en productos reales
    SUBCATEGORIAS = {
        'ACE': {
            'BAB': 'Baberos, batas, gorros',
            'GUA': 'Guantes y protección',
            'CON': 'Contenedores y cajas',
            'INS': 'Instrumental básico',
            'DES': 'Desechables'
        },
        'ANE': {
            'TOP': 'Tópicos y geles',
            'CAR': 'Cartuchos y ampolletas',
            'ACE': 'Accesorios para anestesia',
            'AGU': 'Agujas'
        },
        'RES': {
            'COM': 'Composite y resinas',
            'ADH': 'Adhesivos',
            'ACR': 'Acrílicos',
            'CEM': 'Cementos',
            'ION': 'Ionómeros'
        },
        'IMP': {
            'ALG': 'Alginatos',
            'SIL': 'Siliconas',
            'GOD': 'Godiva y ceras',
            'CUB': 'Cubetas',
            'ADH': 'Adhesivos para cubetas'
        },
        'END': {
            'LIM': 'Limas',
            'HID': 'Hidróxido de calcio',
            'IRR': 'Irrigación',
            'OBT': 'Obturación',
            'GUT': 'Gutapercha'
        },
        'PER': {
            'CUR': 'Curetas',
            'BIS': 'Bisturíes',
            'SUT': 'Suturas',
            'HEM': 'Hemostáticos',
            'GRA': 'Grapas'
        },
        'BLA': {
            'CAS': 'Casero',
            'CON': 'Consultorio',
            'ACE': 'Accesorios',
            'BAR': 'Barreras gingivales'
        },
        'PRO': {
            'PIE': 'Piedras y pasta',
            'FLU': 'Flúor y barnices',
            'CEP': 'Cepillos',
            'HIL': 'Hilo dental'
        },
        'LAB': {
            'ART': 'Articuladores',
            'MOD': 'Modelos',
            'YEP': 'Yeso y platinas',
            'FRE': 'Fresas',
            'ACR': 'Acrílicos de laboratorio'
        },
        'DES': {
            'GUT': 'Glutaraldehído',
            'HIP': 'Hipoclorito',
            'ENZ': 'Enzimáticos',
            'BOL': 'Bolsas de esterilización',
            'IND': 'Indicadores biológicos'
        },
        'ORG': {
            'PAP': 'Papelería',
            'LIM': 'Limpieza',
            'ALM': 'Almacenamiento',
            'VAR': 'Varios',
            'BOL': 'Bolsas y empaques'
        },
        'ORT': {
            'ALA': 'Alambres',
            'CAD': 'Cadenetas',
            'BOT': 'Botones',
            'BAN': 'Bandas',
            'ARC': 'Arcos'
        }
    }
    
    # Tipos/materiales específicos del inventario real
    TIPOS_MATERIALES = {
        # Materiales
        'MET': 'Metálico',
        'PLA': 'Plástico',
        'LAT': 'Látex',
        'NIT': 'Nitrilo',
        'ALU': 'Aluminio',
        'ACE': 'Acero',
        'TIT': 'Titanio',
        'CER': 'Cerámica',
        'VID': 'Vidrio',
        'GOD': 'Godiva',
        
        # Marcas importantes del inventario
        'NSK': 'NSK',
        'BIO': 'BioArt',
        'FGM': 'FGM',
        'HUF': 'Hu-Friedy',
        'KER': 'Kerr',
        'M3M': '3M',
        'ULT': 'Ultradent',
        'SEP': 'Septodont',
        'ZHE': 'Zhermack',
        'COL': 'Coltene',
        'MAQ': 'Maquira',
        'ANG': 'Angelus',
        'PRO': 'Prodont',
        'PQU': 'Proquident',
        'NEW': 'New Stetic',
        'DUR': 'Duraphat',
        'GAT': 'Gates',
        'BIS': 'Bisco',
        'JUL': 'Julvident',
        'IVO': 'Ivoclar',
        'GC': 'GC',
        
        # Tamaños y características
        'PEQ': 'Pequeño',
        'MED': 'Mediano',
        'GRA': 'Grande',
        'XGR': 'Extra Grande',
        'AZU': 'Azul',
        'BLA': 'Blanco',
        'NEG': 'Negro',
        'TRA': 'Transparente',
        'EST': 'Estéril',
        'DES': 'Desechable',
        'UNI': 'Universal',
        'ADU': 'Adulto',
        'PED': 'Pediátrico',
        'SET': 'Set/Kit',
        'KIT': 'Kit completo',
        
        # Tipos específicos
        'JER': 'Jeringa',
        'TUB': 'Tubo',
        'CAJ': 'Caja',
        'SOB': 'Sobre',
        'UND': 'Unidad',
        'LIQ': 'Líquido',
        'POL': 'Polvo',
        'GEL': 'Gel',
        'SPR': 'Spray',
        'CRE': 'Crema',
        'PAS': 'Pasta'
    }
    
    def __call__(self, value):
        """
        Valida que el SKU siga el formato correcto.
        """
        if not value:
            raise ValidationError("El SKU es obligatorio.")
        
        # Patrón: CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL
        # Permite letras mayúsculas y números en las primeras 3 partes, solo números en el secuencial
        pattern = r'^[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}-\d{3}$'
        
        if not re.match(pattern, value):
            raise ValidationError(
                "El SKU debe seguir el formato: CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL "
                "(ej: LAB-ART-BIO-001). "
                "Categoría, subcategoría y tipo deben ser de 3 caracteres (letras mayúsculas y números), "
                "el secuencial debe ser de 3 dígitos."
            )
        
        # Dividir el SKU en partes
        partes = value.split('-')
        categoria, subcategoria, tipo, secuencial = partes
        
        # Validar categoría
        if categoria not in self.CATEGORIAS:
            categorias_validas = ', '.join(self.CATEGORIAS.keys())
            raise ValidationError(
                f"Categoría '{categoria}' no válida. "
                f"Categorías válidas: {categorias_validas}"
            )
        
        # Validar subcategoría
        if subcategoria not in self.SUBCATEGORIAS.get(categoria, {}):
            subcategorias_validas = ', '.join(self.SUBCATEGORIAS.get(categoria, {}).keys())
            raise ValidationError(
                f"Subcategoría '{subcategoria}' no válida para la categoría '{categoria}'. "
                f"Subcategorías válidas: {subcategorias_validas}"
            )
        
        # Validar tipo/material (más flexible, no obligatorio que esté en la lista)
        if tipo not in self.TIPOS_MATERIALES:
            # Solo mostrar una advertencia en los logs, no un error
            pass
    
    @classmethod
    def get_sku_structure_info(cls):
        """
        Devuelve la información completa de la estructura de SKUs.
        """
        return {
            'formato': 'CATEGORIA-SUBCATEGORIA-TIPO-SECUENCIAL',
            'ejemplo': 'LAB-ART-BIO-001',
            'descripcion': 'Sistema basado en el inventario real de UNIDENTAL',
            'categorias': cls.CATEGORIAS,
            'subcategorias': cls.SUBCATEGORIAS,
            'tipos_materiales': cls.TIPOS_MATERIALES,
            'ejemplos_reales': [
                {
                    'producto': 'ARTICULADOR BIO-ART',
                    'sku': 'LAB-ART-BIO-001',
                    'explicacion': 'Laboratorio - Articulador - BioArt - 001'
                },
                {
                    'producto': 'ANESTESIA SEPTODONT 1/100.000',
                    'sku': 'ANE-CAR-SEP-001',
                    'explicacion': 'Anestesia - Cartucho - Septodont - 001'
                },
                {
                    'producto': 'Adhesivo 3M Universal 5ML',
                    'sku': 'RES-ADH-M3M-001',
                    'explicacion': 'Restauración - Adhesivo - 3M - 001'
                },
                {
                    'producto': 'Alginato Hidrogum ZHERMACK',
                    'sku': 'IMP-ALG-ZHE-001',
                    'explicacion': 'Impresión - Alginato - Zhermack - 001'
                },
                {
                    'producto': 'Guantes latex M',
                    'sku': 'ACE-GUA-LAT-001',
                    'explicacion': 'Accesorios - Guantes - Latex - 001'
                }
            ],
            'reglas': [
                'El SKU debe tener exactamente 4 partes separadas por guiones (-)',
                'Categoría: 3 caracteres (letras mayúsculas y números) que identifican el grupo principal',
                'Subcategoría: 3 caracteres (letras mayúsculas y números) que especifican el tipo dentro de la categoría',
                'Tipo/Material: 3 caracteres (letras mayúsculas y números) que identifican marca, material o característica',
                'Secuencial: 3 dígitos (001, 002, etc.) para numeración única',
                'Todas las letras deben estar en mayúsculas',
                'No se permiten espacios ni caracteres especiales excepto el guión separador',
                'El sistema está basado en el inventario real de UNIDENTAL'
            ]
        }
    
    @classmethod
    def generate_next_sku(cls, categoria, subcategoria, tipo, existing_skus=[]):
        """
        Genera el siguiente SKU disponible para una combinación dada.
        """
        if categoria not in cls.CATEGORIAS:
            raise ValueError(f"Categoría '{categoria}' no válida. Válidas: {', '.join(cls.CATEGORIAS.keys())}")
        
        if subcategoria not in cls.SUBCATEGORIAS.get(categoria, {}):
            subcategorias_validas = ', '.join(cls.SUBCATEGORIAS.get(categoria, {}).keys())
            raise ValueError(f"Subcategoría '{subcategoria}' no válida para '{categoria}'. Válidas: {subcategorias_validas}")
        
        # Buscar el siguiente número secuencial disponible
        prefix = f"{categoria}-{subcategoria}-{tipo}-"
        
        # Filtrar SKUs que coincidan con el prefijo
        matching_skus = [sku for sku in existing_skus if sku.startswith(prefix)]
        
        if not matching_skus:
            return f"{prefix}001"
        
        # Extraer números secuenciales y encontrar el siguiente
        secuenciales = []
        for sku in matching_skus:
            try:
                secuencial = int(sku.split('-')[3])
                secuenciales.append(secuencial)
            except (IndexError, ValueError):
                continue
        
        if secuenciales:
            next_secuencial = max(secuenciales) + 1
        else:
            next_secuencial = 1
        
        return f"{prefix}{next_secuencial:03d}"


def validate_sku(value):
    """
    Función de validación para SKU que puede ser serializada por Django.
    Esta función será utilizada en el campo del modelo.
    """
    validator = SKUValidator()
    validator(value) 