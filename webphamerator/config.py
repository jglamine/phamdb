import os
basedir = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root@localhost/webphamerate'
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')
GENBANK_FILE_DIR = os.path.join(basedir, 'genbank_files')
DATABASE_DUMP_DIR = os.path.join(basedir, 'database_dumps')

if not os.path.exists(GENBANK_FILE_DIR):
    os.makedirs(GENBANK_FILE_DIR)
if not os.path.exists(DATABASE_DUMP_DIR):
    os.makedirs(DATABASE_DUMP_DIR)

CELERY_BROKER_URL = 'amqp://guest:guest@localhost:5672//'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERYD_CONCURRENCY = 1

SECRET_KEY = 'XcdnxpdQ3HgvbWPcrQCyy69VYcBYIg8xjs0nx542'
