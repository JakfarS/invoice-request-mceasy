# Odoo 17 + Custom Module + Client App

This project includes:
- Odoo 17 with custom add-on `odoo_module` mounted into the container
- A lightweight client backend in `client_app`
- PostgreSQL database

All services run via `docker-compose.yml` in this folder.

## A) Setup: Odoo and Client Backend

Prerequisites:
- Docker and Docker Compose

Steps:
1. Start the stack
```bash
docker compose up -d --build
```
2. Access services
- Odoo UI: http://localhost:8069
- Client App: http://localhost:4000
- Postgres: localhost:5432

3. First-time Odoo setup
- Default DB connection is configured by the container command
- Log in to Odoo and update the Apps list
- Install the app `odoo_module` (mounted from `./odoo_module`)

4. Client App
- Built from `./client_app/Dockerfile`
- Env (from compose):
  - `ODOO_URL=http://odoo:8069`
  - `ODOO_DB=odoo`
  - `ODOO_USERNAME=admin`
  - `ODOO_PASSWORD=admin`
  - `PORT=4000`
  - `DEBUG=False`

## B) Endpoints and Testing

The `odoo_module` exposes public endpoints for external invoice requests by partner token (`res.partner.external_token`).

Set a token on a partner (Developer Mode → Contacts → External Token) then use it below.

### 1) External Invoice Form (HTML)
- GET `/external/sale-invoice/<token>`
- Renders a page to request an invoice for eligible Sale Orders

Example:
```bash
curl -i "http://localhost:8069/external/sale-invoice/abc123"
```

### 2) Create Invoice Request
- POST `/external/sale-invoice/<token>/request`
- Body (form-encoded): `sale_order_id=<int>`
- Response: `{ success: boolean, message: string, request_id?: number }`
- Validations: SO must belong to partner, state `sale`, `invoice_status=to invoice`, and not already requested

Example:
```bash
curl -i -X POST \
  -d "sale_order_id=123" \
  "http://localhost:8069/external/sale-invoice/abc123/request"
```

### 3) Refresh Available Sale Orders
- GET `/external/sale-invoice/<token>/available_sos`
- Response: `{ success: boolean, sale_orders: [{ id, name, amount_total }] }`

Example:
```bash
curl -s "http://localhost:8069/external/sale-invoice/abc123/available_sos"
```

### 4) Download Invoice PDF
- GET `/external/sale-invoice/<token>/download/<invoice_id>`

Example:
```bash
curl -o Invoice_1001.pdf "http://localhost:8069/external/sale-invoice/abc123/download/1001"
```

### 5) Status (Pending/Approved)
- GET `/external/sale-invoice/<token>/status`

Example:
```bash
curl -s "http://localhost:8069/external/sale-invoice/abc123/status"
```

Notes:
- Replace `<token>` with partner's external token
- Replace `<so_id>` and `<invoice_id>` accordingly

## C) Client App (Flask XML-RPC Gateway)

The `client_app` is a small Flask service that connects to Odoo via XML-RPC. It exposes REST endpoints useful for testing and integrating with Odoo without using the Odoo HTTP controllers directly.

Base URL (local): http://localhost:4000

Environment (from compose overrides the in-file defaults):
- ODOO_URL: http://odoo:8069
- ODOO_DB: odoo
- ODOO_USERNAME: admin
- ODOO_PASSWORD: admin
- PORT: 4000
- DEBUG: False

Notes:
- The Python defaults in `client_app/app.py` (e.g., `http://localhost:8017`, `odoo17`) are overridden by the Docker Compose environment above when running via Docker.

### Endpoints

- GET `/health`
  - Health check and connection status
  - Example:
  ```bash
  curl -s http://localhost:4000/health | jq
  ```

- GET `/api/sale-orders`
  - Query sale orders
  - Query params: `limit` (int), `offset` (int), `domain` (JSON string)
  - Example (last 5 confirmed SOs):
  ```bash
  curl -s "http://localhost:4000/api/sale-orders?limit=5&domain=%5B%5B%5C%22state%5C%22,%5C%22=%5C%22,%5C%22sale%5C%22%5D%5D" | jq
  ```
  - Human-readable domain before URL-encode: `[["state","=","sale"]]`

- GET `/api/sale-orders/<id>`
  - Read one sale order with details
  - Example:
  ```bash
  curl -s http://localhost:4000/api/sale-orders/123 | jq
  ```

- POST `/api/sale-orders`
  - Create a sale order
  - JSON body requires `partner_id` and `order_line`
  - Minimal example:
  ```bash
  curl -s -X POST http://localhost:4000/api/sale-orders \
    -H 'Content-Type: application/json' \
    -d '{
      "partner_id": 1,
      "order_line": [[0,0,{"product_id": 1, "product_uom_qty": 1, "price_unit": 100}]]
    }' | jq
  ```

- PUT `/api/sale-orders/<id>`
  - Update fields on a sale order
  - Example (update note):
  ```bash
  curl -s -X PUT http://localhost:4000/api/sale-orders/123 \
    -H 'Content-Type: application/json' \
    -d '{"note": "Updated via client_app"}' | jq
  ```

- POST `/api/sale-orders/<id>/confirm`
  - Confirm an order
  - Example:
  ```bash
  curl -s -X POST http://localhost:4000/api/sale-orders/123/confirm | jq
  ```

- POST `/api/sale-orders/<id>/cancel`
  - Cancel an order
  - Example:
  ```bash
  curl -s -X POST http://localhost:4000/api/sale-orders/123/cancel | jq
  ```

- POST `/api/sale-orders/<id>/reset`
  - Reset an order to draft
  - Example:
  ```bash
  curl -s -X POST http://localhost:4000/api/sale-orders/123/reset | jq
  ```

### Postman Collection

A ready-to-use Postman collection is provided: `client_app.postman_collection.json` in this folder.

How to use:
1. Open Postman → Import → select `client_app.postman_collection.json`
2. Set collection variables as needed:
   - `base_url` (default `http://localhost:4000`)
   - `so_id`, `partner_id`, `partner_id_2`, `product_id`
3. Run requests directly (Create SO, Update SO, Get list/detail, Confirm/Cancel/Reset)

## D) Docker Compose (as used here)

This mirrors the provided `docker-compose.yml`.

```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: odoo
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
    volumes:
      - odoo-db-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - odoo-network

  odoo:
    image: odoo:17
    depends_on:
      - db
    command: >
      odoo
      --db_host=db
      --db_port=5432
      --db_user=odoo
      --db_password=odoo
    ports:
      - "8069:8069"
    volumes:
      - ./odoo_module:/mnt/extra-addons/odoo_module
      - ./odoo.conf:/etc/odoo/odoo.conf
      - odoo-web-data:/var/lib/odoo
    networks:
      - odoo-network

  client-app:
    build:
      context: ./client_app
      dockerfile: Dockerfile
    depends_on:
      - odoo
    environment:
      - ODOO_URL=http://odoo:8069
      - ODOO_DB=odoo
      - ODOO_USERNAME=admin
      - ODOO_PASSWORD=admin
      - PORT=4000
      - DEBUG=False
    ports:
      - "4000:4000"
    networks:
      - odoo-network
    restart: unless-stopped

volumes:
  odoo-db-data:
  odoo-web-data:
  odoo-config:

networks:
  odoo-network:
    driver: bridge
```

Troubleshooting:
- If `odoo_module` is not visible, Update Apps List and ensure the `./odoo_module` folder is mounted correctly
- Ensure partners have `external_token` set to access external endpoints
- Eligible SOs must be in state `sale` and `invoice_status=to invoice`
