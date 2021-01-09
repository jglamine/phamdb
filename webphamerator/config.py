import os
basedir = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = (
                    "mysql+pymysql://root:phage@localhost/webphamerate")
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, "db_repository")
GENBANK_FILE_DIR = os.path.join(basedir, "genbank_files")
DATABASE_DUMP_DIR = os.path.join(basedir, "database_dumps")

INSTALLED_APPS = ["webphamerator.app.celery_ext.tasks"]
CELERY_BROKER_URI = "amqp://guest:guest@localhost:5672//"
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERYD_CONCURRENCY = 1

# replace this in production
SECRET_KEY = 'override in production'
SECRET_KEY = 'xYQ8Asv9Ie9Y2XDNfIorkj0l'
SECRET_KEY = 'ULZH8hJfSNflNvtWjBsn.sw5'
