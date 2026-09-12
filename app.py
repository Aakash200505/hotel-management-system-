import threading
import webbrowser
from flask import Flask
from flask_login import LoginManager
from models import db, User
from routes import init_routes


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'change-this-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'static/images/hotels'
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    init_routes(app)

    with app.app_context():
        db.create_all()
        User.bootstrap_admin()

    return app


app = create_app()


if __name__ == '__main__':
    threading.Timer(1.0, lambda: webbrowser.open_new('http://127.0.0.1:5000')).start()
    app.run(debug=True)
