from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# db dùng chung cho cả project
db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user")  # admin hoặc user

    orders = db.relationship("Order", backref="user", lazy=True)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    size = db.Column(db.String(50), default="M/L")
    topping = db.Column(db.String(120), default="Không")
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, default="")
    image = db.Column(db.String(255), default="")

    order_items = db.relationship("OrderItem", backref="product", lazy=True)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    customer_name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(30), default="")
    address = db.Column(db.String(255), default="")
    note = db.Column(db.Text, default="")

    total_price = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default="Chờ xác nhận")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Integer, nullable=False)
