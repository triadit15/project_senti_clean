import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)

    # SECRET KEY
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev_key")

    # DATABASE CONFIG (Render or local)
    db_url = os.environ.get("DATABASE_URL")

    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///senti.db"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # INIT EXTENSIONS
    db.init_app(app)
    migrate.init_app(app, db)

    # LOGIN MANAGER
    login_manager = LoginManager()
    login_manager.login_view = "main.login"
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # BLUEPRINTS
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    from .marketplace_routes import market
    app.register_blueprint(market)

    from .utility_routes import utility
    app.register_blueprint(utility)

    return app