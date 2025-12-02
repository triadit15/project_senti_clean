
from flask import Blueprint, render_template, request, redirect, flash, url_for
from flask_login import login_required, current_user
from . import db
from .models import UtilityPurchase
import datetime

utility = Blueprint("utility", __name__, url_prefix="/utility")

# UTILITIES HOME
@utility.route("/")
@login_required
def utility_home():
    return render_template("utility/home.html")

# SHOW FORM
@utility.route("/<string:category>")
@login_required
def utility_form(category):
    return render_template("utility/form.html", category=category)

# PROCESS PURCHASE
@utility.route("/buy/<string:category>", methods=["POST"])
@login_required
def utility_buy(category):
    amount = float(request.form.get("amount"))
    details = request.form.get("details")

    if current_user.wallet_balance < amount:
        flash("Insufficient balance", "danger")
        return redirect(url_for("utility.utility_form", category=category))

    # Deduct
    current_user.wallet_balance -= amount

    tx = UtilityPurchase(
        user_id=current_user.id,
        category=category,
        amount=amount,
        details=details,
        created_at=datetime.utcnow()
    )

    db.session.add(tx)
    db.session.commit()

    flash("Utility purchase successful!", "success")

from flask import Blueprint, render_template, request, redirect, flash, url_for
from flask_login import login_required, current_user
from . import db
from .models import UtilityPurchase
import datetime

utility = Blueprint("utility", __name__, url_prefix="/utility")

# UTILITIES HOME
@utility.route("/")
@login_required
def utility_home():
    return render_template("utility/home.html")

# SHOW FORM
@utility.route("/<string:category>")
@login_required
def utility_form(category):
    return render_template("utility/form.html", category=category)

# PROCESS PURCHASE
@utility.route("/buy/<string:category>", methods=["POST"])
@login_required
def utility_buy(category):
    amount = float(request.form.get("amount"))
    details = request.form.get("details")

    if current_user.wallet_balance < amount:
        flash("Insufficient balance", "danger")
        return redirect(url_for("utility.utility_form", category=category))

    # Deduct
    current_user.wallet_balance -= amount

    tx = UtilityPurchase(
        user_id=current_user.id,
        category=category,
        amount=amount,
        details=details,
        created_at=datetime.utcnow()
    )

    db.session.add(tx)
    db.session.commit()

    flash("Utility purchase successful!", "success")

    return redirect(url_for("main.wallet"))