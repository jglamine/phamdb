import datetime
import os

from flask import (current_app)

import pham
from webphamerator.app.sqlalchemy_ext import models
from webphamerator.app.celery_ext.celery_app import celery as celery_app


class TaskHandler:
    def __init__(self, app=None, celery=None):
        self._app = app
        self._celery = celery

        self._initialized = False

        self._BaseTaskClass = None
        self._CreatorMaker = None
        self._ModifierMaker = None

        self._create = None
        self._modify = None

    def init_app(self, app, celery):
        TaskBase = celery.Task

        self._app = app
        self._celery = celery

        class ContextTask(TaskBase):
            abstract = True

            def __call__(self, *args, **kwargs):
                def __call__(self, *args, **kwargs):
                    with app.app_context():
                        return TaskBase.__call__(self, *args, **kwargs)

        self._context_task_maker = ContextTask
        self.build_bases()
        self.build_createtask()
        self.build_modifytask()
        self._initialized = True

    @property
    def context_task(self, *args, **kwargs):
        if not self._initialized:
            raise NotInitializedError("Task handler has not been initialzied "
                                      "with a Celery or Flask application.")

        return self._context_task_maker(*args, **kwargs)

    @property
    def create_task(self):
        if self._CreatorMaker is None:
            self.build_creatormaker()

        return self._CreatorMaker

    @property
    def modify_task(self):
        if self._ModifierMaker is None:
            self.build_modifiermaker()

        return self._ModifierMaker

    @property
    def create(self):
        if self._create is None:
            self.build_createtask()

        return self._create

    @property
    def modify(self):
        if self._modify is None:
            self.build_modifytask()

        return self._modify

    def build_basemaker(self):
        if self._celery is None:
            raise AttributeError("Task handler missing valid Celery object.")

        class _BaseDatabaseTask(celery_app.Task):
            success_message = None
            type_code = None

            def __init__(self):
                self._server = None

            @property
            def server(self):
                if self._server is None:
                    self._server = pham.db.DatabaseServer.from_url(
                                                current_app.config[
                                                    'SQLALCHEMY_DATABASE_URI'])
                return self._server

            def database_call(self, database_id, genbank_files, organism_ids,
                              cdd_search, callback):
                pass

            def failure_hook(self, database_record, job_record, exception):
                pass

            def _get_job(self, job_id):
                return (models.db.session.query(models.Job)
                        .filter(models.Job.id == job_id)
                        .first())

            def _get_database(self, database_id):
                return (models.db.session.query(models.Database)
                        .filter(models.Database.id == database_id)
                        .first())

            def on_failure(self, exc, task_id, args, kwargs, einfo):
                print("FAILURE")
                job_id = args[0]
                job_record = self._get_job(job_id)
                database_record = self._get_database(job_record.database_id)
                database_record.locked = False
                if job_record.status_code != 'failed':
                    job_record.status_code = 'failed'
                    job_record.status_message = 'An unexpected error occurred.'
                models.db.session.commit()

                self.failure_hook(database_record, job_record, exc)
                self.always(job_record)

            def on_success(self, return_value, task_id, args, kwargs):
                print("SUCCESS")
                job_id = args[0]
                job_record = self._get_job(job_id)
                database_record = self._get_database(job_record.database_id)
                job_record.status_code = 'success'
                job_record.status_message = self.success_message

                database_record.visible = True
                database_record.locked = False
                database_record.created = datetime.datetime.utcnow()
                database_record.modified = datetime.datetime.utcnow()

                summary = pham.db.summary(self.server,
                                          database_record.mysql_name())
                database_record.number_of_organisms = \
                    summary.number_of_organisms
                database_record.number_of_orphams = summary.number_of_orphams
                database_record.number_of_phams = summary.number_of_phams

                self.always(job_record)

            def always(self, job_record):
                if job_record.start_time is None:
                    job_record.runtime = (datetime.datetime.utcnow() -
                                          job_record.modified)
                else:
                    job_record.runtime = (datetime.datetime.utcnow() -
                                          job_record.start_time)
                job_record.modified = datetime.datetime.utcnow()
                job_record.seen = False

                # delete genbank files
                for file_record in job_record.genbank_files_to_add.all():
                    try:
                        os.remove(file_record.filename)
                    except IOError:
                        pass
                    file_record.filename = None

                models.db.session.commit()

        self._BaseTaskClass = _BaseDatabaseTask

    def build_creatormaker(self):
        if self._BaseTaskClass is None:
            self.build_basemaker()

        class CreateDatabase(self._BaseTaskClass):
            success_message = 'Database created.'
            type_code = 'create'

            def database_call(self, database_id, genbank_files, organism_ids,
                              cdd_search, callback):
                print("Creating actual database...")
                return pham.db.create(self.server, database_id,
                                      genbank_files=genbank_files,
                                      cdd_search=cdd_search,
                                      callback=callback)

            def failure_hook(self, database_record, job_record, exception):
                if not isinstance(exception,
                                  pham.db.DatabaseAlreadyExistsError):
                    pham.db.delete(self.server, database_record.mysql_name())
                else:
                    job_record.status_message = 'Database already exists.'
                models.db.session.delete(database_record)

        print("Created database creator...")

        self._CreatorMaker = CreateDatabase

    def build_modifiermaker(self):
        if self._BaseTaskClass is None:
            self.build_basemaker()

        class ModifyDatabase(self._BaseTaskClass):
            success_message = 'Database updated.'
            type_code = 'edit'

            def database_call(self, database_id, genbank_files, organism_ids,
                              cdd_search, callback):
                return pham.db.rebuild(self.server, database_id,
                                       organism_ids_to_delete=organism_ids,
                                       genbank_files_to_add=genbank_files,
                                       cdd_search=cdd_search,
                                       callback=callback)

            def failure_hook(self, database_record, job_record, exception):
                if isinstance(exception, pham.db.DatabaseDoesNotExistError):
                    job_record.status_message = 'Database does not exist.'

        self._ModifierMaker = ModifyDatabase

    def build_createtask(self):
        if self._CreatorMaker is None:
            self.build_creatormaker()

        self._create = self._CreatorMaker()

    def build_modifytask(self):
        if self._ModifierMaker is None:
            self.build_modifiermaker()

        self._modify = self._ModifierMaker()

    def build_bases(self):
        if self._BaseTaskClass is None:
            self.build_basemaker()

        if self._CreatorMaker is None:
            self.build_creatormaker()

        if self._ModifierMaker is None:
            self.build_modifiermaker()


class NotInitializedError(Exception):
    pass
