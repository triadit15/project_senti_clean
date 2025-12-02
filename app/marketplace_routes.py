
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from .models import Store, Product

market = Blueprint("market", __name__, url_prefix="/market")

@market.route("/")
@login_required
def marketplace_home():
    stores = Store.query.limit(10).all()
    categories = [
        "Fashion", "Electronics", "Home", "Beauty",
        "Kids", "Fitness", "Groceries", "Tech Accessories"
    ]
    return render_template(
        "market/home.html",
        stores=stores,
        categories=categories
    )

@market.route("/store/<int:store_id>")
@login_required
def view_store(store_id):
    store = Store.query.get_or_404(store_id)
    products = Product.query.filter_by(store_id=store_id).limit(20).all()
    return render_template("market/store.html", store=store, products=products)

@market.route("/product/<int:product_id>")
@login_required
def view_product(product_id):
    product = Product.query.get_or_404(product_id)

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from .models import Store, Product

market = Blueprint("market", __name__, url_prefix="/market")

@market.route("/")
@login_required
def marketplace_home():
    stores = Store.query.limit(10).all()
    categories = [
        "Fashion", "Electronics", "Home", "Beauty",
        "Kids", "Fitness", "Groceries", "Tech Accessories"
    ]
    return render_template(
        "market/home.html",
        stores=stores,
        categories=categories
    )

@market.route("/store/<int:store_id>")
@login_required
def view_store(store_id):
    store = Store.query.get_or_404(store_id)
    products = Product.query.filter_by(store_id=store_id).limit(20).all()
    return render_template("market/store.html", store=store, products=products)

@market.route("/product/<int:product_id>")
@login_required
def view_product(product_id):
    product = Product.query.get_or_404(product_id)

    return render_template("market/product.html", product=product)