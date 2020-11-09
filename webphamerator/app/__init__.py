import os
from flask import (Flask)
from webphamerator.app import (
                    filters, auth, views, api, celery_ext, sqlalchemy_ext)
from webphamerator.app.celery_ext import tasks


def create_app():
    app = Flask(__name__)

    app.config.from_object("webphamerator.config")

    if not os.path.exists(app.config['GENBANK_FILE_DIR']):
        os.makedirs(app.config['GENBANK_FILE_DIR'])
    if not os.path.exists(app.config['DATABASE_DUMP_DIR']):
        os.makedirs(app.config['DATABASE_DUMP_DIR'])

    with app.app_context():
        sqlalchemy_ext.db.init_app(app)
        celery_ext.init_app(celery_ext.celery, app)
        tasks.database_farmer.init_app(app, celery_ext.celery)

        app.jinja_env.filters["replaceifequal"] = filters.replaceifequal
        app.jinja_env.filters["humandate"] = filters.humandate
        app.jinja_env.filters["isodate"] = filters.isodate
        app.jinja_env.filters["toclocktime"] = filters.isodate

        app.register_blueprint(auth.bp)
        app.register_blueprint(api.bp)
        app.register_blueprint(views.bp)

        app.context_processor(auth.template_context)

    if not app.debug:
        import logging
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler('webphamerator.log', 'a',
                                           1 * 1024 * 1024, 10)
        file_handler.setFormatter(
                        logging.Formatter(
                                "%(asctime)s %(levelname)s: %(message)s "
                                "[in %(pathname)s:%(lineno)d]"))
        app.logger.setLevel(logging.INFO)
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

    return app
