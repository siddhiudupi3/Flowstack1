import os, csv, io
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Email, Optional, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
database_url = os.environ.get("DATABASE_URL", "sqlite:///flowstock.db")
if database_url.startswith("mysql://"):
    database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CSRFProtect(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to access the system."

# ----------------------------- Database models -----------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, nullable=False, default=10)
    unit_price = db.Column(db.Float, nullable=False, default=0)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier", backref="products")

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact_person = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    category = db.Column(db.String(80), nullable=True)

class CustomerOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(30), unique=True, nullable=False)
    customer = db.Column(db.String(120), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(30), default="Pending")
    product = db.relationship("Product")

class Shipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tracking_code = db.Column(db.String(40), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("customer_order.id"), nullable=False)
    destination = db.Column(db.String(180), nullable=False)
    courier = db.Column(db.String(100), nullable=False)
    expected_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), default="Dispatched")
    order = db.relationship("CustomerOrder")

class StockMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    movement_type = db.Column(db.String(20), nullable=False)  # IN / OUT / ADJUSTMENT
    quantity = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(250), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship("Product")

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

# --------------------------------- Forms ------------------------------------
class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")

class ProductForm(FlaskForm):
    name = StringField("Product name", validators=[DataRequired(), Length(max=120)])
    sku = StringField("SKU", validators=[DataRequired(), Length(max=50)])
    category = StringField("Category", validators=[DataRequired(), Length(max=80)])
    quantity = IntegerField("Opening quantity", validators=[DataRequired(), NumberRange(min=0)])
    reorder_level = IntegerField("Reorder level", validators=[DataRequired(), NumberRange(min=0)])
    unit_price = StringField("Unit price (₹)", validators=[DataRequired()])
    supplier_id = SelectField("Supplier", coerce=int, validators=[Optional()])
    submit = SubmitField("Save product")

class SupplierForm(FlaskForm):
    name = StringField("Supplier name", validators=[DataRequired(), Length(max=120)])
    contact_person = StringField("Contact person", validators=[DataRequired(), Length(max=100)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    category = StringField("Category supplied", validators=[Optional(), Length(max=80)])
    submit = SubmitField("Save supplier")

class OrderForm(FlaskForm):
    customer = StringField("Customer name", validators=[DataRequired(), Length(max=120)])
    product_id = SelectField("Product", coerce=int, validators=[DataRequired()])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField("Create order")

class ShipmentForm(FlaskForm):
    order_id = SelectField("Order", coerce=int, validators=[DataRequired()])
    tracking_code = StringField("Tracking ID", validators=[DataRequired(), Length(max=40)])
    destination = StringField("Destination", validators=[DataRequired(), Length(max=180)])
    courier = StringField("Courier company", validators=[DataRequired(), Length(max=100)])
    expected_date = StringField("Expected delivery (YYYY-MM-DD)", validators=[Optional()])
    status = SelectField("Status", choices=[("Dispatched","Dispatched"),("In transit","In transit"),("Delivered","Delivered"),("Delayed","Delayed")])
    submit = SubmitField("Save shipment")

class StockForm(FlaskForm):
    product_id = SelectField("Product", coerce=int, validators=[DataRequired()])
    movement_type = SelectField("Movement", choices=[("IN","Stock received"),("OUT","Stock issued")])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)])
    note = StringField("Reference / note", validators=[Optional(), Length(max=250)])
    submit = SubmitField("Update stock")

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "admin":
            flash("Administrator permission is required for that action.", "warning")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper

def populate_selects():
    return [(0, "— No supplier —")] + [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name).all()]

# --------------------------------- Routes -----------------------------------
@app.route("/")
@login_required
def dashboard():
    products = Product.query.order_by(Product.name).all()
    low_stock = [p for p in products if p.quantity <= p.reorder_level]
    open_orders = CustomerOrder.query.filter(CustomerOrder.status != "Delivered").count()
    moving = Shipment.query.filter(Shipment.status.in_(["Dispatched", "In transit"])).count()
    recent_orders = CustomerOrder.query.order_by(CustomerOrder.order_date.desc(), CustomerOrder.id.desc()).limit(6).all()
    recent_movements = StockMovement.query.order_by(StockMovement.created_at.desc()).limit(6).all()
    category_totals = {}
    for p in products: category_totals[p.category] = category_totals.get(p.category, 0) + p.quantity
    return render_template("dashboard.html", products=products, low_stock=low_stock,
        open_orders=open_orders, moving=moving, recent_orders=recent_orders,
        recent_movements=recent_movements, category_totals=category_totals)

@app.route("/login", methods=["GET","POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Incorrect username or password.", "danger")
    return render_template("login.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have signed out.", "success")
    return redirect(url_for("login"))

@app.route("/inventory")
@login_required
def inventory():
    q = request.args.get("q", "").strip()
    stock_filter = request.args.get("stock", "all")
    query = Product.query
    if q: query = query.filter(db.or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%"), Product.category.ilike(f"%{q}%")))
    products = query.order_by(Product.name).all()
    if stock_filter == "low": products = [p for p in products if p.quantity <= p.reorder_level]
    elif stock_filter == "healthy": products = [p for p in products if p.quantity > p.reorder_level]
    return render_template("inventory.html", products=products, q=q, stock_filter=stock_filter)

@app.route("/inventory/add", methods=["GET","POST"])
@admin_required
def add_product():
    form = ProductForm()
    form.supplier_id.choices = populate_selects()
    if form.validate_on_submit():
        sku = form.sku.data.strip().upper()
        if Product.query.filter_by(sku=sku).first():
            flash("That SKU already exists. Use a unique SKU.", "danger")
        else:
            try: price = float(form.unit_price.data)
            except ValueError: price = -1
            if price < 0: flash("Enter a valid non-negative unit price.", "danger")
            else:
                p = Product(name=form.name.data.strip(), sku=sku, category=form.category.data.strip(),
                    quantity=form.quantity.data, reorder_level=form.reorder_level.data, unit_price=price,
                    supplier_id=form.supplier_id.data or None)
                db.session.add(p); db.session.flush()
                if p.quantity: db.session.add(StockMovement(product_id=p.id, movement_type="IN", quantity=p.quantity, note="Opening stock"))
                db.session.commit(); flash("Product added successfully.", "success")
                return redirect(url_for("inventory"))
    return render_template("form.html", form=form, title="Add inventory product", back=url_for("inventory"))

@app.route("/inventory/<int:product_id>/edit", methods=["GET","POST"])
@admin_required
def edit_product(product_id):
    p = Product.query.get_or_404(product_id); form = ProductForm(obj=p)
    form.supplier_id.choices = populate_selects()
    if request.method == "GET": form.supplier_id.data = p.supplier_id or 0
    if form.validate_on_submit():
        sku = form.sku.data.strip().upper()
        duplicate = Product.query.filter(Product.sku==sku, Product.id!=p.id).first()
        try: price = float(form.unit_price.data)
        except ValueError: price = -1
        if duplicate: flash("Another product already uses that SKU.", "danger")
        elif price < 0: flash("Enter a valid non-negative unit price.", "danger")
        else:
            p.name=form.name.data.strip(); p.sku=sku; p.category=form.category.data.strip()
            p.reorder_level=form.reorder_level.data; p.unit_price=price; p.supplier_id=form.supplier_id.data or None
            # Quantity changes should be made through stock movements to preserve audit history.
            db.session.commit(); flash("Product details updated. Use Stock movements to change quantity.", "success")
            return redirect(url_for("inventory"))
    return render_template("form.html", form=form, title="Edit product", back=url_for("inventory"), lock_quantity=True)

@app.route("/stock", methods=["GET","POST"])
@login_required
def stock():
    form = StockForm()
    form.product_id.choices = [(p.id, f"{p.name} ({p.sku}) — {p.quantity} units") for p in Product.query.order_by(Product.name).all()]
    if form.validate_on_submit():
        p = db.session.get(Product, form.product_id.data)
        qty = form.quantity.data
        if not p: flash("Select a valid product.", "danger")
        elif form.movement_type.data == "OUT" and p.quantity < qty: flash("Not enough stock available for this issue.", "danger")
        else:
            p.quantity += qty if form.movement_type.data == "IN" else -qty
            db.session.add(StockMovement(product_id=p.id, movement_type=form.movement_type.data, quantity=qty, note=form.note.data))
            db.session.commit(); flash("Stock updated and movement recorded.", "success")
            return redirect(url_for("stock"))
    movements = StockMovement.query.order_by(StockMovement.created_at.desc()).limit(100).all()
    return render_template("stock.html", form=form, movements=movements)

@app.route("/orders")
@login_required
def orders():
    items = CustomerOrder.query.order_by(CustomerOrder.id.desc()).all()
    return render_template("orders.html", orders=items)

@app.route("/orders/add", methods=["GET","POST"])
@login_required
def add_order():
    form = OrderForm()
    form.product_id.choices = [(p.id, f"{p.name} — {p.quantity} available") for p in Product.query.order_by(Product.name).all()]
    if form.validate_on_submit():
        p = db.session.get(Product, form.product_id.data); qty = form.quantity.data
        if not p: flash("Select a valid product.", "danger")
        elif p.quantity < qty: flash(f"Insufficient stock. Only {p.quantity} units are available.", "danger")
        else:
            code = f"ORD-{datetime.utcnow():%y%m%d%H%M%S}-{CustomerOrder.query.count()+1}"
            order = CustomerOrder(order_code=code, customer=form.customer.data.strip(), product_id=p.id, quantity=qty)
            p.quantity -= qty
            db.session.add(order); db.session.flush()
            db.session.add(StockMovement(product_id=p.id, movement_type="OUT", quantity=qty, note=f"Allocated to {code}"))
            db.session.commit(); flash(f"Order {code} created and stock automatically reduced.", "success")
            return redirect(url_for("orders"))
    return render_template("form.html", form=form, title="Create customer order", back=url_for("orders"))

@app.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id):
    o = CustomerOrder.query.get_or_404(order_id)
    new_status = request.form.get("status")
    if new_status not in ["Pending","Processing","Dispatched","Delivered","Cancelled"]:
        flash("Invalid order status.", "danger")
    elif new_status == "Cancelled" and o.status in ["Dispatched", "Delivered"]:
        flash("This order has already been dispatched or delivered and cannot be cancelled here.", "warning")
    elif new_status == "Cancelled" and o.status != "Cancelled":
        p = o.product
        p.quantity += o.quantity
        db.session.add(StockMovement(product_id=p.id, movement_type="IN", quantity=o.quantity, note=f"Restocked from cancelled {o.order_code}"))
        o.status = new_status; db.session.commit(); flash("Order cancelled and stock returned to inventory.", "success")
    else:
        o.status = new_status; db.session.commit(); flash("Order status updated.", "success")
    return redirect(url_for("orders"))

@app.route("/shipments")
@login_required
def shipments():
    items = Shipment.query.order_by(Shipment.id.desc()).all()
    return render_template("shipments.html", shipments=items)

@app.route("/shipments/add", methods=["GET","POST"])
@login_required
def add_shipment():
    form = ShipmentForm()
    form.order_id.choices = [(o.id, f"{o.order_code} — {o.customer}") for o in CustomerOrder.query.filter(CustomerOrder.status!="Cancelled").order_by(CustomerOrder.id.desc()).all()]
    if form.validate_on_submit():
        if Shipment.query.filter_by(tracking_code=form.tracking_code.data.strip().upper()).first():
            flash("That tracking ID already exists.", "danger")
        else:
            try: eta = date.fromisoformat(form.expected_date.data) if form.expected_date.data else None
            except ValueError: eta = None
            s = Shipment(tracking_code=form.tracking_code.data.strip().upper(), order_id=form.order_id.data,
                destination=form.destination.data.strip(), courier=form.courier.data.strip(), expected_date=eta, status=form.status.data)
            db.session.add(s); db.session.commit(); flash("Shipment created.", "success")
            return redirect(url_for("shipments"))
    return render_template("form.html", form=form, title="Create shipment", back=url_for("shipments"))

@app.route("/shipments/<int:shipment_id>/status", methods=["POST"])
@login_required
def update_shipment_status(shipment_id):
    s = Shipment.query.get_or_404(shipment_id); new_status = request.form.get("status")
    if new_status in ["Dispatched","In transit","Delivered","Delayed"]:
        s.status = new_status
        if new_status == "Delivered": s.order.status = "Delivered"
        db.session.commit(); flash("Shipment status updated.", "success")
    else: flash("Invalid shipment status.", "danger")
    return redirect(url_for("shipments"))

@app.route("/suppliers")
@login_required
def suppliers():
    return render_template("suppliers.html", suppliers=Supplier.query.order_by(Supplier.name).all())

@app.route("/suppliers/add", methods=["GET","POST"])
@admin_required
def add_supplier():
    form = SupplierForm()
    if form.validate_on_submit():
        s = Supplier(name=form.name.data.strip(), contact_person=form.contact_person.data.strip(),
            email=form.email.data.strip() or None, phone=form.phone.data.strip() or None, category=form.category.data.strip() or None)
        db.session.add(s); db.session.commit(); flash("Supplier added.", "success")
        return redirect(url_for("suppliers"))
    return render_template("form.html", form=form, title="Add supplier", back=url_for("suppliers"))

@app.route("/reports")
@login_required
def reports():
    products = Product.query.order_by(Product.quantity.desc()).all()
    total_units = sum(p.quantity for p in products)
    stock_value = sum(p.quantity * p.unit_price for p in products)
    delivered = CustomerOrder.query.filter_by(status="Delivered").count()
    return render_template("reports.html", products=products, total_units=total_units, stock_value=stock_value,
        delivered=delivered, supplier_count=Supplier.query.count(), order_count=CustomerOrder.query.count())

@app.route("/reports/inventory.csv")
@login_required
def export_inventory():
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["Product","SKU","Category","Quantity","Reorder level","Unit price","Supplier"])
    for p in Product.query.order_by(Product.name).all():
        writer.writerow([p.name,p.sku,p.category,p.quantity,p.reorder_level,p.unit_price,p.supplier.name if p.supplier else ""])
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=flowstock-inventory.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response

@app.cli.command("init-db")
def init_db():
    """Create tables and demo accounts/sample records."""
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        u=User(username="admin",role="admin"); u.set_password(os.environ.get("ADMIN_PASSWORD","Admin@123")); db.session.add(u)
    if not User.query.filter_by(username="staff").first():
        u=User(username="staff",role="staff"); u.set_password(os.environ.get("STAFF_PASSWORD","Staff@123")); db.session.add(u)
    if Product.query.count() == 0:
        s1=Supplier(name="Metro Components",contact_person="Riya Shah",email="sales@metro.example",phone="+91 90000 10001",category="Electronics")
        s2=Supplier(name="PaperTrail Supplies",contact_person="Kabir Mehta",email="orders@papertrail.example",phone="+91 90000 10002",category="Stationery")
        db.session.add_all([s1,s2]); db.session.flush()
        db.session.add_all([
            Product(name="Wireless Mouse",sku="EL-104",category="Electronics",quantity=42,reorder_level=15,unit_price=599,supplier_id=s1.id),
            Product(name="USB-C Cable",sku="EL-105",category="Electronics",quantity=8,reorder_level=20,unit_price=249,supplier_id=s1.id),
            Product(name="Notebook A5",sku="ST-201",category="Stationery",quantity=120,reorder_level=30,unit_price=60,supplier_id=s2.id),
            Product(name="Packing Carton",sku="PK-310",category="Packaging",quantity=14,reorder_level=25,unit_price=35),
            Product(name="Desk Lamp",sku="HM-410",category="Home",quantity=26,reorder_level=10,unit_price=899)
        ])
    db.session.commit()
    print("FlowStock database initialized. Demo login: admin / Admin@123 (change before deployment).")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
