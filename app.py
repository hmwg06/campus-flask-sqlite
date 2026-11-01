"""Flask entry point. Run directly or from PyCharm."""
import os
import secrets
from pathlib import Path

from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(exist_ok=True)
    key_path = Path(app.instance_path) / 'secret.key'
    if not key_path.exists():
        try:
            with key_path.open('x', encoding='utf-8') as file:
                file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY') or key_path.read_text(encoding='utf-8'),
        DATABASE=str(Path(app.instance_path) / 'campus.sqlite3'),
        UPLOAD_FOLDER=str(Path(app.instance_path) / 'uploads'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
    )
    if test_config:
        app.config.update(test_config)
    from campus import db, views
    db.init_app(app)
    app.register_blueprint(views.bp)
    with app.app_context():
        db.init_db()
    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=False)
