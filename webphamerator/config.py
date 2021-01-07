import os
basedir = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = (
                    "mysql+mysqlconnector://root:phage@localhost/webphamerate")
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
SECRET_KEY = 'SgkXtVs2W6jWYbTVBgTIIwHa'
SECRET_KEY = 'vMxM8DqFBWnOeM31SeoIbT.i'
SECRET_KEY = '4ZZ6r_7.Br02QZnQpUfwGXfI'
SECRET_KEY = 'IpZYBHVKtL06T2SJqgg40n07'
SECRET_KEY = 'i3jPIHJEFZ7P.z6O8yc057mE'
SECRET_KEY = 'KuEEWjOfAjKYpdL6xvSJFkrN'
SECRET_KEY = 'k0CiyGakKBT5SSv91xfNvQ2u'
SECRET_KEY = 'RUy4Yo7UFl7LR.9VaZMdX8xm'
SECRET_KEY = 'fR58qs1h_d.wRrR6cihA6Fu2'
SECRET_KEY = 'h4Johsp4_Ok3rtGqjv999rgu'
SECRET_KEY = 'BwXMYOBvRyR_PLZ76yqbDkzH'
SECRET_KEY = 'aEQollHACtIslTAmUhofD_nN'
SECRET_KEY = 'W7UM2yo5Rb6JDSY0upZF4lve'
SECRET_KEY = 'OD9ndQhIUYLuyJzHleJygP9y'
SECRET_KEY = '8HB8SSeEE2NlKmkR8L4bVs96'
SECRET_KEY = 'NK.tzxpd9q75W5UwQ3qzd8Uu'
SECRET_KEY = 'L8zBXhlXjxBNAdsTaz271VwW'
SECRET_KEY = 'pO2v5LBeXOIJYuFHwispUIPw'
SECRET_KEY = 'MihHIkIIx67doMqVOzhT8fRG'
SECRET_KEY = 'k4A_waLFZ2VlpSrLBgafeAsw'
SECRET_KEY = 'c0jfYUR57L7jWGMOuG_Eq3MN'
SECRET_KEY = 'cb0wUpGSb9l.f6YLBpYHroC6'
SECRET_KEY = 'das0uhn1B6ps2VJOjKeV9Yry'
SECRET_KEY = 'yFDkgp8KJeFu1XPRNe4PSa_s'
SECRET_KEY = 'PYTOO1gbPbXnspoTpSvrXada'
SECRET_KEY = 'ASzChvFDbjZJgKgQYyNuKqwp'
SECRET_KEY = 'rMuC0WT2rsU4e3GEed.oadtE'
SECRET_KEY = '9zZ3ueCTluAq6whKs0B0vuXi'
SECRET_KEY = 'SQsTFGQtkRQaP1wV4txwAo3D'
SECRET_KEY = 'iotrp1Bzy1._3MBQXuCFfaoD'
SECRET_KEY = 'BqyoiQCgrGUvSciAUUGNUIGk'
SECRET_KEY = 'P8tc7BFoYpROMsRR91GzXe2j'
SECRET_KEY = 'ZttjokUtxj6FSTh2OxH.4NqB'
SECRET_KEY = 'Ko9qZIaELMkZ7X0AOPqec_Hl'
SECRET_KEY = '.UL0nHHT5BxsLWCJkOtvLg2J'
SECRET_KEY = 'zK4QGoKhkdgUm_o5o4WFmZDv'
SECRET_KEY = 'SFE_ltvgnjhBR0sYI3qt2Z23'
SECRET_KEY = 'TCBsy35vyKIYweSkhFU2Xu7I'
