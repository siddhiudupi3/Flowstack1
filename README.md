# FlowStock — Full-stack logistics and inventory management system

A Flask + SQLAlchemy web application for an academic Idea Lab project. It includes user login, role-based access, inventory, stock movements, orders, suppliers, shipment tracking, dashboard alerts, reports and CSV export.

## 1. Requirements
- Python 3.10 or newer
- pip
- MySQL Server (optional; SQLite is used by default for the quickest first run)

## 2. Run locally (SQLite — easiest)
Open a terminal inside the extracted `FlowStock_FullStack` folder:

```bash
python -m venv venv
```

Activate it:
- Windows: `venv\Scripts\activate`
- macOS/Linux: `source venv/bin/activate`

Install and initialize:
```bash
pip install -r requirements.txt
flask --app app init-db
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

### Demo accounts
- Admin: `admin` / `Admin@123`
- Staff: `staff` / `Staff@123`

Change these passwords and set a unique `SECRET_KEY` before using the app beyond a classroom demo. Demo accounts are created only by the `init-db` command.

## 3. Use MySQL
Create a database in MySQL:
```sql
CREATE DATABASE flowstock CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Set the connection string before starting the app.

Windows PowerShell:
```powershell
$env:DATABASE_URL="mysql+pymysql://flowstock_user:YOUR_PASSWORD@localhost/flowstock"
$env:SECRET_KEY="replace-with-a-long-random-secret"
flask --app app init-db
python app.py
```

macOS/Linux:
```bash
export DATABASE_URL="mysql+pymysql://flowstock_user:YOUR_PASSWORD@localhost/flowstock"
export SECRET_KEY="replace-with-a-long-random-secret"
flask --app app init-db
python app.py
```

Use a dedicated MySQL user and a strong password. Do not publish database credentials in source code or screenshots. If your MySQL password contains special URL characters, URL-encode them.

## 4. Main modules
1. Login and roles: admin and staff.
2. Dashboard: product count, low-stock alerts, open orders, moving shipments, category totals and recent stock movements.
3. Inventory: add/edit products, SKU uniqueness, supplier link, reorder levels and unit prices.
4. Stock movements: stock-in and stock-out records; prevents issuing more than available.
5. Orders: create customer orders; checks availability and automatically deducts stock.
6. Cancellation: cancelling an order returns allocated stock and logs the movement.
7. Suppliers: supplier contact directory.
8. Shipments: tracking ID, courier, destination, expected date and status; delivery updates the order to Delivered.
9. Reports: inventory units, estimated stock value, delivered orders and CSV export.

## 5. Role permissions
- Admin: add/edit products and add suppliers; all other operational functions.
- Staff: view inventory and suppliers, create orders/shipments, update stock and statuses, view reports.

## 6. Important project notes / limitations
- This is a functional educational prototype, not a production-certified logistics platform.
- Shipment statuses are entered by the operator; there is no live courier API connection.
- Route optimization, barcode/QR scanning, email/SMS notifications and AI demand forecasting are planned extensions, not implemented features.
- SQLite is the default. MySQL can be enabled with `DATABASE_URL`.
- For public deployment, use HTTPS, a production WSGI server, a secure secret key, strong account passwords, backups and restricted database access. Do not use Flask's development server in production.

## 7. Suggested future enhancements
- Live courier API integrations and delivery webhooks.
- Barcode/QR label generation and scanner support.
- Multi-warehouse stock transfers.
- Purchase orders and supplier replenishment.
- Forecasting from historical sales.
- Email alerts for low stock and delayed shipments.
- Audit logs and downloadable invoices.
