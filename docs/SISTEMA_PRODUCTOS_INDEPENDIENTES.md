# Sistema de Productos Independientes con Conversiones Manuales

## Descripción General

El sistema ha sido rediseñado para manejar todos los productos como **productos independientes**, eliminando las conversiones automáticas y reemplazándolas con un sistema de **conversiones manuales** controlado por el usuario.

### Ventajas del Nuevo Sistema

✅ **Simplicidad**: Cada producto tiene su propio stock independiente  
✅ **Transparencia**: No hay conversiones automáticas misteriosas  
✅ **Control**: El usuario decide cuándo y cómo convertir productos  
✅ **Auditoría**: Todas las conversiones quedan registradas  
✅ **Flexibilidad**: Soporte completo para lotes y stock mixto  

---

## Componentes del Sistema

### 1. Modelo ProductConversion

Define las reglas de conversión entre productos:

```python
class ProductConversion:
    from_product: Product      # Producto origen (ej: Caja)
    to_product: Product        # Producto destino (ej: Blisters)
    conversion_rate: int       # Factor de conversión (ej: 5 blisters por caja)
    is_reversible: bool        # Si se puede hacer conversión inversa
```

### 2. API Endpoints

#### Gestión de Conversiones
- `GET /api/catalogs/product-conversions/` - Listar conversiones
- `POST /api/catalogs/product-conversions/` - Crear conversión
- `GET /api/catalogs/product-conversions/possible-from/?product=X&location=Y` - Conversiones desde un producto
- `GET /api/catalogs/product-conversions/possible-to/?product=X&location=Y` - Conversiones hacia un producto

#### Ejecución de Conversiones
- `POST /api/catalogs/conversions/execute/` - Ejecutar conversión manual
- `POST /api/catalogs/conversions/suggest/` - Obtener sugerencias de conversión

---

## Flujo de Trabajo

### 1. Configuración Inicial

Ejecutar el comando de migración para convertir productos compuestos existentes:

```bash
# Ver qué cambios se harían (modo dry-run)
python manage.py setup_independent_products --dry-run

# Ejecutar los cambios reales
python manage.py setup_independent_products
```

Este comando:
1. Crea conversiones automáticas basadas en productos compuestos existentes
2. Convierte todos los productos a tipo `'simple'`

### 2. Gestión de Stock

Cada producto mantiene su stock independiente:

```python
# Stock independiente de cada producto
Caja Ibuprofeno: 10 cajas
Blister Ibuprofeno: 25 blisters  
Pastilla Ibuprofeno: 150 pastillas
```

**Stock disponible total para venta:**
- Pastillas: 150 + (25×10) + (10×5×10) = **900 pastillas**
- Blisters: 25 + (10×5) = **75 blisters**  
- Cajas: **10 cajas**

### 3. Proceso de Venta

#### Caso 1: Stock Suficiente
Venta normal sin conversiones necesarias.

#### Caso 2: Stock Insuficiente
El sistema responde con sugerencias de conversión:

```json
{
  "error": {
    "product": "Blister Ibuprofeno",
    "available": 25,
    "required": 30,
    "deficit": 5,
    "suggestions": [
      {
        "conversion_id": 1,
        "from_product": {
          "id": 1,
          "name": "Caja Ibuprofeno",
          "sku": "IBU-CAJ-001"
        },
        "to_product": {
          "id": 2, 
          "name": "Blister Ibuprofeno",
          "sku": "IBU-BLI-001"
        },
        "conversion_rate": 5,
        "available_stock": 10,
        "can_provide": 50,
        "units_needed": 1,
        "would_convert_to": 5
      }
    ],
    "message": "Stock insuficiente del producto Blister Ibuprofeno en Sede Central."
  }
}
```

### 4. Conversión Manual

El usuario debe ejecutar la conversión explícitamente:

```bash
curl -X POST /api/catalogs/conversions/execute/ \
  -H "Content-Type: application/json" \
  -d '{
    "conversion_id": 1,
    "quantity_to_convert": 1,
    "location_id": 1,
    "notes": "Abriendo caja para completar venta"
  }'
```

**Resultado:**
- Caja Ibuprofeno: 10 → 9 (-1)
- Blister Ibuprofeno: 25 → 30 (+5)

### 5. Completar la Venta

Ahora que hay stock suficiente, se puede completar la venta original.

---

## Ejemplos de Uso

### Ejemplo 1: Conversión Simple

**Configuración:**
- 1 Caja = 5 Blisters
- Stock: 3 cajas, 2 blisters
- Necesidad: 8 blisters

**Proceso:**
1. Stock actual de blisters: 2
2. Déficit: 8 - 2 = 6 blisters
3. Conversión sugerida: 2 cajas → 10 blisters
4. Usuario ejecuta: convertir 2 cajas
5. Resultado: 1 caja, 12 blisters
6. Venta de 8 blisters completada

### Ejemplo 2: Conversión con Lotes

**Configuración:**
- Producto con control de lotes
- Caja Lote A: 5 cajas
- Blister Lote A: 10 blisters

**Conversión:**
```json
{
  "conversion_id": 1,
  "quantity_to_convert": 2,
  "location_id": 1, 
  "batch_id": 5,
  "notes": "Conversión con lote específico"
}
```

**Validaciones:**
- El lote debe pertenecer al producto origen
- Debe haber stock suficiente del lote específico
- La conversión mantiene el mismo lote en el producto destino

### Ejemplo 3: Conversión en Cadena

**Jerarquía:**
- Caja de Cajas → Cajas → Blisters → Pastillas

**Configuración:**
- 1 Caja de Cajas = 6 Cajas
- 1 Caja = 5 Blisters  
- 1 Blister = 10 Pastillas

**Para obtener 100 pastillas:**
1. **Opción A:** Convertir 1 Caja de Cajas → 6 Cajas → 30 Blisters → 300 Pastillas
2. **Opción B:** Convertir 2 Cajas → 10 Blisters → 100 Pastillas  
3. **Opción C:** Convertir 10 Blisters → 100 Pastillas

El sistema sugiere las opciones más eficientes.

---

## API Reference

### Crear Conversión

```http
POST /api/catalogs/product-conversions/
```

```json
{
  "from_product": 1,
  "to_product": 2,
  "conversion_rate": 5,
  "is_reversible": false
}
```

### Ejecutar Conversión

```http
POST /api/catalogs/conversions/execute/
```

```json
{
  "conversion_id": 1,
  "quantity_to_convert": 2,
  "location_id": 1,
  "batch_id": 3,
  "notes": "Conversión manual para venta"
}
```

### Obtener Sugerencias

```http
POST /api/catalogs/conversions/suggest/
```

```json
{
  "product_id": 2,
  "location_id": 1, 
  "required_quantity": 15
}
```

**Respuesta:**
```json
{
  "current_stock": 10,
  "required_quantity": 15,
  "deficit": 5,
  "suggestions": [
    {
      "conversion": {...},
      "available_stock": 3,
      "can_provide": 15,
      "units_needed": 1,
      "would_convert_to": 5
    }
  ]
}
```

---

## Migración desde Sistema Anterior

### Paso 1: Backup
```bash
python manage.py dumpdata catalogs.Product > products_backup.json
python manage.py dumpdata inventory.InventoryStock > stock_backup.json
```

### Paso 2: Migrar
```bash
python manage.py setup_independent_products --dry-run  # Revisar cambios
python manage.py setup_independent_products            # Ejecutar
```

### Paso 3: Validar
- Verificar que todas las conversiones se crearon correctamente
- Confirmar que todos los productos son tipo `'simple'`
- Validar que el stock se mantiene consistente

### Paso 4: Actualizar Frontend
- Remover lógica de `confirm_breakdown`
- Implementar manejo de sugerencias de conversión
- Agregar UI para ejecutar conversiones manuales

---

## Consideraciones de Rendimiento

### Índices Recomendados
```sql
CREATE INDEX idx_conversion_from_product ON catalogs_productconversion(from_product_id);
CREATE INDEX idx_conversion_to_product ON catalogs_productconversion(to_product_id);
CREATE INDEX idx_movement_conversion ON inventory_inventorymovement(is_conversion);
```

### Optimizaciones
- Las sugerencias de conversión se calculan en tiempo real
- Usar cache para conversiones frecuentes
- Considerar pre-calcular opciones para productos críticos

---

## Troubleshooting

### Problema: "No hay conversiones disponibles"
**Causa:** No se han configurado conversiones entre productos  
**Solución:** Crear conversiones manualmente o ejecutar `setup_independent_products`

### Problema: "Lote no válido para conversión"
**Causa:** El lote especificado no pertenece al producto origen  
**Solución:** Verificar que el lote corresponde al producto correcto

### Problema: "Stock inconsistente después de conversión"
**Causa:** Error en la ejecución de la conversión  
**Solución:** Revisar logs de `InventoryMovement` con `is_conversion=True`

### Problema: "Conversión circular detectada"
**Causa:** Se configuró una cadena de conversiones que forma un ciclo  
**Solución:** Revisar y corregir las relaciones de conversión

---

## Roadmap Futuro

### Funcionalidades Planeadas
- [ ] Conversiones automáticas programadas
- [ ] Optimización de sugerencias con ML
- [ ] Dashboard de análisis de conversiones
- [ ] API GraphQL para consultas complejas
- [ ] Integración con sistema de compras para re-stock inteligente

### Mejoras Consideradas
- [ ] Conversiones parciales con fracciones
- [ ] Historial de conversiones por usuario
- [ ] Alertas automáticas de stock bajo con sugerencias
- [ ] Integración con sistema de costos para tracking de conversiones

---

## 🎨 GUÍA PARA FRONTEND DEVELOPER

### 🔄 **Cambios Principales en la UI**

#### ❌ **REMOVER (Sistema Anterior):**
```javascript
// Ya NO usar
confirm_breakdown: true/false  // Campo eliminado
```

#### ✅ **AGREGAR (Sistema Nuevo):**

### 1. **Manejo de Errores de Stock**

**Antes:** Error simple
```javascript
// Respuesta antigua
{
  "error": "Stock insuficiente"
}
```

**Ahora:** Error con sugerencias
```javascript
// Nueva respuesta con sugerencias
{
  "error": {
    "product": "Blister Ibuprofeno",
    "available": 25,
    "required": 30,
    "deficit": 5,
    "suggestions": [
      {
        "conversion_id": 1,
        "from_product": {
          "id": 1,
          "name": "Caja Ibuprofeno",
          "sku": "IBU-CAJ-001"
        },
        "to_product": {
          "id": 2,
          "name": "Blister Ibuprofeno", 
          "sku": "IBU-BLI-001"
        },
        "conversion_rate": 5,
        "available_stock": 10,
        "can_provide": 50,
        "units_needed": 1,
        "would_convert_to": 5
      }
    ],
    "message": "Stock insuficiente del producto Blister Ibuprofeno en Sede Central."
  }
}
```

### 2. **Componente de Sugerencias de Conversión**

```jsx
function ConversionSuggestions({ suggestions, onExecute }) {
  return (
    <div className="conversion-suggestions">
      <h3>💡 Sugerencias de Conversión</h3>
      <p>No hay suficiente stock. ¿Quieres abrir productos para obtener más?</p>
      
      {suggestions.map(suggestion => (
        <div key={suggestion.conversion_id} className="suggestion-card">
          <div className="conversion-info">
            <strong>Abrir {suggestion.units_needed}x {suggestion.from_product.name}</strong>
            <span>→ Obtienes {suggestion.would_convert_to}x {suggestion.to_product.name}</span>
          </div>
          
          <div className="stock-info">
            <span>Disponible: {suggestion.available_stock}</span>
            <span>Puede dar: {suggestion.can_provide} unidades</span>
          </div>
          
          <button 
            onClick={() => onExecute(suggestion)}
            className="btn-primary"
          >
            Abrir {suggestion.units_needed} {suggestion.from_product.name}
          </button>
        </div>
      ))}
    </div>
  );
}
```

### 3. **Función para Ejecutar Conversión**

```javascript
async function executeConversion(suggestion, locationId, notes = "") {
  try {
    const response = await fetch('/api/catalogs/conversions/execute/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        conversion_id: suggestion.conversion_id,
        quantity_to_convert: suggestion.units_needed,
        location_id: locationId,
        notes: notes || `Conversión manual para venta`
      })
    });
    
    if (response.ok) {
      const result = await response.json();
      console.log('Conversión exitosa:', result.message);
      return result;
    } else {
      throw new Error('Error en conversión');
    }
  } catch (error) {
    console.error('Error ejecutando conversión:', error);
    throw error;
  }
}
```

### 4. **Flujo de Venta Actualizado**

```javascript
async function processSale(saleData) {
  try {
    // 1. Intentar crear venta
    const response = await createSale(saleData);
    
    if (response.ok) {
      // ✅ Venta exitosa
      return await response.json();
    }
    
    // 2. Si hay error de stock, manejar sugerencias
    const errorData = await response.json();
    
    if (errorData.error && errorData.error.suggestions) {
      // 🔄 Mostrar sugerencias de conversión
      const shouldConvert = await showConversionDialog(errorData.error);
      
      if (shouldConvert) {
        // 3. Ejecutar conversión seleccionada
        await executeConversion(shouldConvert, saleData.location_id);
        
        // 4. Reintentar venta
        return await processSale(saleData);
      }
    }
    
    throw new Error(errorData.message || 'Error en venta');
    
  } catch (error) {
    console.error('Error procesando venta:', error);
    throw error;
  }
}
```

### 5. **Modal/Dialog de Conversión**

```jsx
function ConversionDialog({ error, onConfirm, onCancel }) {
  const [selectedSuggestion, setSelectedSuggestion] = useState(null);
  
  return (
    <div className="modal-overlay">
      <div className="conversion-modal">
        <h2>🚨 Stock Insuficiente</h2>
        <p>{error.message}</p>
        
        <div className="stock-summary">
          <span>Disponible: {error.available}</span>
          <span>Necesario: {error.required}</span>
          <span>Falta: {error.deficit}</span>
        </div>
        
        <ConversionSuggestions 
          suggestions={error.suggestions}
          onExecute={setSelectedSuggestion}
        />
        
        <div className="modal-actions">
          <button onClick={onCancel} className="btn-secondary">
            Cancelar Venta
          </button>
          <button 
            onClick={() => onConfirm(selectedSuggestion)}
            disabled={!selectedSuggestion}
            className="btn-primary"
          >
            Confirmar Conversión
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 6. **Estados de Loading**

```jsx
function SaleForm() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [conversionError, setConversionError] = useState(null);
  
  const handleSubmit = async (saleData) => {
    setIsProcessing(true);
    setConversionError(null);
    
    try {
      await processSale(saleData);
      // ✅ Venta exitosa
      onSaleSuccess();
    } catch (error) {
      if (error.suggestions) {
        setConversionError(error);
      } else {
        showErrorMessage(error.message);
      }
    } finally {
      setIsProcessing(false);
    }
  };
  
  return (
    <div>
      {/* Formulario de venta */}
      
      {conversionError && (
        <ConversionDialog 
          error={conversionError}
          onConfirm={handleConversion}
          onCancel={() => setConversionError(null)}
        />
      )}
      
      {isProcessing && <LoadingSpinner />}
    </div>
  );
}
```

### 7. **Gestión de Conversiones (Admin)**

```jsx
function ConversionsManager() {
  const [conversions, setConversions] = useState([]);
  
  useEffect(() => {
    // Cargar conversiones existentes
    fetch('/api/catalogs/product-conversions/')
      .then(res => res.json())
      .then(setConversions);
  }, []);
  
  return (
    <div className="conversions-manager">
      <h2>⚙️ Gestión de Conversiones</h2>
      
      <table>
        <thead>
          <tr>
            <th>Producto Origen</th>
            <th>Producto Destino</th>
            <th>Factor</th>
            <th>Reversible</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {conversions.map(conv => (
            <tr key={conv.id}>
              <td>{conv.from_product_name}</td>
              <td>{conv.to_product_name}</td>
              <td>1 → {conv.conversion_rate}</td>
              <td>{conv.is_reversible ? '✅' : '❌'}</td>
              <td>
                <button onClick={() => editConversion(conv)}>
                  Editar
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### 📱 **UX/UI Recomendaciones**

1. **Colores:**
   - 🔴 Rojo para stock insuficiente
   - 🟡 Amarillo para sugerencias
   - 🟢 Verde para conversión exitosa

2. **Iconos:**
   - 📦 Cajas/productos origen
   - ➡️ Flecha de conversión  
   - 📋 Productos destino
   - ⚡ Conversión rápida

3. **Mensajes:**
   - "¿Abrir 2 cajas para obtener 10 blisters?"
   - "Conversión exitosa: +10 blisters disponibles"
   - "Stock actualizado, puedes completar la venta"

### 🎯 **Testing Frontend**

```javascript
// Test del flujo completo
describe('Conversion Flow', () => {
  it('should handle insufficient stock with suggestions', async () => {
    // 1. Simular venta con stock insuficiente
    // 2. Verificar que aparezcan sugerencias
    // 3. Simular ejecución de conversión
    // 4. Verificar que se complete la venta
  });
});
```

### ⚡ **Resumen para Frontend**

**QUÉ HACER:**
1. ❌ Remover campo `confirm_breakdown` 
2. ✅ Agregar manejo de sugerencias de conversión
3. ✅ Crear componente de modal/dialog para conversiones
4. ✅ Implementar flujo: Error → Sugerencia → Ejecución → Retry
5. ✅ Agregar UI de gestión de conversiones (opcional)

**ENDPOINTS A USAR:**
- `POST /api/sales/sales/` (sin `confirm_breakdown`)
- `POST /api/catalogs/conversions/execute/`
- `GET /api/catalogs/product-conversions/`

¡Ahora sí está **100% completo** para el frontend! 🎉 