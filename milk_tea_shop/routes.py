import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Product, Order, OrderItem


main_bp = Blueprint("main", __name__)

MAX_QUANTITY = 99
CATEGORIES = ["Tất cả", "Trà sữa", "Topping"]
ORDER_STATUS = ["Chờ xác nhận", "Đang làm", "Đang giao", "Hoàn thành", "Đã hủy"]


# =========================
# HÀM NHỎ DÙNG CHUNG
# =========================

def money(number):
    return f"{number:,.0f}đ".replace(",", ".")


@main_bp.app_context_processor
def send_data_to_html():
    cart = session.get("cart", {})
    cart_count = 0

    for quantity in cart.values():
        cart_count += int(quantity)

    return {
        "money": money,
        "cart_count": cart_count
    }


def save_image(file):
    if file and file.filename != "":
        filename = secure_filename(file.filename)
        new_name = datetime.now().strftime("%Y%m%d%H%M%S_") + filename
        file_path = os.path.join(current_app.config["IMAGE_FOLDER"], new_name)
        file.save(file_path)
        return new_name

    return ""


def check_login():
    if "user_id" not in session:
        flash("Vui lòng đăng nhập trước.", "warning")
        return False
    return True


def check_admin():
    if "user_id" not in session:
        flash("Vui lòng đăng nhập trước.", "warning")
        return False

    if session.get("role") != "admin":
        flash("Bạn không có quyền truy cập trang quản lý.", "danger")
        return False

    return True


def check_user():
    if "user_id" not in session:
        flash("Vui lòng đăng nhập trước.", "warning")
        return False

    if session.get("role") == "admin":
        flash("Admin chỉ dùng trang quản lý.", "warning")
        return False

    return True


# =========================
# ĐĂNG NHẬP / ĐĂNG KÝ
# =========================

@main_bp.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    if session.get("role") == "admin":
        return redirect(url_for("main.dashboard"))

    return redirect(url_for("main.menu"))


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("main.menu"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role

            flash("Đăng nhập thành công.", "success")

            if user.role == "admin":
                return redirect(url_for("main.dashboard"))

            return redirect(url_for("main.menu"))

        flash("Sai tài khoản hoặc mật khẩu.", "danger")

    return render_template("login.html")


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("main.menu"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if username == "" or password == "" or confirm_password == "":
            return render_template("register.html", error="Vui lòng nhập đầy đủ thông tin.")

        if password != confirm_password:
            return render_template("register.html", error="Mật khẩu nhập lại không khớp.")

        old_user = User.query.filter_by(username=username).first()

        if old_user:
            return render_template("register.html", error="Tên đăng nhập đã tồn tại.")

        new_user = User(
            username=username,
            password=generate_password_hash(password),
            role="user"
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Đăng ký thành công. Bạn có thể đăng nhập.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html")


@main_bp.route("/logout")
def logout():
    session.clear()
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for("main.login"))


# =========================
# KHÁCH HÀNG
# =========================

@main_bp.route("/menu")
def menu():
    if not check_user():
        return redirect(url_for("main.login"))

    keyword = request.args.get("keyword", "").strip()
    category = request.args.get("category", "Tất cả")

    query = Product.query

    if keyword != "":
        query = query.filter(Product.name.ilike(f"%{keyword}%"))

    if category != "Tất cả":
        query = query.filter(Product.category == category)

    products = query.order_by(Product.id.desc()).all()

    return render_template(
        "menu.html",
        products=products,
        categories=CATEGORIES,
        keyword=keyword,
        selected_category=category
    )


@main_bp.route("/order/<int:product_id>", methods=["GET", "POST"])
def order(product_id):
    if not check_user():
        return redirect(url_for("main.login"))

    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        note = request.form.get("note", "").strip()
        quantity = request.form.get("quantity", 1, type=int)

        if customer_name == "" or phone == "" or address == "":
            flash("Vui lòng nhập họ tên, số điện thoại và địa chỉ.", "warning")
            return redirect(url_for("main.order", product_id=product.id))

        if quantity < 1:
            quantity = 1

        if quantity > MAX_QUANTITY:
            quantity = MAX_QUANTITY

        total_price = product.price * quantity

        new_order = Order(
            user_id=session.get("user_id"),
            customer_name=customer_name,
            phone=phone,
            address=address,
            note=note,
            total_price=total_price,
            status="Chờ xác nhận"
        )

        db.session.add(new_order)
        db.session.flush()

        order_item = OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=quantity,
            price=product.price
        )

        db.session.add(order_item)
        db.session.commit()

        flash("Đặt món thành công! Tổng tiền: " + money(total_price), "success")
        return redirect(url_for("main.my_orders"))

    return render_template("order.html", product=product)


@main_bp.route("/cart")
def cart():
    if not check_user():
        return redirect(url_for("main.login"))

    cart = session.get("cart", {})
    cart_items = []
    total_price = 0

    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))

        if product:
            quantity = int(quantity)
            item_total = product.price * quantity
            total_price += item_total

            cart_items.append({
                "product": product,
                "quantity": quantity,
                "item_total": item_total
            })

    return render_template("cart.html", cart_items=cart_items, total_price=total_price)


@main_bp.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if not check_user():
        return redirect(url_for("main.login"))

    product = Product.query.get_or_404(product_id)

    if "cart" not in session:
        session["cart"] = {}

    cart = session["cart"]
    key = str(product.id)

    old_quantity = int(cart.get(key, 0))
    add_quantity = request.form.get("quantity", 1, type=int)

    if add_quantity < 1:
        add_quantity = 1

    new_quantity = old_quantity + add_quantity

    if new_quantity > MAX_QUANTITY:
        new_quantity = MAX_QUANTITY
        flash("Mỗi món tối đa 99 ly.", "warning")
    else:
        flash("Đã thêm món vào giỏ hàng.", "success")

    cart[key] = new_quantity
    session["cart"] = cart
    session.modified = True

    return redirect(url_for("main.menu"))


@main_bp.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    if not check_user():
        return redirect(url_for("main.login"))

    cart = session.get("cart", {})
    key = str(product_id)

    quantity = request.form.get("quantity", 1, type=int)

    if quantity < 1:
        quantity = 1

    if quantity > MAX_QUANTITY:
        quantity = MAX_QUANTITY

    if key in cart:
        cart[key] = quantity
        session["cart"] = cart
        session.modified = True
        flash("Đã cập nhật giỏ hàng.", "success")

    return redirect(url_for("main.cart"))


@main_bp.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    if not check_user():
        return redirect(url_for("main.login"))

    cart = session.get("cart", {})
    cart.pop(str(product_id), None)

    session["cart"] = cart
    session.modified = True

    flash("Đã xóa món khỏi giỏ hàng.", "success")
    return redirect(url_for("main.cart"))


@main_bp.route("/cart/checkout", methods=["POST"])
def checkout_cart():
    if not check_user():
        return redirect(url_for("main.login"))

    cart = session.get("cart", {})

    if not cart:
        flash("Giỏ hàng đang trống.", "warning")
        return redirect(url_for("main.cart"))

    customer_name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    note = request.form.get("note", "").strip()

    if customer_name == "" or phone == "" or address == "":
        flash("Vui lòng nhập họ tên, số điện thoại và địa chỉ.", "warning")
        return redirect(url_for("main.cart"))

    total_price = 0
    cart_items = []

    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))

        if product:
            quantity = int(quantity)
            item_total = product.price * quantity
            total_price += item_total

            cart_items.append({
                "product": product,
                "quantity": quantity
            })

    new_order = Order(
        user_id=session.get("user_id"),
        customer_name=customer_name,
        phone=phone,
        address=address,
        note=note,
        total_price=total_price,
        status="Chờ xác nhận"
    )

    db.session.add(new_order)
    db.session.flush()

    for item in cart_items:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item["product"].id,
            quantity=item["quantity"],
            price=item["product"].price
        )
        db.session.add(order_item)

    db.session.commit()

    session["cart"] = {}
    session.modified = True

    flash("Đặt hàng thành công! Tổng tiền: " + money(total_price), "success")
    return redirect(url_for("main.my_orders"))


@main_bp.route("/my-orders")
def my_orders():
    if not check_user():
        return redirect(url_for("main.login"))

    orders = Order.query.filter_by(
        user_id=session.get("user_id")
    ).order_by(Order.created_at.desc()).all()

    return render_template("my_orders.html", orders=orders)


# =========================
# ADMIN
# =========================

@main_bp.route("/admin/dashboard")
def dashboard():
    if not check_admin():
        return redirect(url_for("main.login"))

    product_count = Product.query.count()
    order_count = Order.query.count()
    revenue = db.session.query(db.func.sum(Order.total_price)).scalar() or 0

    return render_template(
        "dashboard.html",
        product_count=product_count,
        order_count=order_count,
        revenue=revenue
    )


@main_bp.route("/admin/products")
def admin_products():
    if not check_admin():
        return redirect(url_for("main.login"))

    products = Product.query.order_by(Product.id.desc()).all()
    return render_template("admin_products.html", products=products)


@main_bp.route("/admin/products/add", methods=["GET", "POST"])
def add_product():
    if not check_admin():
        return redirect(url_for("main.login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "Trà sữa").strip()
        size = request.form.get("size", "M/L").strip()
        topping = request.form.get("topping", "Không").strip()
        price = request.form.get("price", type=int)
        description = request.form.get("description", "").strip()
        image = save_image(request.files.get("image"))

        if name == "" or not price or price < 0:
            flash("Vui lòng nhập tên món và giá hợp lệ.", "warning")
            return redirect(url_for("main.add_product"))

        new_product = Product(
            name=name,
            category=category,
            size=size,
            topping=topping,
            price=price,
            description=description,
            image=image
        )

        db.session.add(new_product)
        db.session.commit()

        flash("Thêm món thành công.", "success")
        return redirect(url_for("main.admin_products"))

    return render_template("add_product.html", categories=CATEGORIES[1:])


@main_bp.route("/admin/products/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if not check_admin():
        return redirect(url_for("main.login"))

    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        product.name = request.form.get("name", "").strip()
        product.category = request.form.get("category", "Trà sữa").strip()
        product.size = request.form.get("size", "M/L").strip()
        product.topping = request.form.get("topping", "Không").strip()
        product.price = request.form.get("price", type=int) or product.price
        product.description = request.form.get("description", "").strip()

        image = save_image(request.files.get("image"))

        if image != "":
            product.image = image

        db.session.commit()

        flash("Cập nhật món thành công.", "success")
        return redirect(url_for("main.admin_products"))

    return render_template("edit_product.html", product=product, categories=CATEGORIES[1:])


@main_bp.route("/admin/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if not check_admin():
        return redirect(url_for("main.login"))

    product = Product.query.get_or_404(product_id)

    db.session.delete(product)
    db.session.commit()

    flash("Đã xóa món.", "success")
    return redirect(url_for("main.admin_products"))


@main_bp.route("/admin/orders")
def order_list():
    if not check_admin():
        return redirect(url_for("main.login"))

    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("order_list.html", orders=orders, status_list=ORDER_STATUS)


@main_bp.route("/admin/orders/<int:order_id>/status", methods=["POST"])
def update_order_status(order_id):
    if not check_admin():
        return redirect(url_for("main.login"))

    order = Order.query.get_or_404(order_id)
    status = request.form.get("status", "Chờ xác nhận")

    if status in ORDER_STATUS:
        order.status = status
        db.session.commit()
        flash("Đã cập nhật trạng thái đơn hàng.", "success")
    else:
        flash("Trạng thái không hợp lệ.", "danger")

    return redirect(url_for("main.order_list"))