from webphamerator import app
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

from webphamerator.app.models import *

migrate = Migrate(app.app, app.db)

manager = Manager(app)
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
