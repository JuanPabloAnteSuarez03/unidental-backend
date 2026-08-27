# UNIDENTAL — Backend

**English** · [Español](README.es.md)

REST API for UNIDENTAL, a dental-supplies distributor operating from two locations in Cali, Colombia. Built with Django 5.2 and Django REST Framework.

Covers the product catalog (SKUs and batches), per-location inventory, sales and returns, purchases and suppliers, receivables and payables, deliveries, and cash handling.

🔗 **Live API docs:** [Swagger](https://unidental-backend.onrender.com/swagger/) · [Redoc](https://unidental-backend.onrender.com/redoc/)
🔗 **Frontend:** [unidental-frontend](https://github.com/JuanPabloAnteSuarez03/unidental-frontend)

---

## Why this exists

The company's inventory wasn't systematized at all: there was no real database, only Google Sheets with no relational structure between products, batches and locations. Any question — how much stock is left, at which location, from which batch — meant cross-checking spreadsheets by hand.

On top of that, these are products with expiry dates. Without a system modelling the relationship between products, batches and locations, which batch to dispatch was left to staff memory, and the cost of a mistake showed up late, as expired product.

**Why Django and DRF instead of Node:** the domain is strongly relational — products, batches, locations, movements and credits reference each other and need transactional integrity.

---

## Stack

| Concern | Technology |
|---|---|
| Framework | Django 5.2, Django REST Framework |
| Auth | Djoser + DRF token authentication |
| API docs | drf-yasg (Swagger / Redoc) |
| Filtering | django-filter |
| CORS | django-cors-headers |
| Static files | WhiteNoise |
| Database | PostgreSQL (dev/prod) · SQLite (tests) |
| Hosting | Render (also configured for Railway) |

---

## Apps

| App | Responsibility |
|---|---|
| `core` | Utilities, health check, email (Djoser), permissions |
| `catalogs` | Products, categories, SKU system (category/subcategory/type), batches (`ProductBatch`), kits and components, manual conversions |
| `inventory` | Locations and warehouses, stock per location + batch, movements that update stock automatically (inbound, outbound, transfers, composite conversion) |
| `sales` | Customers, sales and items, returns and items, signals that adjust inventory |
| `suppliers` | Suppliers and `PurchaseOption` (brand, price, validity) |
| `purchases` | Purchase orders and items |
| `credits` | Sales receivables and purchase payables, payments, WhatsApp reminders |
| `deliveries` | Deliveries, statuses and statistics |
| `cash` | Per-location cash registers, movements (in/out/adjustment) and transfers |

---

## Quick start

```bash
# 1) Create and activate a virtual environment
python -m venv env
source env/bin/activate        # Windows: env\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Configure your environment (.env) — see below

# 4) Run migrations
python manage.py migrate

# 5) Start the server
python manage.py runserver
```

Then open http://127.0.0.1:8000/swagger/.

---

## Environment variables

| Variable | Notes |
|---|---|
| `SECRET_KEY` | Required |
| `DEBUG` | `True` / `False` |
| `ALLOWED_HOSTS` | e.g. `127.0.0.1,localhost` |
| `CSRF_TRUSTED_ORIGINS` | e.g. `https://my-domain.app` |
| `DATABASE_URL` | PostgreSQL connection string |
| `USE_SQLITE_FOR_TESTS` | `True` to run the suite on in-memory SQLite |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL` | Production email |

---

## Authentication

Djoser endpoints live under `/api/auth/`.

```http
POST /api/auth/token/login/      → returns a token
Authorization: Token <token>     → send it on every authenticated request
```

---

## Importing the client's data

Management commands populate the database from the CSV exports of the client's original spreadsheets, which are checked into the repository.

```bash
# All-in-one orchestrator
python manage.py import_all
```

It runs, in order:

1. `populate_database_fast "UNIDENTAL - COMPRAS E INV (1).csv" --clear-data` — products, SKUs, batches, stock, purchase options and orders
2. `populate_suppliers --file "UNIDENTAL (1) - PROVEEDORES 2024.csv"` — suppliers (without `--clean`, to preserve `PurchaseOption`)
3. `populate_customers --file "UNIDENTAL (1) - BASE DATOS  .csv" --clean` — customers

Individual commands accept `--clear-data`, `--dry-run` and `--orders-only`.

> **Notes**
> - Batches are only created when the expiry date can be parsed; otherwise the product ends up without batch tracking.
> - `InventoryStock` is created from the per-location inventory columns; if they are `0` or empty, no stock is attached even when batches exist.
> - Use `populate_suppliers --clean` with care — it cascades onto `PurchaseOption`.

---

## API reference

Interactive documentation: `/swagger/`, `/redoc/`, raw schema at `/swagger.json` or `/swagger.yaml`.

Pagination is DRF's `PageNumberPagination` with `PAGE_SIZE=25`; filtering via `django-filter`; text search through `?search=`.

<details>
<summary><strong>Notable endpoints by domain</strong></summary>

**Catalog** — `/api/catalogs/`
- Products: `/products/`, unpaginated `/products/all/`
- Products by location: `GET /products/by-location/?location=<id>&has_stock=true|false&search=...`
- Kit components: `/product-components/` · Batches: `/product-batches/`
- Manual conversions: `/product-conversions/`, `/conversions/execute/`, `/conversions/suggest/`
- SKU system: `/sku-categories/`, `/sku-subcategories/`, `/sku-types/`, `/sku/info/`, `/sku/generate/`, `/sku/validate/`

**Inventory** — `/api/inventory/`
- Locations: `/locations/`
- Stock: `/stock/`, `/stock/summary/`, `/stock/all/`
- FIFO batch stock: `/stock/by_batches/`
- Batches of a product across locations: `/stock/product_batches_stock/?product=...`
- Batches at one location: `/stock/location_batch_stock/?location=...`
- Movements: `/movements/` (+ `complete`, `cancel`), stock-level and expiry alerts

**Sales** — `/api/sales/`
- Customers `/customers/` · Sales `/sales/`, `/sale-items/` · Returns `/returns/`, `/return-items/`
- Statistics by period and location

**Purchases & suppliers**
- `/api/suppliers/suppliers/` · `/api/suppliers/purchase-options/`
- `/api/purchases/orders/` · `/api/purchases/items/`

**Credits** — `/api/credits/`
- Receivables `/accounts/`, `/payments/` · Payables `/purchase-accounts/`, `/purchase-payments/`
- Statistics, summaries and WhatsApp reminder URLs

**Deliveries** — `/api/deliveries/`
- CRUD plus `update_status`, `mark_shipped`, `mark_delivered`; statistics per location

**Cash** — `/api/cash/`
- Registers `/cashes/` (+ `summary`) · Movements `/movements/` (+ `cancel`, `reactivate`) · Transfers `/transfers/` (+ `execute`, `cancel`)

**Core**
- Health check: `/api/core/health-check/` — verifies database and cache

</details>

---

## Testing

```bash
pytest -q
```

Tests run against in-memory SQLite (`USE_SQLITE_FOR_TESTS=True`). Each app carries its own `tests/` folder.

---

## Deployment

Deployed on Render (`render.yaml`; `railway.json` is also present for Railway).

- Set `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and the email variables
- `collectstatic` is handled by WhiteNoise
- See `RAILWAY_PERFORMANCE_TROUBLESHOOTING.md` for performance notes

---

## Business notes

- Products are modelled as **independent items with manual conversions** — there is no automatic breakdown of kits during a sale.
- Batch selection defaults to **FIFO** (closest to expiry first), with a **manual override**: the counter needs to break that rule when a customer asks for a specific batch. Automating with no escape hatch would have pushed staff to work around the system.
- Extended functional documentation lives in `docs/`.

---

## About

Built by [Juan Pablo Ante Suárez](https://github.com/JuanPabloAnteSuarez03). I developed the entire backend; the React frontend was implemented largely together with a teammate, on top of this API.

📖 **Full case study:** [juanpabloante.vercel.app/en/projects/unidental](https://juanpabloante.vercel.app/en/projects/unidental)

---

Private · © UNIDENTAL. All rights reserved.
