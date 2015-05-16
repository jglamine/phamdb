import datetime
import os
import pham.db
import pham.query
from contextlib import closing
from webphamerator.app import app, db, models, celery

class CallbackObserver(object):
    def __init__(self, job_id):
        self.job_id = job_id

    def handle_call(self, code, *args, **kwargs):
        job_record = db.session.query(models.Job).filter(models.Job.id == self.job_id).first()
        if code == pham.db.CallbackCode.status:
            message = args[0]
            step = args[1]
            total_steps = args[2]
            job_record.status_message = '{} ({}/{})'.format(message, step, total_steps)
        else:
            # only report the first error
            if job_record.status_code != 'failed':
                message = pham.db.message_for_callback(code, *args, **kwargs)
                job_record.status_message = message
                job_record.status_code = 'failed'
        db.session.commit()

class _BaseDatabaseTask(celery.Task):
    abstract = True
    success_message = None
    type_code = None

    def __init__(self):
        self._server = None

    @property
    def server(self):
        if self._server is None:
            self._server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
        return self._server

    def database_call(self, database_id, genbank_files, organism_ids, cdd_search, callback):
        pass

    def failure_hook(self, database_record, job_record, exception):
        pass

    def _get_job(self, job_id):
        return (db.session.query(models.Job)
                .filter(models.Job.id == job_id)
                .first())

    def _get_database(self, database_id):
        return (db.session.query(models.Database)
                .filter(models.Database.id == database_id)
                .first())

    def run(self, job_id):
        # get job record from the database
        job_record = self._get_job(job_id)
        database_record = self._get_database(job_record.database_id)
        job_record.start_time = datetime.datetime.utcnow()
        job_record.modified = datetime.datetime.utcnow()
        job_record.seen = False
        job_record.status_code = 'running'
        job_record.type_code = self.type_code
        job_record.task_id = self.request.id

        genbank_paths = [r.filename for r in job_record.genbank_files_to_add.all()]
        organism_ids = [r.organism_id for r in job_record.organism_ids_to_delete.all()]

        # update job and database with status, status_message, start_time, modified
        db.session.commit()

        observer = CallbackObserver(job_id)
        success = self.database_call(database_record.mysql_name(),
                                     genbank_paths,
                                     organism_ids,
                                     database_record.cdd_search,
                                     observer.handle_call)
        if not success:
            raise RuntimeError

        # export database dump
        path = os.path.join(app.config['DATABASE_DUMP_DIR'], database_record.name_slug)
        # delete old dump
        try:
            os.remove(path + '.sql')
        except OSError:
            pass
        try:
            os.remove(path + '.md5sum')
        except OSError:
            pass
        try:
            os.remove(path + '.version')
        except OSError:
            pass

        pham.db.export(self.server, database_record.mysql_name(), path + '.sql')

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job_id = args[0]
        job_record = self._get_job(job_id)
        database_record = self._get_database(job_record.database_id)
        database_record.locked = False
        if job_record.status_code != 'failed':
            job_record.status_code = 'failed'
            job_record.status_message = 'An unexpected error occurred.'
        db.session.commit()

        self.failure_hook(database_record, job_record, exc)
        self.always(job_record)

    def on_success(self, return_value, task_id, args, kwargs):
        job_id = args[0]
        job_record = self._get_job(job_id)
        database_record = self._get_database(job_record.database_id)
        job_record.status_code = 'success'
        job_record.status_message = self.success_message

        database_record.visible = True
        database_record.locked = False
        database_record.created = datetime.datetime.utcnow()
        database_record.modified = datetime.datetime.utcnow()
        with closing(self.server.get_connection(database=database_record.mysql_name())) as cnx:
            database_record.number_of_organisms = pham.query.count_phages(cnx)
            database_record.number_of_phams = pham.query.count_phams(cnx)

        self.always(job_record)

    def always(self, job_record):
        if job_record.start_time is None:
            job_record.runtime = datetime.datetime.utcnow() - job_record.modified
        else:
            job_record.runtime = datetime.datetime.utcnow() - job_record.start_time
        job_record.modified = datetime.datetime.utcnow()
        job_record.seen = False

        # delete genbank files
        for file_record in job_record.genbank_files_to_add.all():
            try:
                os.remove(file_record.filename)
            except IOError:
                pass
            file_record.filename = None

        db.session.commit()

class CreateDatabase(_BaseDatabaseTask):
    abstract = False
    success_message = 'Database created.'
    type_code = 'create'

    def database_call(self, database_id, genbank_files, organism_ids, cdd_search, callback):
        return pham.db.create(self.server, database_id,
                              genbank_files=genbank_files,
                              cdd_search=cdd_search,
                              callback=callback)

    def failure_hook(self, database_record, job_record, exception):
        if not isinstance(exception, pham.db.DatabaseAlreadyExistsError):
            pham.db.delete(self.server, database_record.mysql_name())
        else:
            job_record.status_message = 'Database already exists.'
        db.session.delete(database_record)

class ModifyDatabase(_BaseDatabaseTask):
    abstract = False
    success_message = 'Database updated.'
    type_code = 'edit'

    def database_call(self, database_id, genbank_files, organism_ids, cdd_search, callback):
        return pham.db.rebuild(self.server, database_id,
                               organism_ids_to_delete=organism_ids,
                               genbank_files_to_add=genbank_files,
                               cdd_search=cdd_search,
                               callback=callback)

    def failure_hook(self, database_record, job_record, exception):
        if isinstance(exception, pham.db.DatabaseDoesNotExistError):
            job_record.status_message = 'Database does not exist.'
