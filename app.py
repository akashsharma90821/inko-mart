import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ----------------- APP CONFIG -----------------
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "inko-secret")

database_url = os.environ.get("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///inko.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------- LOGIN MANAGER -----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in first."

# ----------------- DATABASE MODEL -----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ----------------- PRODUCTS -----------------
PRODUCTS = [
    {"id": 1, "name": "Maggi", "price": 20, "category": "Snacks", "image": "maggi.png"},
    {"id": 2, "name": "Amul Milk", "price": 30, "category": "Dairy", "image": "milk.png"},
    {"id": 3, "name": "Parle-G", "price": 10, "category": "Snacks", "image": "parle.png"},
    {"id": 4, "name": "Lay's Chips", "price": 20, "category": "Snacks", "image": "chips.png"},
    {"id": 5, "name": "Bisleri Water", "price": 20, "category": "Drinks", "image": "water.png"},
    {"id": 6, "name": "Dairy Milk", "price": 50, "category": "Chocolate", "image": "chocolate.png"},
    {"id": 7, "name": "Bread", "price": 40, "category": "Bakery", "image": "bread.png"},
    {"id": 8, "name": "Banana", "price": 35, "category": "Fruits", "image": "banana.png"},
    {"id": 9, "name": "Apple", "price": 80, "category": "Fruits", "image": "apple.png"},
    {"id": 10, "name": "Coca Cola", "price": 40, "category": "Drinks", "image": "cola.png"},
]

CATEGORIES = ["All", "Snacks", "Dairy", "Drinks", "Chocolate", "Bakery", "Fruits"]

# ----------------- CART HELPERS -----------------
def get_cart():
    cart = session.get("cart")
    if not isinstance(cart, dict):
        cart = {}
        session["cart"] = cart
    return cart

def cart_count():
    return sum(get_cart().values())

@app.context_processor
def inject_cart_count():
    return {"cart_count": cart_count()}

def find_product(product_id):
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product
    return None

def build_cart_items():
    cart = get_cart()
    cart_items = []
    subtotal = 0

    for pid, qty in cart.items():
        product = find_product(int(pid))
        if product:
            item_total = product["price"] * qty
            subtotal += item_total
            cart_items.append({
                "product": product,
                "qty": qty,
                "item_total": item_total
            })

    delivery_fee = 0 if subtotal >= 199 else 25 if subtotal > 0 else 0
    total = subtotal + delivery_fee

    return cart_items, subtotal, delivery_fee, total

# ----------------- ROUTES -----------------
@app.route("/")
def index():
    search = request.args.get("search", "").strip().lower()
    category = request.args.get("category", "All")

    filtered_products = PRODUCTS

    if category != "All":
        filtered_products = [p for p in filtered_products if p["category"] == category]

    if search:
        filtered_products = [p for p in filtered_products if search in p["name"].lower()]

    featured = PRODUCTS[:4]

    return render_template(
        "index.html",
        products=filtered_products,
        categories=CATEGORIES,
        selected_category=category,
        search=search,
        featured=featured
    )

@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):
    product = find_product(product_id)
    if not product:
        flash("Product not found.")
        return redirect(url_for("index"))

    cart = get_cart()
    pid = str(product_id)
    cart[pid] = cart.get(pid, 0) + 1
    session["cart"] = cart

    flash("Item added to cart!")
    return redirect(url_for("index"))

@app.route("/cart")
def cart():
    cart_items, subtotal, delivery_fee, total = build_cart_items()
    return render_template(
        "cart.html",
        cart_items=cart_items,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=total
    )

@app.route("/increase/<int:product_id>")
def increase(product_id):
    cart = get_cart()
    pid = str(product_id)

    if pid in cart:
        cart[pid] += 1
        session["cart"] = cart

    return redirect(url_for("cart"))

@app.route("/decrease/<int:product_id>")
def decrease(product_id):
    cart = get_cart()
    pid = str(product_id)

    if pid in cart:
        cart[pid] -= 1
        if cart[pid] <= 0:
            del cart[pid]
        session["cart"] = cart

    return redirect(url_for("cart"))

@app.route("/checkout")
def checkout():
    cart_items, subtotal, delivery_fee, total = build_cart_items()

    if not cart_items:
        flash("Cart is empty!")
        return redirect(url_for("index"))

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=total
    )

@app.route("/place_order", methods=["POST"])
def place_order():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    payment_method = request.form.get("payment_method", "").strip()

    if not name or not phone or not address or not payment_method:
        flash("Please fill all checkout details.")
        return redirect(url_for("checkout"))

    _, subtotal, delivery_fee, total = build_cart_items()

    if total == 0:
        flash("Your cart is empty.")
        return redirect(url_for("index"))

    order_data = {
        "name": name,
        "phone": phone,
        "address": address,
        "payment_method": payment_method,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total
    }

    session["last_order"] = order_data
    session["cart"] = {}

    return redirect(url_for("order_success"))

@app.route("/order-success")
def order_success():
    order = session.get("last_order")
    if not order:
        return redirect(url_for("index"))
    return render_template("order_success.html", order=order)

@app.route("/ai", methods=["GET", "POST"])
def ai_assistant():
    ai_reply = None
    user_message = ""

    if request.method == "POST":
        user_message = request.form.get("message", "").strip()
        if user_message:
            ai_reply = "AI feature will be added later. For now, use search, categories, and cart features."

    return render_template("ai.html", ai_reply=ai_reply, user_message=user_message)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not username or not email or not password:
            flash("Please fill all fields.")
            return redirect(url_for("register"))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash("Registered successfully! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Please enter email and password.")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.")
    return redirect(url_for("index"))

# ----------------- CREATE TABLES -----------------
with app.app_context():
    db.create_all()

# ----------------- RUN APP -----------------
if __name__ == "__main__":
    app.run(debug=True)