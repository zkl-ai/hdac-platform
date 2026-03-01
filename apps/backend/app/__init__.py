from flask import Flask
from .config import Config
from .extensions import db, jwt, migrate, socketio
from .routes.auth import auth_bp
from .routes.device import device_bp
from .routes.metrics import metrics_bp
from app.routes.user import user_bp
from .routes.dashboard import dashboard_bp
from .routes.model_library import model_bp
from .routes.surrogate_task import surrogate_bp
from .routes.compress_task import compress_bp
from .routes.gray_deploy_task import deploy_bp
from .routes.dataset import dataset_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # init extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)

    # register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(device_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(model_bp)
    app.register_blueprint(surrogate_bp)
    app.register_blueprint(compress_bp)
    app.register_blueprint(deploy_bp)
    app.register_blueprint(dataset_bp)

    # register sockets
    from app import sockets

    return app
