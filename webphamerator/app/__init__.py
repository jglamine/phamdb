import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from webphamerator.flask import filters, auth, views, api, models, tasks
from celery import Celery


def create_app():
    app = Flask(__name__)

    app.config.from_object('webphamerator.config')

    if not os.path.exists(app.config['GENBANK_FILE_DIR']):
        os.makedirs(app.config['GENBANK_FILE_DIR'])
    if not os.path.exists(app.config['DATABASE_DUMP_DIR']):
        os.makedirs(app.config['DATABASE_DUMP_DIR'])

    models.db.init_app(app)

    app.register_blueprint(filters.bp)

    celery = make_celery(app)

    if not app.debug:
        import logging
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler('webphamerator.log', 'a', 1 * 1024 * 1024, 10)
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        app.logger.setLevel(logging.INFO)
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

def build_celery(a):
    celery = Celery(a.import_name, broker=a.config['CELERY_BROKER_URL'])
    celery.conf.update(a.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask

    return celery



