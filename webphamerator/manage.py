from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

from webphamerator.app import create_app
from webphamerator.flask import models


def build_manager():
    app = create_app()

    Migrate(app, models.db)

    manager = Manager(app=app)
    manager.add_command("db", MigrateCommand)

    return manager


if __name__ == '__main__':
    manager = build_manager()
    manager.run()
