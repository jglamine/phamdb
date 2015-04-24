from flask import render_template, abort, request, url_for, redirect, send_from_directory, send_file
from webphamerator.app import app, db, models, celery
import pham.db
import os
import tempfile
from contextlib import closing

def get_navbar(active_url, ignore_done=False):
    queued_and_running = (db.session.query(models.Job)
                           .filter(models.Job.status_code.in_(('running', 'queued')))
                           .count())
    error = 0
    success = 0
    if not ignore_done:
        error = (db.session.query(models.Job)
                  .filter(models.Job.seen == False)
                  .filter(models.Job.status_code == 'failed')
                  .count())
        success = (db.session.query(models.Job)
                    .filter(models.Job.seen == False)
                    .filter(models.Job.status_code == 'success')
                    .count())

    navbar = []
    navbar.append(NavbarItem('Databases', '/databases'))
    navbar.append(NavbarItem('Create Database', '/databases/new'))
    navbar.append(NavbarItem('Jobs', '/jobs',
                  info=queued_and_running, success=success, error=error))

    for item in navbar:
        if item.url == active_url:
            item.active = True

    return navbar

class NavbarItem(object):
    def __init__(self, title, url,
                 active=False,
                 info=None,
                 success=None,
                 error=None):
        self.title = title
        self.url = url
        self.active = active
        self.info = info
        self.success = success
        self.error = error

@app.route('/')
@app.route('/index')
@app.route('/databases')
def databases():
    databases = (db.session.query(models.Database)
                    .filter(models.Database.visible == True)
                    .order_by(models.Database.display_name)
                    .all()
                )

    return render_template('databases.html',
                           title='Databases',
                           databases=databases,
                           navbar=get_navbar('/databases'))

class PhageViewModel(object):
    def __init__(self, name=None, id=None, genes=None, url=None):
        self.name = name
        self.id = id
        self.genes = genes
        self.url = url

    def to_dict(self):
        return self.__dict__

@app.route('/databases/<int:db_id>', methods=['GET'])
def database(db_id):
    database = (db.session.query(models.Database)
                .filter(models.Database.visible == True)
                .filter(models.Database.id == db_id)
                .first()
                )

    if database is None:
        abort(404)

    server_url = request.url_root + 'db'

    server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
    phage_view_models = []
    for phage in pham.db.list_organisms(server, database.mysql_name()):
        phage_view_models.append(PhageViewModel(
                                 id=phage.id,
                                 name=phage.name,
                                 genes=phage.genes,
                                 url='/databases/{}/phage/{}'.format(database.id, phage.id)
                                 ))

    return render_template('database.html',
                           title='Database - {}'.format(database.display_name),
                           database=database,
                           server_url=server_url,
                           sql_dump_filename='{}.sql'.format(database.name_slug),
                           phages=phage_view_models,
                           navbar=get_navbar('/databases'))

@app.route('/databases/<int:db_id>', methods=['POST'])
def delete_database(db_id):
    db_record = (db.session.query(models.Database)
                 .filter(models.Database.id == db_id)
                 .first())
    if db_record is None:
        abort(404)
        return

    if request.form.get('delete') not in ['true', 'True']:
        return redirect(url_for('database', db_id=db_id), code=303)

    if db_record.locked == True:
        return redirect(url_for('database', db_id=db_id), code=303)

    server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
    pham.db.delete(server, db_record.mysql_name())
    db.session.delete(db_record)
    db.session.commit()
    return redirect(url_for('databases'), code=302)

@app.route('/databases/<int:db_id>/edit', methods=['GET'])
def edit_database(db_id):
    database = (db.session.query(models.Database)
                .filter(models.Database.visible == True)
                .filter(models.Database.id == db_id)
                .first()
                )

    if database is None:
        abort(404)

    server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
    phage_view_models = []
    for phage in pham.db.list_organisms(server, database.mysql_name()):
        phage_view_models.append(PhageViewModel(
                                 id=phage.id,
                                 name=phage.name,
                                 genes=phage.genes
                                 ))

    return render_template('edit-database.html',
                           title='Edit Database - {}'.format(database.display_name),
                           database=database,
                           phages=[phage.to_dict() for phage in phage_view_models],
                           navbar=get_navbar('/databases'))


@app.route('/databases/<int:db_id>/phage/<phage_id>', methods=['GET'])
def download_genbank_file(db_id, phage_id):
    db_record = (db.session.query(models.Database)
                .filter(models.Database.visible == True)
                .filter(models.Database.id == db_id)
                .first()
                )

    if db_record is None:
        abort(404)

    # export genbank file
    server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
    with tempfile.NamedTemporaryFile(delete=False, prefix='phage-download-') as file_handle:
        filename = file_handle.name
        try:
            phage = pham.db.export_to_genbank(server, db_record.mysql_name(),
                                              phage_id,
                                              file_handle)
        except pham.db.DatabaseDoesNotExistError as e:
            return abort(404)
        except pham.db.PhageNotFoundError as e:
            return abort(404)

    return send_file(filename, as_attachment=True,
                     attachment_filename=phage.name + '.gb', cache_timeout=1)

@app.route('/jobs')
def jobs():
    jobs = (db.session.query(models.Job)
                .order_by(models.Job.modified.desc())
            )

    view = render_template('jobs.html',
                           title='Jobs',
                           jobs=jobs,
                           navbar=get_navbar('/jobs', ignore_done=True))

    for job in jobs:
        if not job.seen:
            job.seen = True
    db.session.commit()

    return view

@app.route('/jobs', methods=['POST'])
def cancel_all_jobs():
    if request.form.get('cancel-all') not in ['true', 'True']:
        return redirect(url_for('jobs'), code=303)

    celery.control.purge()
    # kill currently running tasks
    running_jobs = (db.session.query(models.Job)
            .filter(models.Job.status_code == 'running')
            .all())
    running_job_ids = [job.task_id for job in running_jobs]
    celery.control.revoke(running_job_ids, terminate=True)

    # delete job entries
    jobs = (db.session.query(models.Job)
            .filter(models.Job.status_code.in_(('running', 'queued')))
            .all())

    # delete database entries
    database_ids = [job.database_id for job in jobs if job.type_code == 'create']
    if len(database_ids):
        (db.session.query(models.Database)
         .filter(models.Database.id.in_(database_ids))
         .delete(synchronize_session='fetch'))

    for job in jobs:
        db.session.delete(job)

    # unlock all databases
    (db.session.query(models.Database)
     .filter(models.Database.locked == True)
     .update({'locked': False}))

    db.session.commit()

    return redirect(url_for('jobs'), code=302)

@app.route('/jobs/<int:job_id>', methods=['GET'])
def job(job_id):
    job = db.session.query(models.Job).filter(models.Job.id == job_id).first()

    if job is None:
        abort(404)

    if not job.seen:
        job.seen = True
        db.session.commit()

    runtime = None
    if job.runtime is not None:
        runtime = job.runtime.total_seconds() * 1000

    start_time = job.start_time
    if start_time is None:
        start_time = job.modified

    return render_template('job.html',
                           title='Job - {}'.format(job.database_name),
                           job=job,
                           start_time=start_time,
                           end_time=job.modified,
                           runtime=runtime,
                           phages_to_add=job.genbank_files_to_add.all(),
                           phages_to_remove=job.organism_ids_to_delete.all(),
                           navbar=get_navbar('/jobs'))

@app.route('/jobs/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    job = db.session.query(models.Job).filter(models.Job.id == job_id).first()

    if job is None:
        return redirect(url_for('jobs'))

    if request.form.get('delete') not in ['true', 'True']:
        return redirect(url_for('job', job_id=job_id))

    if job.status_code in ['queued', 'running']:
        return redirect(url_for('job', job_id=job_id))

    # delete genbank files
    for file_record in job.genbank_files_to_add.all():
        if file_record.filename is not None:
            try:
                os.remove(file_record.filename)
            except IOError:
                pass

    db.session.delete(job)
    db.session.commit()

    return redirect(url_for('jobs'))

@app.route('/databases/new')
def create_database():
    return render_template('create-database.html',
                           title='Create Database',
                           navbar=get_navbar('/databases/new'))

@app.route('/db/<path:path>')
def download_database(path):
    return send_from_directory(app.config['DATABASE_DUMP_DIR'], path)

@app.route('/db')
def thing():
    return '', 200
