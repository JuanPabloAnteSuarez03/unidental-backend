# UNIDENTAL — Backend

[English](README.md) · **Español**

API REST de UNIDENTAL, distribuidora de insumos dentales que opera desde dos sedes en Cali, Colombia. Construida con Django 5.2 y Django REST Framework.

Cubre el catálogo de productos (SKUs y lotes), inventario por sede, ventas y devoluciones, compras y proveedores, cuentas por cobrar y por pagar, entregas y manejo de caja.

🔗 **Documentación de la API en vivo:** [Swagger](https://unidental-backend.onrender.com/swagger/) · [Redoc](https://unidental-backend.onrender.com/redoc/)
🔗 **Frontend:** [unidental-frontend](https://github.com/JuanPabloAnteSuarez03/unidental-frontend)

---

## Por qué existe

El inventario de la empresa no estaba sistematizado: no existía una base de datos real, solo hojas de cálculo de Google Sheets sin relación entre productos, lotes y sedes. Cualquier pregunta — cuánto stock queda, en qué sede, de qué lote — dependía de revisar y cruzar esas hojas a mano.

Además son productos con fecha de vencimiento. Sin un sistema que modelara la relación entre productos, lotes y sedes, qué lote despachar quedaba a la memoria del personal, y el costo de un error aparecía tarde, en forma de producto vencido.

**Por qué Django y DRF en lugar de Node:** el dominio es fuertemente relacional — productos, lotes, sedes, movimientos y créditos se referencian entre sí y necesitan integridad transaccional.

---

## Stack

| Aspecto | Tecnología |
|---|---|
| Framework | Django 5.2, Django REST Framework |
| Autenticación | Djoser + token de DRF |
| Documentación de API | drf-yasg (Swagger / Redoc) |
| Filtros | django-filter |
| CORS | django-cors-headers |
| Archivos estáticos | WhiteNoise |
| Base de datos | PostgreSQL (dev/prod) · SQLite (tests) |
| Hosting | Render (también configurado para Railway) |

---

## Apps

| App | Responsabilidad |
|---|---|
| `core` | Utilidades, health check, correo (Djoser), permisos |
| `catalogs` | Productos, categorías, sistema SKU (categoría/subcategoría/tipo), lotes (`ProductBatch`), kits y componentes, conversiones manuales |
| `inventory` | Sedes y bodegas, stock por sede + lote, movimientos con actualización automática de stock (entradas, salidas, traslados, conversión compuesta) |
| `sales` | Clientes, ventas e items, devoluciones e items, señales que ajustan el inventario |
| `suppliers` | Proveedores y `PurchaseOption` (marca, precio, vigencia) |
| `purchases` | Órdenes de compra e items |
| `credits` | Cuentas por cobrar (ventas) y por pagar (compras), pagos, recordatorios por WhatsApp |
| `deliveries` | Entregas, estados y estadísticas |
| `cash` | Caja por sede, movimientos (ingreso/egreso/ajuste) y transferencias |

---

## Puesta en marcha

```bash
# 1) Crear y activar el entorno virtual
python -m venv env
source env/bin/activate        # Windows: env\Scripts\activate

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Configurar el entorno (.env) — ver abajo

# 4) Correr migraciones
python manage.py migrate

# 5) Levantar el servidor
python manage.py runserver
```

Y abrir http://127.0.0.1:8000/swagger/.

---

## Variables de entorno

| Variable | Notas |
|---|---|
| `SECRET_KEY` | Obligatoria |
| `DEBUG` | `True` / `False` |
| `ALLOWED_HOSTS` | ej. `127.0.0.1,localhost` |
| `CSRF_TRUSTED_ORIGINS` | ej. `https://mi-dominio.app` |
| `DATABASE_URL` | Cadena de conexión de PostgreSQL |
| `USE_SQLITE_FOR_TESTS` | `True` para correr la suite sobre SQLite en memoria |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL` | Correo en producción |

---

## Autenticación

Los endpoints de Djoser viven bajo `/api/auth/`.

```http
POST /api/auth/token/login/      → devuelve un token
Authorization: Token <token>     → enviarlo en cada petición autenticada
```

---

## Importar los datos del cliente

Hay comandos de management que pueblan la base desde los CSV exportados de las hojas de cálculo originales del cliente, versionados en el repositorio.

```bash
# Orquestador todo-en-uno
python manage.py import_all
```

Ejecuta, en este orden:

1. `populate_database_fast "UNIDENTAL - COMPRAS E INV (1).csv" --clear-data` — productos, SKUs, lotes, stock, opciones de compra y órdenes
2. `populate_suppliers --file "UNIDENTAL (1) - PROVEEDORES 2024.csv"` — proveedores (sin `--clean`, para preservar `PurchaseOption`)
3. `populate_customers --file "UNIDENTAL (1) - BASE DATOS  .csv" --clean` — clientes

Los comandos individuales aceptan `--clear-data`, `--dry-run` y `--orders-only`.

> **Notas**
> - Los lotes solo se crean si la fecha de vencimiento se puede parsear; si no, el producto queda sin control de lotes.
> - `InventoryStock` se crea con los valores de las columnas de inventario por sede; si son `0` o están vacías, no queda stock asociado aunque existan lotes.
> - Usar `populate_suppliers --clean` con cuidado — hace CASCADE sobre `PurchaseOption`.

---

## Referencia de la API

Documentación interactiva: `/swagger/`, `/redoc/`, esquema crudo en `/swagger.json` o `/swagger.yaml`.

La paginación es `PageNumberPagination` de DRF con `PAGE_SIZE=25`; los filtros vienen de `django-filter`; la búsqueda de texto va por `?search=`.

<details>
<summary><strong>Endpoints destacados por dominio</strong></summary>

**Catálogo** — `/api/catalogs/`
- Productos: `/products/`, sin paginar `/products/all/`
- Productos por sede: `GET /products/by-location/?location=<id>&has_stock=true|false&search=...`
- Componentes de kits: `/product-components/` · Lotes: `/product-batches/`
- Conversiones manuales: `/product-conversions/`, `/conversions/execute/`, `/conversions/suggest/`
- Sistema SKU: `/sku-categories/`, `/sku-subcategories/`, `/sku-types/`, `/sku/info/`, `/sku/generate/`, `/sku/validate/`

**Inventario** — `/api/inventory/`
- Sedes: `/locations/`
- Stock: `/stock/`, `/stock/summary/`, `/stock/all/`
- Stock por lotes (FIFO): `/stock/by_batches/`
- Lotes de un producto en todas las sedes: `/stock/product_batches_stock/?product=...`
- Lotes en una sede: `/stock/location_batch_stock/?location=...`
- Movimientos: `/movements/` (+ `complete`, `cancel`), alertas de nivel de stock y de vencimiento

**Ventas** — `/api/sales/`
- Clientes `/customers/` · Ventas `/sales/`, `/sale-items/` · Devoluciones `/returns/`, `/return-items/`
- Estadísticas por período y por sede

**Compras y proveedores**
- `/api/suppliers/suppliers/` · `/api/suppliers/purchase-options/`
- `/api/purchases/orders/` · `/api/purchases/items/`

**Créditos** — `/api/credits/`
- Por cobrar `/accounts/`, `/payments/` · Por pagar `/purchase-accounts/`, `/purchase-payments/`
- Estadísticas, resúmenes y URLs de recordatorio por WhatsApp

**Entregas** — `/api/deliveries/`
- CRUD más `update_status`, `mark_shipped`, `mark_delivered`; estadísticas por sede

**Caja** — `/api/cash/`
- Cajas `/cashes/` (+ `summary`) · Movimientos `/movements/` (+ `cancel`, `reactivate`) · Transferencias `/transfers/` (+ `execute`, `cancel`)

**Core**
- Health check: `/api/core/health-check/` — verifica base de datos y caché

</details>

---

## Testing

```bash
pytest -q
```

Las pruebas corren sobre SQLite en memoria (`USE_SQLITE_FOR_TESTS=True`). Cada app tiene su propia carpeta `tests/`.

---

## Despliegue

Desplegado en Render (`render.yaml`; también está `railway.json` para Railway).

- Definir `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y las variables de correo
- `collectstatic` lo maneja WhiteNoise
- Ver `RAILWAY_PERFORMANCE_TROUBLESHOOTING.md` para notas de rendimiento

---

## Notas de negocio

- Los productos se modelan como **items independientes con conversiones manuales** — no hay desarmado automático de kits durante una venta.
- La selección de lote es **FIFO** por defecto (primero el más próximo a vencer), con **override manual**: el mostrador necesita romper esa regla cuando el cliente pide un lote específico. Automatizar sin dejar salida habría hecho que el personal buscara la forma de esquivar el sistema.
- La documentación funcional ampliada está en `docs/`.

---

## Sobre el proyecto

Desarrollado por [Juan Pablo Ante Suárez](https://github.com/JuanPabloAnteSuarez03). Hice el backend completo; el frontend en React lo implementamos en gran parte junto a un compañero, sobre esta API.

📖 **Caso de estudio completo:** [juanpabloante.vercel.app/es/projects/unidental](https://juanpabloante.vercel.app/es/projects/unidental)

---

Privado · © UNIDENTAL. Todos los derechos reservados.
