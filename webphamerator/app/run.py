from webphamerator.app.flask_app import create_app
from webphamerator.app.celery_ext import celery_app

app = create_app(celery=celery_app.celery)

if __name__ == "__main__":
    app.run(debug=True)
