import datetime
import os
from pathlib import Path

from flask import current_app
from pdm_utils import AlchemyHandler

import pham
from webphamerator.app.sqlalchemy_ext import models
from webphamerator.app.celery_ext.celery_app import celery as celery_app

# GLOBAL VARIABLES
# -----------------------------------------------------------------------------
DB_SUCCESS = "Completed SQL database transcation."
DB_FAILURE = "An unexpected error occurred during SQL database transaction."


# CELERY TASKS
# -----------------------------------------------------------------------------

@celery_app.task()
def create_database(job_id):
    database_task(job_id, "create")


@celery_app.task()
def modify_database(job_id):
    database_task(job_id, "modify")


# DATABASE TASK HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def database_success(job_id):
    job_record = get_job(job_id)
    database_record = get_database(job_record.database_id)
    job_record.status_code = "success"
    job_record.status_message = DB_SUCCESS

    database_record.visible = True
    database_record.locked = False
    database_record.created = datetime.datetime.utcnow()
    database_record.modified = datetime.datetime.utcnow()

    alchemist = get_alchemist()
    summary = pham.db.summary(alchemist,
                              database_record.mysql_name())
    database_record.number_of_organisms = \
        summary.number_of_organisms
    database_record.number_of_orphams = summary.number_of_orphams
    database_record.number_of_phams = summary.number_of_phams
    models.db.session.commit()

    clean_job(job_record)


def database_failure(job_id):
    job_record = get_job(job_id)
    database_record = get_database(job_record.database_id)
    database_record.locked = False
    if job_record.status_code != "failed":
        job_record.status_code = "failed"
        job_record.status_message = DB_FAILURE
    models.db.session.commit()

    # failure_hook(database_record, job_record, exc)
    clean_job(job_record)


def database_task(job_id, task):
    # get job record from the database
    job_record = get_job(job_id)
    database_record = get_database(job_record.database_id)
    job_record.start_time = datetime.datetime.utcnow()
    job_record.modified = datetime.datetime.utcnow()
    job_record.seen = False
    job_record.status_code = 'running'
    job_record.type_code = "create"
    # job_record.task_id = self.request.id

    genbank_paths = [r.filename for r in
                     job_record.genbank_files_to_add.all()]
    organism_ids = [r.organism_id for r in
                    job_record.organism_ids_to_delete.all()]

    # update job and database with status, status_message,
    # start_time, modified
    models.db.session.commit()

    observer = CallbackObserver(job_id)
    alchemist = get_alchemist()

    if task == "create":
        success = pham.db.create(alchemist, database_record.mysql_name(),
                                 genbank_files=genbank_paths,
                                 cdd_search=database_record.cdd_search,
                                 callback=observer.handle_call)
    elif task == "modify":
        success = pham.db.rebuild(alchemist, database_record.mysql_name(),
                                  organism_ids_to_delete=organism_ids,
                                  genbank_files_to_add=genbank_paths,
                                  cdd_search=database_record.cdd_search,
                                  callback=observer.handle_call)

    if not success:
        database_failure(job_id)
        return

    database_success(job_id)

    # export database dump
    path = os.path.join(current_app.config['DATABASE_DUMP_DIR'],
                        database_record.name_slug)
    path = Path(path)

    sql_path = path.with_suffix(".sql")
    md5sum_path = path.with_suffix(".md5sum")
    version_path = path.with_suffix(".version")

    # delete old dump
    try:
        os.remove(sql_path)
    except OSError:
        pass
    try:
        os.remove(md5sum_path)
    except OSError:
        pass
    try:
        os.remove(version_path)
    except OSError:
        pass

    pham.db.export(alchemist, database_record.mysql_name(), sql_path)


# GENERAL HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def clean_job(job_record):
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


def get_alchemist():
    alchemist = AlchemyHandler()
    alchemist.URI = current_app.config["SQLALCHEMY_DATABASE_URI"]

    return alchemist


def get_job(job_id):
    return (models.db.session.query(models.Job)
            .filter(models.Job.id == job_id)
            .first())


def get_database(database_id):
    return (models.db.session.query(models.Database)
            .filter(models.Database.id == database_id)
            .first())


class CallbackObserver(object):
    def __init__(self, job_id):
        self.job_id = job_id

    def handle_call(self, code, *args, **kwargs):
        job_record = models.db.session.query(models.Job).filter(
                                        models.Job.id == self.job_id).first()
        if code == pham.db.CallbackCode.status:
            message = args[0]
            step = args[1]
            total_steps = args[2]
            job_record.status_message = '{} ({}/{})'.format(
                                                message, step, total_steps)
        else:
            # only report the first error
            if job_record.status_code != 'failed':
                message = pham.db.message_for_callback(code, *args, **kwargs)
                job_record.status_message = message
                job_record.status_code = 'failed'
        models.db.session.commit()
