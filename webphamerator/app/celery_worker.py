from webphamerator.app.flask_app import create_app
from webphamerator.app.celery_ext import (celery_app, celery_utils)

app = create_app()

celery = celery_app.celery
celery_utils.init_celery(celery, app)
