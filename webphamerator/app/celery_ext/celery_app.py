from celery import (Celery)

from webphamerator import config
# from werkzeug.local import LocalProxy
# from celery.utils import imports as celery_import


def make_celery(app_name=__name__):
    return Celery(app_name, broker=config.CELERY_BROKER_URI)


celery = make_celery()
