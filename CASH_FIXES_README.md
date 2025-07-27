# Correcciones de Movimientos de Caja

## Problemas Corregidos

### 1. **Duplicación de Cantidades**

**Problema:** Cuando se creaba un movimiento de ingreso o egreso, las cantidades se duplicaban (se sumaban o restaban el doble).

**Causa:** El método `apply_to_cash_balance()` se llamaba tanto en el modelo (`save()`) como en el serializer (`create()`).

**Solución:** Eliminé la llamada duplicada en los serializers, dejando solo la del modelo.

### 2. **Comportamiento Incorrecto de Ajustes**

**Problema:** Los movimientos de tipo "ajuste" se trataban como sumas/restas en lugar de sustituir el valor de la caja.

**Causa:** En el método `apply_to_cash_balance()`, los ajustes usaban `+=` en lugar de `=`.

**Solución:** Modifiqué el método para que los ajustes sustituyan el valor de la caja directamente.

## Cambios Realizados

### Archivos Modificados:

1. **`cash/models.py`**

    - Corregido el método `save()` para manejar mejor los ajustes
    - Actualizado `apply_to_cash_balance()` para sustituir valores en ajustes
    - Mejorado el manejo de reversiones de ajustes

2. **`cash/serializers.py`**
    - Eliminadas las llamadas duplicadas a `apply_to_cash_balance()` en los métodos `create()`

## Cómo Probar las Correcciones

### Opción 1: Script de Prueba Directa (Recomendado)

```bash
cd unidental-backend
python test_cash_movements.py
```

Este script prueba:

-   ✅ Ingresos sin duplicación
-   ✅ Egresos sin duplicación
-   ✅ Ajustes que sustituyen el valor
-   ✅ Actualizaciones de movimientos

### Opción 2: Prueba de Endpoints API

```bash
# 1. Iniciar el servidor
cd unidental-backend
python manage.py runserver 0.0.0.0:8000

# 2. En otra terminal, ejecutar las pruebas de API
python test_cash_endpoints.py
```

### Opción 3: Prueba Manual

1. **Crear un ingreso de $1000:**

    ```bash
    curl -X POST http://localhost:8000/api/cash/movements/ \
      -H "Authorization: Token YOUR_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "cash": 1,
        "movement_type": "ingreso",
        "amount": "1000.00",
        "reference_type": "ajuste_manual",
        "notes": "Prueba de ingreso"
      }'
    ```

2. **Verificar el saldo:**

    ```bash
    curl http://localhost:8000/api/cash/cashes/1/ \
      -H "Authorization: Token YOUR_TOKEN"
    ```

3. **Crear un ajuste a $500:**
    ```bash
    curl -X POST http://localhost:8000/api/cash/movements/ \
      -H "Authorization: Token YOUR_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "cash": 1,
        "movement_type": "ajuste",
        "amount": "500.00",
        "reference_type": "ajuste_manual",
        "notes": "Prueba de ajuste"
      }'
    ```

## Resultados Esperados

### Antes de las correcciones:

-   Ingreso de $1000 → Saldo: $2000 (duplicado)
-   Egreso de $300 → Saldo: $1400 (duplicado)
-   Ajuste a $500 → Saldo: $1000 (sumado en lugar de sustituido)

### Después de las correcciones:

-   Ingreso de $1000 → Saldo: $1000 ✅
-   Egreso de $300 → Saldo: $700 ✅
-   Ajuste a $500 → Saldo: $500 ✅

## Endpoints Disponibles

### Cajas

-   `GET /api/cash/cashes/` - Listar cajas
-   `POST /api/cash/cashes/` - Crear caja
-   `GET /api/cash/cashes/{id}/` - Obtener caja específica
-   `GET /api/cash/cashes/summary/` - Resumen de todas las cajas

### Movimientos

-   `GET /api/cash/movements/` - Listar movimientos
-   `POST /api/cash/movements/` - Crear movimiento
-   `GET /api/cash/movements/{id}/` - Obtener movimiento específico
-   `POST /api/cash/movements/{id}/cancel/` - Anular movimiento
-   `POST /api/cash/movements/{id}/reactivate/` - Reactivar movimiento

### Transferencias

-   `GET /api/cash/transfers/` - Listar transferencias
-   `POST /api/cash/transfers/` - Crear transferencia
-   `POST /api/cash/transfers/{id}/execute/` - Ejecutar transferencia
-   `POST /api/cash/transfers/{id}/cancel/` - Cancelar transferencia

## Notas Importantes

1. **Permisos:** Todos los endpoints requieren autenticación y permisos de administrador.

2. **Ajustes:** Los movimientos de tipo "ajuste" ahora sustituyen el valor de la caja en lugar de sumar/restar.

3. **Reversiones:** Los ajustes no se pueden revertir automáticamente si no se tiene el valor anterior guardado.

4. **Validaciones:** Se mantienen todas las validaciones existentes (saldo suficiente para egresos, etc.).

## Limpieza de Datos (Opcional)

Si tienes datos corruptos por la duplicación anterior, puedes limpiarlos ejecutando:

```python
# En el shell de Django
python manage.py shell

from cash.models import Cashes, Movements
from decimal import Decimal

# Recalcular saldos de todas las cajas
for cash in Cashes.objects.all():
    # Calcular saldo real basado en movimientos activos
    total_ingresos = cash.movements.filter(
        movement_type='ingreso',
        status='active'
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    total_egresos = cash.movements.filter(
        movement_type='egreso',
        status='active'
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    # Obtener el último ajuste activo
    ultimo_ajuste = cash.movements.filter(
        movement_type='ajuste',
        status='active'
    ).order_by('-created_at').first()

    if ultimo_ajuste:
        # Si hay ajuste, usar ese valor
        cash.balance = ultimo_ajuste.amount
    else:
        # Si no hay ajuste, calcular: ingresos - egresos
        cash.balance = total_ingresos - total_egresos

    cash.save()
    print(f"Caja {cash.location.name}: ${cash.balance:,.2f}")
```
