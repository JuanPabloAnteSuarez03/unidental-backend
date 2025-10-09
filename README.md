# UNIDENTAL Backend

Backend de gestión para UNIDENTAL construido con Django 5.2 y Django REST Framework. Cubre catálogo de productos (con SKUs y lotes), inventario por sedes, ventas y devoluciones, compras y proveedores, créditos (CxC y CxP), domicilios, caja (movimientos y transferencias), autenticación y documentación de API.

## Tabla de contenidos
- Stack y arquitectura
- Estructura de apps
- Puesta en marcha (Quick Start)
- Variables de entorno
- Desarrollo local
- Importación de datos (CSV y comandos)
- Autenticación
- Documentación de API (Swagger/Redoc)
- Paginación, filtros y búsqueda
- Endpoints destacados por dominio
- Testing
- Despliegue (Railway/Render)

---

## Stack y arquitectura
- Django 5.2, Django REST Framework (DRF)
- Autenticación vía Djoser + Token (rest_framework.authtoken)
- Documentación interactiva: drf-yasg (Swagger/Redoc)
- CORS: django-cors-headers
- Filtros: django-filter
- Servido de estáticos: WhiteNoise
- Base de datos: PostgreSQL (prod/dev), SQLite en tests

## Estructura de apps
- `core`: utilidades, health check, email (Djoser), permisos
- `catalogs`: productos, categorías, sistema SKU (categoría/subcategoría/tipo), lotes (ProductBatch), kits/componentes, conversiones manuales
- `inventory`: sedes/bodegas (`Location`), stock por sede+lote, movimientos con actualización automática de stock (entradas/salidas/transferencias/conversión compuestos)
- `sales`: clientes, ventas (items), devoluciones (items), señales que ajustan inventario
- `suppliers`: proveedores y `PurchaseOption` (marca/precio/validez)
- `purchases`: órdenes de compra e items
- `credits`: créditos de ventas (CxC) y compras (CxP), pagos, recordatorios/WhatsApp
- `deliveries`: entregas/domicilios, estados y estadísticas
- `cash`: caja por sede, movimientos (ingreso/egreso/ajuste) y transferencias

## Puesta en marcha (Quick Start)
```bash
# 1) Crear y activar entorno
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Configurar variables de entorno (.env)
#   SECRET_KEY, DEBUG, DATABASE_URL, etc. (ver sección Variables de entorno)

# 4) Migraciones
python manage.py migrate

# 5) Ejecutar servidor
python manage.py runserver

# 6) Documentación de API
# Swagger: http://127.0.0.1:8000/swagger/
# Redoc:   http://127.0.0.1:8000/redoc/
```

## Variables de entorno
Mínimas recomendadas en `.env` (o variables del entorno):
- `SECRET_KEY`
- `DEBUG` (True/False)
- `ALLOWED_HOSTS` (ej: `127.0.0.1,localhost`)
- `CSRF_TRUSTED_ORIGINS` (ej: `https://mi-dominio.app`)
- `DATABASE_URL` (PostgreSQL en dev/prod; tests usan SQLite en memoria con `USE_SQLITE_FOR_TESTS=True`)
- Email (prod): `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL`


## Desarrollo local
- Autenticación por Token (Djoser). Añadir header: `Authorization: Token <token>`
- CORS habilitado para dominios de frontend configurados en settings
- Archivo `unidental/settings.py` contiene configuración para Railway/Render en prod

## Importación de datos (CSV y comandos)
Hay comandos de management para poblar la base desde los CSV incluidos en el repo(base de datos interna del cliente):

1) Orquestador todo-en-uno (no borra proveedores para preservar `PurchaseOption` después del flujo):
```bash
python manage.py import_all
```
Internamente ejecuta, en este orden:
- `populate_database_fast "UNIDENTAL - COMPRAS E INV (1).csv" --clear-data` (productos, SKUs, lotes, stock, opciones de compra, órdenes)
- `populate_suppliers --file "UNIDENTAL (1) - PROVEEDORES 2024.csv"` (crea/actualiza proveedores, sin `--clean`)
- `populate_customers --file "UNIDENTAL (1) - BASE DATOS  .csv" --clean` (clientes)

2) Comando rápido y parametrizable (acepta `--clear-data`, `--dry-run`, `--orders-only`):
```bash
python manage.py populate_database_fast "UNIDENTAL - COMPRAS E INV (1).csv"
```
- Crea `Product`, `ProductBatch` (si la fecha de vencimiento es válida), `InventoryStock` por sede (si columnas de inventario tienen valores), `PurchaseOption`, `PurchaseOrder`/items.
- `--orders-only`: genera solo órdenes/items a partir de `PurchaseOption` existentes.

3) Proveedores:
```bash
python manage.py populate_suppliers --file "UNIDENTAL (1) - PROVEEDORES 2024.csv"
# Usar --clean solo si quieres eliminar todos los proveedores existentes (ojo: CASCADE sobre PurchaseOption)
```

4) Clientes:
```bash
python manage.py populate_customers --file "UNIDENTAL (1) - BASE DATOS  .csv" --clean
```

Notas:
- El import crea lotes SOLO si la fecha de vencimiento se puede parsear; si no, el producto queda sin control de lotes.
- `InventoryStock` se crea con los valores de inventario por sede del CSV; si son 0/vacío, no habrá stock asociado (aunque existan lotes).

## Autenticación
Endpoints Djoser disponibles en `/api/auth/`.
- Obtener token: `POST /api/auth/token/login/` (Djoser + authtoken)
- Incluir el token en `Authorization: Token <token>` para todas las llamadas autenticadas.

## Documentación de API
- Swagger UI: `/swagger/`
- Redoc: `/redoc/`
- Esquema JSON/YAML: `/swagger.json` o `/swagger.yaml`

## Paginación, filtros y búsqueda
- Paginación por defecto DRF (PageNumberPagination), `PAGE_SIZE=25`
- Filtros: `django-filter` (ver parámetros en Swagger)
- Búsqueda (cuando aplica): `search=texto`

## Endpoints destacados por dominio

### Catálogo (`/api/catalogs/`)
- Productos CRUD: `/products/`
- Productos (todos, sin paginar): `/products/all/`
- NUEVO: Productos por sede (paginado):
  - `GET /products/by-location/?location=<id>&has_stock=true|false&search=...`
  - Devuelve productos con registros de inventario en esa `location` (si `has_stock=true`, con `quantity>0`).
- Componentes de kits: `/product-components/`
- Lotes: `/product-batches/`
- Conversiones manuales: `/product-conversions/`, ejecutar `/conversions/execute/`, sugerir `/conversions/suggest/`
- Sistema SKU: `/sku-categories/`, `/sku-subcategories/`, `/sku-types/`, info `/sku/info/`, generar `/sku/generate/`, validar `/sku/validate/`

### Inventario (`/api/inventory/`)
- Sedes: `/locations/`
- Stock (CRUD y listados): `/stock/`, resumen `/stock/summary/`, completo `/stock/all/`
- Stock por lotes (FIFO): `/stock/by_batches/`
- Lotes de un producto con stock por sedes: `/stock/product_batches_stock/?product=...`
- Lotes en una sede: `/stock/location_batch_stock/?location=...`
- Movimientos (actualización automática de stock): `/movements/` (+ `complete`/`cancel`), alertas de stock y vencimientos

### Ventas (`/api/sales/`)
- Clientes: `/customers/`
- Ventas y items: `/sales/`, `/sale-items/`
- Devoluciones e items: `/returns/`, `/return-items/`
- Estadísticas por período y por sede

### Compras y Proveedores
- Proveedores: `/api/suppliers/suppliers/`
- Opciones de compra: `/api/suppliers/purchase-options/`
- Órdenes de compra e items: `/api/purchases/orders/`, `/api/purchases/items/`

### Créditos (`/api/credits/`)
- Cuentas (ventas) y pagos: `/accounts/`, `/payments/`
- Cuentas (compras) y pagos: `/purchase-accounts/`, `/purchase-payments/`
- Estadísticas, resúmenes y URLs de WhatsApp para recordatorios

### Entregas (`/api/deliveries/`)
- Entregas CRUD y acciones (`update_status`, `mark_shipped`, `mark_delivered`)
- Estadísticas y resúmenes por ubicación

### Caja (`/api/cash/`)
- Cajas por sede: `/cashes/` (+ `summary`)
- Movimientos: `/movements/` (+ `cancel`/`reactivate`)
- Transferencias: `/transfers/` (+ `execute`/`cancel`)

### Core
- Health check: `/api/core/health-check/` (verifica DB y caché)

## Testing
```bash
pytest -q
```
- En CI/tests, se usa SQLite en memoria (`USE_SQLITE_FOR_TESTS=True`)
- Suite de pruebas por app (ver carpeta `tests/` en cada app)

## Despliegue (Railway/Render)
- Configurar variables (`SECRET_KEY`, `DEBUG=False`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, email/Twilio si aplica)
- `collectstatic` manejado por WhiteNoise
- Revisar `RAILWAY_PERFORMANCE_TROUBLESHOOTING.md` para optimizaciones

---

## Notas de negocio
- Modelo de productos “independientes” con conversiones manuales (no hay desarmados automáticos en ventas).
- Documentación funcional ampliada en `docs/` (tests de lotes, jerarquías, conversión manual, guía frontend).

Si necesitas ejemplos de request/response específicos por endpoint, consulta Swagger o los tests de cada app.
