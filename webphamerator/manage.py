from flask import current_app

from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

from webphamerator.flask.models import *

migrate = Migrate(current_app, db)

manager = Manager(current_app)
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
