from flask import (
        render_template, abort, request, url_for, redirect,
        send_from_directory, make_response, session, current_app, Blueprint)
from webphamerator.flask import models, auth
from webphamerator.flask.models import db
from webphamerator.flask.tasks import celery as celery_ext
import pham.db
import os
import io

bp = Blueprint("views", __name__)


def get_navbar(active_url, ignore_done=False):
    queued_and_running = (db.session.query(models.Job).filter(
        models.Job.status_code.in_(('running', 'queued'))).count())
    error = 0
    success = 0
    if not ignore_done:
        error = (db.session.query(models.Job)
                 .filter(not models.Job.seen)
                 .filter(models.Job.status_code == 'failed')
                 .count())
        success = (db.session.query(models.Job)
                   .filter(not models.Job.seen)
                   .filter(models.Job.status_code == 'success')
                   .count())

    navbar = list()
    navbar.append(NavbarItem('Databases', '/databases'))
    navbar.append(NavbarItem('Create Database', '/databases/new'))
    navbar.append(NavbarItem('Import Database', '/databases/import'))
    navbar.append(NavbarItem('Settings', '/settings', right_side=True))
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
                 error=None,
                 right_side=False):
        self.title = title
        self.url = url
        self.active = active
        self.info = info
        self.success = success
        self.error = error
        self.right_side = right_side


@bp.route('/')
@bp.route('/index')
@bp.route('/databases')
def databases():
    dbs = (db.session.query(models.Database).filter(
        models.Database.visible is True).order_by(
                                        models.Database.display_name).all())

    return render_template('databases.html',
                           title='Databases',
                           databases=dbs,
                           navbar=get_navbar('/databases'))


class PhageViewModel(object):
    def __init__(self, name=None, id=None, genes=None, url=None):
        self.name = name
        self.id = id
        self.genes = genes
        self.url = url

    def to_dict(self):
        return self.__dict__


@bp.route('/databases/<int:db_id>', methods=['GET'])
def database(db_id):
    database = (db.session.query(models.Database).filter(
                                    models.Database.visible).filter(
                                        models.Database.id == db_id).first())

    if database is None:
        abort(404)

    percent_orphams = 0
    if database.number_of_phams != 0:
        orphams = database.number_of_orphams
        phams = database.number_of_phams
        if orphams is None:
            orphams = 0
        if phams is None:
            phams = 0
        percent_orphams = (float(orphams) / float(phams)) * 100
        percent_orphams = round(percent_orphams, 1)

    server_url = request.url_root + 'db/'

    server = pham.db.DatabaseServer.from_url(
                                current_app.config['SQLALCHEMY_DATABASE_URI'])
    phage_view_models = []
    for phage in pham.db.list_organisms(server, database.mysql_name()):
        phage_view_models.append(PhageViewModel(
                                 id=phage.id,
                                 name=phage.name,
                                 genes=phage.genes,
                                 url='/databases/{}/phage/{}'.format(
                                     database.id, phage.id)))

    return render_template(
                        'database.html',
                        title='Database - {}'.format(database.display_name),
                        database=database,
                        percent_orphams=percent_orphams,
                        server_url=server_url,
                        sql_dump_filename='{}.sql'.format(database.name_slug),
                        phages=phage_view_models,
                        navbar=get_navbar('/databases'))


@bp.route('/databases/<int:db_id>', methods=['POST'])
def delete_database(db_id):
    db_record = (db.session.query(models.Database)
                 .filter(models.Database.id == db_id)
                 .first())
    if db_record is None:
        abort(404)
        return

    if request.form.get('delete') not in ['true', 'True']:
        return redirect(url_for('database', db_id=db_id), code=303)

    if db_record.locked:
        return redirect(url_for('database', db_id=db_id), code=303)

    server = pham.db.DatabaseServer.from_url(
                                current_app.config['SQLALCHEMY_DATABASE_URI'])
    pham.db.delete(server, db_record.mysql_name())
    db.session.delete(db_record)
    db.session.commit()
    return redirect(url_for('databases'), code=302)


@bp.route('/databases/<int:db_id>/edit', methods=['GET'])
def edit_database(db_id):
    database = (db.session.query(models.Database)
                .filter(models.Database.visible)
                .filter(models.Database.id == db_id)
                .first()
                )

    if database is None:
        abort(404)

    server = pham.db.DatabaseServer.from_url(
                                current_app.config['SQLALCHEMY_DATABASE_URI'])
    phage_view_models = []
    for phage in pham.db.list_organisms(server, database.mysql_name()):
        phage_view_models.append(PhageViewModel(
                                 id=phage.id,
                                 name=phage.name,
                                 genes=phage.genes
                                 ))

    return render_template(
                    'edit-database.html',
                    title='Edit Database - {}'.format(database.display_name),
                    database=database,
                    phages=[phage.to_dict() for phage in phage_view_models],
                    navbar=get_navbar('/databases'))


@bp.route('/databases/<int:db_id>/phage/<phage_id>', methods=['GET'])
def download_genbank_file(db_id, phage_id):
    db_record = (db.session.query(models.Database).filter(
                                    models.Database.visible).filter(
                                        models.Database.id == db_id).first())

    if db_record is None:
        abort(404)

    # export genbank file
    server = pham.db.DatabaseServer.from_url(
                                current_app.config['SQLALCHEMY_DATABASE_URI'])
    handle = io.StringIO()
    try:
        phage = pham.db.export_to_genbank(server, db_record.mysql_name(),
                                          phage_id,
                                          handle)
    except pham.db.DatabaseDoesNotExistError:
        return abort(404)
    except pham.db.PhageNotFoundError:
        return abort(404)

    response = make_response(handle.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename={}'.format(
                                                            phage.name + '.gb')
    return response


@bp.route('/jobs', methods=['GET'])
def jobs():
    return jobs_page(1)


@bp.route('/jobs/page/<int:page>')
def jobs_page(page):
    if page == 0:
        return abort(404)

    page_size = 8
    jobs = (db.session.query(models.Job).order_by(
            models.Job.modified.desc()).limit(page_size).offset(
                                                    page_size * (page - 1)))
    total_jobs = db.session.query(models.Job).count()
    next_page = None
    prev_page = None
    if page * page_size < total_jobs:
        next_page = page + 1
    if page > 1:
        prev_page = page - 1
        if prev_page == 0:
            prev_page = ''

    title = 'Jobs'
    if page != 1:
        title += ' (page {} of {})'.format(page, total_jobs / page_size + 1)

    view = render_template('jobs.html',
                           title=title,
                           jobs=jobs,
                           page=page,
                           next_page=next_page,
                           prev_page=prev_page,
                           navbar=get_navbar('/jobs', ignore_done=True))

    for job in jobs:
        if not job.seen:
            job.seen = True
    db.session.commit()

    return view


@bp.route('/jobs', methods=['POST'])
def cancel_all_jobs():
    if request.form.get('cancel-all') not in ['true', 'True']:
        return redirect(url_for('jobs'), code=303)

    celery_ext.celery.control.purge()
    # kill currently running tasks
    running_jobs = (db.session.query(models.Job)
                    .filter(models.Job.status_code == 'running').all())
    running_job_ids = [job.task_id for job in running_jobs]
    celery_ext.celery.control.revoke(running_job_ids, terminate=True)

    # delete job entries
    jobs = (db.session.query(models.Job)
            .filter(models.Job.status_code.in_(('running', 'queued')))
            .all())

    # delete database entries
    database_ids = [
                job.database_id for job in jobs if job.type_code == 'create']
    if len(database_ids):
        (db.session.query(models.Database)
         .filter(models.Database.id.in_(database_ids))
         .delete(synchronize_session='fetch'))

    for job in jobs:
        db.session.delete(job)

    # unlock all databases
    (db.session.query(models.Database)
     .filter(models.Database.locked)
     .update({'locked': False}))

    db.session.commit()

    return redirect(url_for('jobs'), code=302)


@bp.route('/jobs/<int:job_id>', methods=['GET'])
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


@bp.route('/jobs/<int:job_id>', methods=['POST'])
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


@bp.route('/databases/new')
def create_database():
    return render_template('create-database.html',
                           title='Create Database',
                           navbar=get_navbar('/databases/new'))


@bp.route('/databases/import')
def import_database():
    return render_template('import-database.html',
                           title='Import Database from SQL File',
                           navbar=get_navbar('/databases/import'))


@bp.route('/signin', methods=['GET'])
def signin_page():
    errors = session.get('errors', [])
    if len(errors):
        del session['errors']

    return render_template('signin.html',
                           title='Sign In',
                           errors=errors,
                           navbar=[])


@bp.route('/signin', methods=['POST'])
def sign_in():
    password = request.form.get('password')
    if password is not None:
        password = password.strip()
        success = auth.authenticate(password)
        if success:
            return redirect('/')

    session['errors'] = ['Incorrect password.']
    return redirect('/signin')


@bp.route('/signout', methods=['POST'])
def sign_out():
    auth.sign_out()
    return redirect(url_for('databases'))


@bp.route('/settings', methods=['GET'])
def settings():
    successes = session.get('successes', [])
    if len(successes):
        del session['successes']
    errors = session.get('errors', [])
    if len(errors):
        del session['errors']

    return render_template('settings.html',
                           title='Settings',
                           successes=successes,
                           errors=errors,
                           navbar=get_navbar('/settings'),
                           password_required=auth.is_password_required())


@bp.route('/settings', methods=['POST'])
def update_settings():
    errors = []
    successes = []

    # set password
    password = request.form.get('password')
    if password is not None:
        password = password.strip()
        if password == '':
            password = None
            errors.append('Password must not be blank.')

    if password is not None:
        auth.set_password(password)
        successes.append('Password updated.')

    # delete password
    if request.form.get('delete-password') == 'true':
        auth.delete_password()
        successes.append('Password deleted.')

    session['errors'] = errors
    session['successes'] = successes

    return redirect(url_for('settings'))

    @bp.route('/db/<path:path>')
    def download_database(path):
        return send_from_directory(
                            current_app.config['DATABASE_DUMP_DIR'], path)


@bp.route('/db')
def database_root():
    """Phamerator GETs this route to verify that a database URL is correct.
    """
    return '', 200
