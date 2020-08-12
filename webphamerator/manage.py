from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

from webphamerator.flask.models import *

migrate = Migrate()
manager = Manager()

if __name__ == '__main__':
    manager.run()
