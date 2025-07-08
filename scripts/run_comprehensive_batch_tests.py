#!/usr/bin/env python
"""
Script para ejecutar tests comprehensivos de productos con lotes, componentes y jerarquías.

Este script ejecuta todos los tests relacionados con:
1. Productos con lotes en jerarquías complejas
2. Algoritmos de prioridad para desglose de productos
3. FIFO con múltiples lotes en componentes
4. Componentes compartidos entre múltiples kits
5. Casos extremos y edge cases
6. Validaciones de consistencia de lotes
7. Operaciones de alto volumen
8. Prevención de dependencias circulares

Uso:
    python scripts/run_comprehensive_batch_tests.py [--verbose] [--coverage] [--specific TEST_NAME]
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_command(command, capture_output=True):
    """Ejecuta un comando y devuelve el resultado."""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=capture_output, 
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        return result
    except Exception as e:
        print(f"Error ejecutando comando: {command}")
        print(f"Error: {e}")
        return None

def print_section_header(title):
    """Imprime una cabecera de sección formateada."""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def print_subsection_header(title):
    """Imprime una subcabecera formateada."""
    print(f"\n--- {title} ---")

def run_comprehensive_tests(verbose=False, coverage=False, specific_test=None):
    """
    Ejecuta todos los tests comprehensivos de lotes y componentes.
    """
    print_section_header("TESTS COMPREHENSIVOS DE PRODUCTOS CON LOTES Y COMPONENTES")
    print(f"Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Lista de módulos de test a ejecutar
    test_modules = [
        "inventory.tests.test_comprehensive_batch_flows",
        "inventory.tests.test_edge_cases_batch_flows",
        "inventory.tests.test_inventory_with_batches",  # Tests existentes
        "sales.tests.test_sale_with_kits",              # Tests existentes
        "sales.tests.test_sale_with_batches",           # Tests existentes
        "catalogs.tests.test_product_batches",          # Tests existentes
        "catalogs.tests.test_product_components",       # Tests existentes
    ]
    
    # Construir comando pytest
    base_command = "python -m pytest"
    
    if specific_test:
        # Test específico
        command = f"{base_command} -v {specific_test}"
    else:
        # Todos los tests
        test_paths = " ".join(test_modules)
        command = f"{base_command} {test_paths}"
    
    # Opciones adicionales
    if verbose:
        command += " -v -s"
    else:
        command += " -v"
    
    if coverage:
        command += " --cov=inventory --cov=sales --cov=catalogs --cov-report=html --cov-report=term"
    
    # Agregar marcadores específicos para nuestros tests
    command += " -m 'not slow'"  # Excluir tests lentos por defecto
    
    print_subsection_header("Comando de ejecución")
    print(f"Ejecutando: {command}")
    
    print_subsection_header("Resultados de Tests")
    
    # Ejecutar tests
    result = run_command(command, capture_output=False)
    
    if result is None:
        print("❌ Error ejecutando tests")
        return False
    
    print_subsection_header("Resumen de Ejecución")
    
    if result.returncode == 0:
        print("✅ Todos los tests pasaron exitosamente")
        
        # Ejecutar análisis adicional si todos los tests pasaron
        run_additional_analysis(coverage)
        
        return True
    else:
        print("❌ Algunos tests fallaron")
        print(f"Código de salida: {result.returncode}")
        
        # Mostrar resumen de errores si está disponible
        if result.stdout:
            print("\nSalida del comando:")
            print(result.stdout)
        if result.stderr:
            print("\nErrores:")
            print(result.stderr)
        
        return False

def run_additional_analysis(coverage_enabled):
    """Ejecuta análisis adicionales después de los tests."""
    
    print_section_header("ANÁLISIS ADICIONAL")
    
    # 1. Análisis de cobertura
    if coverage_enabled:
        print_subsection_header("Cobertura de Código")
        print("📊 Reporte de cobertura generado en htmlcov/index.html")
        
        # Mostrar resumen de cobertura en terminal
        coverage_command = "python -m pytest --cov=inventory --cov=sales --cov=catalogs --cov-report=term-missing --quiet"
        print("Ejecutando análisis de cobertura...")
        run_command(coverage_command, capture_output=False)
    
    # 2. Verificar integridad de la base de datos de test
    print_subsection_header("Verificación de Integridad")
    check_command = "python manage.py check"
    check_result = run_command(check_command)
    
    if check_result and check_result.returncode == 0:
        print("✅ Verificación de integridad del sistema: OK")
    else:
        print("⚠️  Advertencias en verificación de integridad")
        if check_result:
            print(check_result.stdout)
    
    # 3. Análisis de rendimiento (si disponible)
    print_subsection_header("Métricas de Rendimiento")
    print("📈 Para análisis de rendimiento detallado, ejecute:")
    print("    python -m pytest --benchmark-only")

def generate_test_documentation():
    """Genera documentación de los tests ejecutados."""
    
    documentation = """
# DOCUMENTACIÓN DE TESTS COMPREHENSIVOS

## Escenarios Cubiertos

### 1. Jerarquías Complejas de Productos con Lotes
- ✅ Componentes con lotes que forman parte de productos compuestos
- ✅ Jerarquías anidadas (3+ niveles de componentes)
- ✅ FIFO automático en múltiples niveles
- ✅ Validación de consistencia de lotes

### 2. Algoritmo de Prioridad para Desglose
- ✅ Stock directo del componente (prioridad 1)
- ✅ Cajas homogéneas (boxed_component) - prioridad 2
- ✅ Kits mixtos (mixed_kit) - prioridad 3
- ✅ Optimización por tamaño para minimizar desperdicio

### 3. Componentes Compartidos
- ✅ Componente en múltiples tipos de kits
- ✅ Diferentes cantidades en cada kit
- ✅ Prioridad de desglose para componentes compartidos

### 4. Escenarios de Stock Parcial
- ✅ Stock insuficiente con múltiples lotes
- ✅ Consumo parcial de lotes en ventas secuenciales
- ✅ Disponibilidad entre múltiples ubicaciones
- ✅ Operaciones de alto volumen

### 5. Casos Extremos (Edge Cases)
- ✅ Lotes vencidos y próximos a vencer
- ✅ Stock cero y prevención de stock negativo
- ✅ Prevención de dependencias circulares
- ✅ Validación de cantidades cero
- ✅ Operaciones concurrentes simuladas

### 6. Validaciones Especiales
- ✅ Mezcla de productos con y sin lotes en la misma jerarquía
- ✅ Validación de fechas de vencimiento en componentes
- ✅ Consistencia de lotes en ventas de kits
- ✅ Threshold de días mínimos antes del vencimiento

### 7. Conversiones en Cadena
- ✅ Desarmado de 3 niveles: caja -> blister -> tableta
- ✅ Optimización selectiva de nivel de desarmado
- ✅ FIFO mantenido en toda la cadena

### 8. Re-ensamblaje (Pendiente)
- 🔄 Re-ensamblaje automático al devolver componentes
- 🔄 Validación de suficientes componentes para re-ensamblar

## Productos de Prueba Creados

### Jerarquía de Ejemplo:
```
Kit Premium Hospital
├── Caja Ibuprofeno (5 blisters)
│   └── Blister Ibuprofeno (10 tabletas)
│       └── Tableta Ibuprofeno 600mg [CON LOTES]
└── Caja Amoxicilina (4 blisters)
    └── Blister Amoxicilina (10 cápsulas)
        └── Cápsula Amoxicilina 500mg [CON LOTES]

Kit Médico Completo (Mixto)
├── 2x Blister Ibuprofeno [CON LOTES]
├── 1x Blister Amoxicilina [CON LOTES]
└── 5x Jeringa Desechable [SIN LOTES]
```

### Lotes de Prueba:
- **Tableta Ibuprofeno**: 2 lotes (uno vence antes - FIFO)
- **Cápsula Amoxicilina**: 1 lote bueno
- **Blisters**: Lotes propios independientes
- **Kits y Cajas**: Sin lotes (comportamiento típico)

## Métricas de Testing

### Casos de Prueba por Categoría:
- Jerarquías complejas: 4 tests
- Algoritmo de prioridad: 3 tests
- Componentes compartidos: 2 tests
- Stock parcial: 4 tests
- Edge cases: 15+ tests
- Validaciones especiales: 5 tests
- Conversiones en cadena: 2 tests

### Total: 35+ casos de prueba comprehensivos

## Comandos Útiles

### Ejecutar todos los tests:
```bash
python scripts/run_comprehensive_batch_tests.py
```

### Ejecutar con cobertura:
```bash
python scripts/run_comprehensive_batch_tests.py --coverage
```

### Ejecutar test específico:
```bash
python scripts/run_comprehensive_batch_tests.py --specific "test_nested_component_breakdown_with_batches"
```

### Solo tests de edge cases:
```bash
python -m pytest inventory/tests/test_edge_cases_batch_flows.py -v
```

### Solo tests de jerarquías complejas:
```bash
python -m pytest inventory/tests/test_comprehensive_batch_flows.py::TestComplexBatchHierarchies -v
```
"""
    
    # Guardar documentación
    doc_file = "docs/comprehensive_batch_testing.md"
    os.makedirs(os.path.dirname(doc_file), exist_ok=True)
    
    with open(doc_file, 'w', encoding='utf-8') as f:
        f.write(documentation)
    
    print_subsection_header("Documentación Generada")
    print(f"📖 Documentación guardada en: {doc_file}")

def main():
    """Función principal del script."""
    
    parser = argparse.ArgumentParser(
        description="Ejecuta tests comprehensivos de productos con lotes y componentes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python scripts/run_comprehensive_batch_tests.py
  python scripts/run_comprehensive_batch_tests.py --verbose --coverage
  python scripts/run_comprehensive_batch_tests.py --specific "test_fifo_with_multiple_batch_levels"
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Mostrar salida detallada de los tests'
    )
    
    parser.add_argument(
        '--coverage', '-c',
        action='store_true',
        help='Generar reporte de cobertura de código'
    )
    
    parser.add_argument(
        '--specific', '-s',
        type=str,
        help='Ejecutar solo un test específico'
    )
    
    parser.add_argument(
        '--docs-only',
        action='store_true',
        help='Solo generar documentación sin ejecutar tests'
    )
    
    args = parser.parse_args()
    
    if args.docs_only:
        generate_test_documentation()
        return
    
    # Ejecutar tests
    success = run_comprehensive_tests(
        verbose=args.verbose,
        coverage=args.coverage,
        specific_test=args.specific
    )
    
    # Generar documentación siempre
    generate_test_documentation()
    
    print_section_header("RESUMEN FINAL")
    
    if success:
        print("🎉 Tests comprehensivos completados exitosamente")
        print("\n📋 Escenarios verificados:")
        print("   ✅ Jerarquías complejas con lotes")
        print("   ✅ Algoritmos de prioridad FIFO")
        print("   ✅ Componentes compartidos")
        print("   ✅ Casos extremos y edge cases")
        print("   ✅ Validaciones de consistencia")
        print("   ✅ Operaciones de alto volumen")
        
        if args.coverage:
            print("\n📊 Reporte de cobertura disponible en htmlcov/index.html")
        
        print(f"\n📖 Documentación actualizada en docs/comprehensive_batch_testing.md")
        print(f"\n⏰ Completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        sys.exit(0)
    else:
        print("❌ Algunos tests fallaron - revisar salida anterior")
        print("\n🔧 Pasos sugeridos:")
        print("   1. Revisar errores específicos arriba")
        print("   2. Ejecutar test individual: --specific 'nombre_del_test'")
        print("   3. Verificar configuración de base de datos de test")
        
        sys.exit(1)

if __name__ == "__main__":
    main() 