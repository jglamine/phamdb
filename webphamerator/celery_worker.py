from webphamerator.app import create_app
from webphamerator.app.celery_ext import (celery, init_celery)
app = create_app()
init_celery(celery, app)
