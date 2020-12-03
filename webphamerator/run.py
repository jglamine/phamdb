from webphamerator.app import celery_ext, create_app

if __name__ == "__main__":
    app = create_app(celery=celery_ext.celery)
    app.run(debug=True)
