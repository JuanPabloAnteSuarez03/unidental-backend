
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
