from celery import (Celery)

from webphamerator import config
# from werkzeug.local import LocalProxy
# from celery.utils import imports as celery_import


def make_celery(app_name=__name__):
    return Celery(app_name, broker=config.CELERY_BROKER_URI)


celery = make_celery()


def init_celery(celery, app):
    celery.conf.update(app.config)

    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
