# app/routes.py
from functools import wraps
from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, jsonify, send_file, current_app
)
from flask_login import (
    login_required, login_user, logout_user,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from .models import User, MerchantPayment, Voucher
import io
import qrcode
import datetime
import secrets

bp = Blueprint("main", __name__)

# Helper: render primary template, fallback to alt if primary not found
def render_flexible_template(primary, alt=None, **context):
    """Try to render primary template; if TemplateNotFound, render alt (if provided)."""
    try:
        return render_template(primary, **context)
    except Exception as e:
        # only attempt fallback for missing template errors
        from jinja2 import TemplateNotFound
        if alt and isinstance(e, TemplateNotFound):
            return render_template(alt, **context)
        raise

# Admin guard
def admin_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            flash("Admin access required", "danger")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return wrapped

# ---------------------------------------------------------
# HOME / LANDING
# ---------------------------------------------------------
@bp.route("/")
def home():
    # allow landing.html or home.html fallback
    return render_flexible_template("landing.html", alt="home.html")

# ---------------------------------------------------------
# AUTH: LOGIN / REGISTER / LOGOUT
# ---------------------------------------------------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone")
        password = request.form.get("password")

        user = User.query.filter_by(phone=phone).first()

        if not user or not check_password_hash(user.password, password):
            flash("Invalid login details", "danger")
            return redirect(url_for("main.login"))

        login_user(user)
        return redirect(url_for("main.dashboard"))

    return render_flexible_template("login.html")

@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        phone = request.form.get("phone")
        password = request.form.get("password")

        if User.query.filter_by(phone=phone).first():
            flash("Phone already registered.", "danger")
            return redirect(url_for("main.register"))

        new_user = User(
            phone=phone,
            password=generate_password_hash(password),
            wallet_balance=0,
            created_at=datetime.datetime.utcnow()
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful!", "success")
        return redirect(url_for("main.login"))

    return render_flexible_template("register.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.home"))

# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------
@bp.route("/dashboard")
@login_required
def dashboard():
    # use getattr so missing column doesn't crash
    wallet = getattr(current_user, "wallet_balance", 0) or 0
    # simple stats for small card widgets (can be expanded)
    total_vouchers = Voucher.query.count()
    total_payments = MerchantPayment.query.count()
    return render_flexible_template(
        "dashboard.html",
        wallet=wallet,
        total_vouchers=total_vouchers,
        total_payments=total_payments
    )

# Admin dashboard: totals and quick actions
@bp.route("/admin")
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_vouchers = Voucher.query.count()
    total_payments = MerchantPayment.query.count()
    # sum of all wallet balances (guard missing attribute)
    users = User.query.all()
    total_balance = sum(getattr(u, "wallet_balance", 0) or 0 for u in users)

    return render_flexible_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_vouchers=total_vouchers,
        total_payments=total_payments,
        total_balance=total_balance
    )

# ---------------------------------------------------------
# PROFILE PAGE
# ---------------------------------------------------------
@bp.route("/profile")
@login_required
def profile():
    # pass 'user' for compatibility with templates that expect it
    return render_flexible_template("profile.html", user=current_user)


# ---------------------------------------------------------
# WALLET PAGE
# ---------------------------------------------------------
@bp.route("/wallet")
@login_required
def wallet():
    transactions = []  # placeholder for your transactions logic
    balance = getattr(current_user, "wallet_balance", 0) or 0
    return render_flexible_template("wallet.html", transactions=transactions, balance=balance)

@bp.route("/transactions")
@login_required
def transactions():
    txs = WalletTransaction.query.filter_by(user_id=current_user.id).order_by(
        WalletTransaction.created_at.desc()
    ).all()

    return render_template("transactions.html", transactions=txs)

# ---------------------------------------------------------
# UTILITIES (CLEAN / FINAL VERSION)
# ---------------------------------------------------------

from .models import WalletTransaction  # make sure this import exists

# ---------- MOBILE ----------
@bp.route("/utility/mobile", methods=["GET", "POST"])
@login_required
def utility_mobile():
    if request.method == "POST":
        amount = float(request.form.get("amount", 0))
        network = request.form.get("network")

        if amount <= 0 or not network:
            flash("Invalid mobile purchase details", "danger")
            return redirect(url_for("main.utility_mobile"))

        if current_user.wallet_balance < amount:
            flash("Insufficient wallet balance!", "danger")
            return redirect(url_for("main.utility_mobile"))

        # Deduct
        current_user.wallet_balance -= amount

        # Log transaction
        tx = WalletTransaction(
            user_id=current_user.id,
            type=f"Mobile ({network})",
            amount=amount
        )
        db.session.add(tx)
        db.session.commit()

        flash(f"Successfully purchased R{amount} {network} airtime/data!", "success")
        return redirect(url_for("main.wallet"))

    return render_template("utilities/mobile.html")


# ---------- ELECTRICITY ----------
@bp.route("/utility/electricity", methods=["GET", "POST"])
@login_required
def utility_electricity():
    if request.method == "POST":
        amount = float(request.form.get("amount", 0))
        meter = request.form.get("meter")

        if amount <= 0 or not meter:
            flash("Invalid electricity details", "danger")
            return redirect(url_for("main.utility_electricity"))

        if current_user.wallet_balance < amount:
            flash("Insufficient wallet balance!", "danger")
            return redirect(url_for("main.utility_electricity"))

        current_user.wallet_balance -= amount

        tx = WalletTransaction(
            user_id=current_user.id,
            type=f"Electricity (Meter {meter})",
            amount=amount
        )
        db.session.add(tx)
        db.session.commit()

        flash(f"Electricity token purchased for meter {meter}!", "success")
        return redirect(url_for("main.wallet"))

    return render_template("utilities/electricity.html")


# ---------- DIGITAL VOUCHERS ----------
@bp.route("/utility/vouchers", methods=["GET", "POST"])
@login_required
def utility_vouchers():
    if request.method == "POST":
        brand = request.form.get("brand")
        amount = float(request.form.get("amount", 0))

        if not brand or amount <= 0:
            flash("Invalid voucher purchase details", "danger")
            return redirect(url_for("main.utility_vouchers"))

        if current_user.wallet_balance < amount:
            flash("Not enough wallet balance", "danger")
            return redirect(url_for("main.utility_vouchers"))

        current_user.wallet_balance -= amount

        tx = WalletTransaction(
            user_id=current_user.id,
            type=f"Digital Voucher ({brand})",
            amount=amount
        )
        db.session.add(tx)
        db.session.commit()

        flash(f"You purchased a {brand} voucher!", "success")
        return redirect(url_for("main.wallet"))

    return render_template("utilities/vouchers.html")


# ---------- LOTTO ----------
@bp.route("/utility/lotto", methods=["GET", "POST"])
@login_required
def utility_lotto():
    if request.method == "POST":
        ticket_type = request.form.get("ticket")
        price = float(request.form.get("price", 0))

        if price <= 0 or not ticket_type:
            flash("Invalid Lotto ticket details", "danger")
            return redirect(url_for("main.utility_lotto"))

        if current_user.wallet_balance < price:
            flash("Insufficient wallet balance", "danger")
            return redirect(url_for("main.utility_lotto"))

        current_user.wallet_balance -= price

        tx = WalletTransaction(
            user_id=current_user.id,
            type=f"Lotto ({ticket_type})",
            amount=price
        )
        db.session.add(tx)
        db.session.commit()

        flash("Lotto ticket purchased!", "success")
        return redirect(url_for("main.wallet"))

    return render_template("utilities/lotto.html")



# ---------------------------------------------------------
# QR SCANNER PAGE
# ---------------------------------------------------------
@bp.route("/scan")
@login_required
def qr_scanner():
    # keep endpoint name stable: 'main.qr_scanner'
    return render_flexible_template("scan.html")

# =
# MERCHANT / PAYMENT (STATIC QR)
# =

@bp.route("/merchant/create_payment", methods=["GET", "POST"])
@login_required
def create_merchant_payment():
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount"))
        except (TypeError, ValueError):
            flash("Invalid amount", "danger")
            return redirect(url_for("main.create_merchant_payment"))
        description = request.form.get("description", "")

        code = secrets.token_urlsafe(8)
        mp = MerchantPayment(
            merchant_id=current_user.id,
            amount=amount,
            description=description,
            code=code,
            status="pending",
            created_at=datetime.datetime.utcnow()
        )
        db.session.add(mp)
        db.session.commit()

        return redirect(url_for("main.view_merchant_payment", code=code))

    return render_flexible_template("merchant/create_payment.html")

@bp.route("/merchant/payment/<code>")
@login_required
def view_merchant_payment(code):
    mp = MerchantPayment.query.filter_by(code=code).first_or_404()
    return render_flexible_template("merchant/view_payment.html", payment=mp)

@bp.route("/merchant/payment/<code>/qrcode")
def merchant_payment_qrcode(code):
    # produce QR linking to /merchant/pay/<code>
    link = f"{request.url_root}merchant/pay/{code}"
    qr = qrcode.make(link)
    buf = io.BytesIO()
    qr.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@bp.route("/merchant/pay/<code>", methods=["GET", "POST"])
@login_required
def pay_merchant(code):
    mp = MerchantPayment.query.filter_by(code=code).first_or_404()
    merchant = User.query.get(mp.merchant_id)

    # guard missing wallet_balance
    payer_balance = getattr(current_user, "wallet_balance", 0) or 0
    merchant_balance = getattr(merchant, "wallet_balance", 0) or 0

    if request.method == "POST":
        if payer_balance < mp.amount:
            flash("Insufficient wallet balance", "danger")
            return redirect(url_for("main.pay_merchant", code=code))

        current_user.wallet_balance = payer_balance - mp.amount
        merchant.wallet_balance = merchant_balance + mp.amount

        mp.status = "paid"
        mp.paid_at = datetime.datetime.utcnow()
        db.session.commit()

        flash("Payment successful", "success")
        return redirect(url_for("main.wallet"))

    return render_flexible_template("merchant/pay_merchant.html", payment=mp, merchant=merchant)

@bp.route("/merchant/payments")
@login_required
def merchant_payment_list():
    # endpoint name: main.merchant_payment_list — templates should use this name or url_for('main.merchant_payment_list')
    records = MerchantPayment.query.filter_by(merchant_id=current_user.id).all()
    return render_flexible_template("merchant/payment_list.html", payments=records)

# =
# VOUCHER SYSTEM
# =

@bp.route("/merchant/create_voucher", methods=["GET", "POST"])
@login_required
def create_voucher():
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount"))
        except (TypeError, ValueError):
            flash("Invalid amount", "danger")
            return redirect(url_for("main.create_voucher"))

        code = secrets.token_urlsafe(6)
        v = Voucher(
            creator_id=current_user.id,
            amount=amount,
            code=code,
            status="active",
            created_at=datetime.datetime.utcnow()
        )
        db.session.add(v)
        db.session.commit()
        return redirect(url_for("main.voucher_created", code=code))

    return render_flexible_template("voucher/create_voucher.html")

@bp.route("/voucher/created/<code>")
@login_required
def voucher_created(code):
    v = Voucher.query.filter_by(code=code).first_or_404()
    qr_url = url_for("main.voucher_qrcode", code=code)
    redeem_url = url_for("main.redeem_voucher", code=code)
    return render_flexible_template("voucher/voucher_created.html", voucher=v, qr_url=qr_url, redeem_url=redeem_url)

@bp.route("/voucher/<code>/qrcode")
def voucher_qrcode(code):
    link = f"{request.url_root}redeem/{code}"
    qr = qrcode.make(link)
    buf = io.BytesIO()
    qr.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@bp.route("/redeem/<code>", methods=["GET", "POST"])
@login_required
def redeem_voucher(code):
    # Support showing a redeem confirmation (GET) and performing redeem (POST)
    v = Voucher.query.filter_by(code=code).first_or_404()

    if request.method == "POST":
        if v.status != "active":
            flash("Voucher already used or invalid.", "danger")
            return redirect(url_for("main.wallet"))

        current_user.wallet_balance = (getattr(current_user, "wallet_balance", 0) or 0) + v.amount
        v.status = "redeemed"
        v.redeemed_at = datetime.datetime.utcnow()
        db.session.commit()

        flash("Voucher redeemed successfully!", "success")
        return redirect(url_for("main.wallet"))

    # GET: show a confirmation page that contains voucher details and a Redeem button
    return render_flexible_template("voucher/redeem_confirm.html", voucher=v)

@bp.route("/merchant/vouchers")
@login_required
def merchant_voucher_list():
    # endpoint name: main.merchant_voucher_list
    vouchers = Voucher.query.filter_by(creator_id=current_user.id).all()
    return render_flexible_template("voucher/voucher_list.html", vouchers=vouchers)

@bp.route("/redeem", methods=["GET", "POST"])
@login_required
def redeem_page():
    if request.method == "POST":
        code = request.form.get("code")
        return redirect(url_for("main.redeem_voucher", code=code))
    return render_template("voucher/redeem_page.html")

# Marketplace listing
@bp.route("/marketplace")
@login_required
def marketplace_index():
    products = Product.query.filter_by(in_stock=True).all()
    return render_flexible_template("marketplace/index.html", products=products)

@bp.route("/marketplace/product/<int:pid>")
@login_required
def marketplace_product(pid):
    p = Product.query.get_or_404(pid)
    return render_flexible_template("marketplace/product.html", product=p)

# Add to cart (POST)
@bp.route("/marketplace/cart/add", methods=["POST"])
@login_required
def cart_add():
    pid = int(request.form.get("product_id"))
    qty = int(request.form.get("qty", 1))
    p = Product.query.get_or_404(pid)
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
    if item:
        item.qty += qty
    else:
        item = CartItem(user_id=current_user.id, product_id=pid, qty=qty)
        db.session.add(item)
    db.session.commit()
    flash("Added to cart", "success")
    return redirect(url_for("main.marketplace_index"))

@bp.route("/marketplace/cart")
@login_required
def cart_view():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum((it.product.price or 0) * it.qty for it in items)
    return render_flexible_template("marketplace/cart.html", items=items, total=total)

@bp.route("/marketplace/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def cart_remove(item_id):
    it = CartItem.query.get_or_404(item_id)
    if it.user_id != current_user.id:
        flash("Not allowed", "danger")
        return redirect(url_for("main.cart_view"))
    db.session.delete(it)
    db.session.commit()
    flash("Removed", "success")
    return redirect(url_for("main.cart_view"))

# Checkout: deduct wallet and create order (prototype: instant success)
@bp.route("/marketplace/checkout", methods=["POST"])
@login_required
def marketplace_checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash("Cart empty", "danger")
        return redirect(url_for("main.cart_view"))
    total = sum((it.product.price or 0) * it.qty for it in items)

    user_balance = getattr(current_user, "wallet_balance", 0) or 0
    if user_balance < total:
        flash("Insufficient wallet balance. Top up to continue.", "danger")
        return redirect(url_for("main.wallet"))

    # create order and transfer funds
    order = MarketplaceOrder(user_id=current_user.id, total=total, status="paid")
    current_user.wallet_balance = user_balance - total

    # (simulate) create external_order_id
    order.external_order_id = f"SIM-{secrets.token_urlsafe(6)}"
    db.session.add(order)

    # remove cart items
    for it in items:
        db.session.delete(it)

    db.session.commit()
    flash("Order placed successfully", "success")
    return redirect(url_for("main.marketplace_order", oid=order.id))

@bp.route("/marketplace/order/<int:oid>")
@login_required
def marketplace_order(oid):
    order = MarketplaceOrder.query.get_or_404(oid)
    if order.user_id != current_user.id and not getattr(current_user, "is_admin", False):
        flash("Not authorized", "danger")
        return redirect(url_for("main.dashboard"))
    return render_flexible_template("marketplace/order.html", order=order)

# Admin product manage (admin guard)
@bp.route("/admin/marketplace/products")
@admin_required
def admin_products():
    products = Product.query.all()
    return render_flexible_template("admin/marketplace_products.html", products=products)

@bp.route("/admin/marketplace/product/create", methods=["GET", "POST"])
@admin_required
def admin_create_product():
    if request.method == "POST":
        title = request.form.get("title")
        price = float(request.form.get("price", 0))
        desc = request.form.get("description")
        img = request.form.get("image")  # just a filename for prototype
        p = Product(title=title, price=price, description=desc, image=img, in_stock=True)
        db.session.add(p)
        db.session.commit()
        flash("Product created", "success")
        return redirect(url_for("main.admin_products"))
    return render_flexible_template("admin/create_product.html")