import tempfile
import shutil
import os
import pham.genbank
import pham.db

import flask
from flask import (abort, Blueprint, current_app, request)
from webphamerator.app import sqlalchemy_ext as sqlext
from webphamerator.app import (filters, celery_ext)
from webphamerator.app.sqlalchemy_ext import models
from webphamerator.app.celery_ext import tasks

bp = Blueprint("api", __name__)


@bp.route('/api/databases', methods=['POST'])
def new_database():
    """
    expected POST data:
        {
            name: "",
            description: "",
            file_ids: [],
            phages_from_other_databases: [], // {database: 8, id: 42}
            cdd_search: true,
            test: true // optional
        }


    status codes:
        201: success, job queued
        400: validation error occurred
            response object will contain an 'errors' array.
        412: POST data missing a required property
    """
    # with current_app.app_context():
    database_farmer = tasks.database_farmer

    json_data = request.get_json()
    errors = []

    if 'sql_dump_id' in json_data:
        return import_sql_dump()

    if 'name' not in json_data:
        return 'Missing property \'name\'.', 412
    if 'description' not in json_data:
        return 'Missing property \'description\'', 412
    if 'file_ids' not in json_data:
        return 'Missing property \'file_ids\'.', 412
    if 'cdd_search' not in json_data:
        return 'Missing property: \'cdd_search\'.', 412
    if 'phages_from_other_databases' not in json_data:
        return 'Missing property: \'phages_from_other_databases\'.', 412

    name = json_data.get('name')
    description = json_data.get('description')
    phages_from_other_databases = json_data.get(
                                            'phages_from_other_databases', [])
    file_ids = json_data.get('file_ids', [])
    test = json_data.get('test', False)

    count = sqlext.db.session.query(models.Database).filter(
                                models.Database.display_name == name).count()
    if count:
        errors.append('Database name \'{}\' is already in use.'.format(name))

    server = pham.db.DatabaseServer.from_url(
                                current_app.config['SQLALCHEMY_DATABASE_URI'])
    file_ids, err = _prepare_genbank_files(
                                server, file_ids, phages_from_other_databases)
    errors += err

    if len(errors):
        return flask.jsonify(errors=errors), 400

    file_records = []
    if len(file_ids):
        file_records = (sqlext.db.session.query(models.GenbankFile)
                        .filter(models.GenbankFile.id.in_(file_ids))
                        .all())

    genbank_filepaths = [x.filename for x in file_records]

    # create database record
    database_record = models.Database(
                        display_name=name,
                        name_slug=models.Database.phamerator_name_for(name),
                        description=description, locked=True, visible=False,
                        cdd_search=json_data['cdd_search'])
    sqlext.db.session.add(database_record)
    sqlext.db.session.commit()

    # check database creation transaction for errors
    database_id = database_record.mysql_name()

    success, errors = pham.db.check_create(server, database_id,
                                           genbank_files=genbank_filepaths)

    if not success:
        sqlext.db.session.delete(database_record)
        sqlext.db.session.commit()
        return flask.jsonify(errors=errors,
                             job_id=None), 400

    job_record = models.Job(database_id=database_record.id,
                            status_code='queued',
                            status_message='Waiting to run.',
                            database_name=database_record.display_name,
                            seen=False)
    sqlext.db.session.add(job_record)
    sqlext.db.session.commit()
    job_id = job_record.id

    if len(file_ids):
        (sqlext.db.session.query(models.GenbankFile)
            .filter(models.GenbankFile.id.in_(file_ids))
            .update({models.GenbankFile.job_id: job_record.id},
                    synchronize_session='fetch')
         )
        sqlext.db.session.commit()

    if not test:
        # database_farmer.create.delay(job_id)
        # task = database_farmer.create
        # task.run (job_id)

        # task = celery_ext.celery.task()(tasks.create_database)
        # celery_ext.celery.register_task(task)
        # task(job_id)

        tasks.create_database.delay(job_id)
        print("Queued job...")

    return flask.jsonify(errors=[],
                         job_id=job_id), 201


def import_sql_dump():
    """Create a database from a .sql dump.

    The .sql dump was previously uploaded using the '/api/file' endpoint.
    """
    errors = []
    json_data = request.get_json()

    if 'name' not in json_data:
        return 'Missing property \'name\'.', 412
    if 'description' not in json_data:
        return 'Missing property \'description\'', 412
    if 'sql_dump_id' not in json_data:
        return 'Missing property \'sql_dump_id\'.', 412

    name = json_data.get('name')
    description = json_data.get('description')
    filename = json_data.get('sql_dump_id')
    test = json_data.get('test', False)

    count = sqlext.db.session.query(models.Database).filter(
                                models.Database.display_name == name).count()
    if count:
        errors.append('Database name \'{}\' is already in use.'.format(name))

    if not os.path.isfile(filename):
        errors.append('SQL file not found on server.')

    if len(errors):
        return flask.jsonify(errors=errors), 400

    # create database from sql dump
    server = pham.db.DatabaseServer.from_url(current_app.config['SQLALCHEMY_DATABASE_URI'])
    database_id = models.Database.mysql_name_for(name)

    try:
        pham.db.load(server, database_id, filename)
    except pham.db.DatabaseAlreadyExistsError:
        errors.append('A database with that name already exists.')
    except Exception:
        pham.db.delete(server, database_id)
        errors.append('Invalid database schema.')
    finally:
        if os.path.isfile(filename):
            os.remove(filename)

    if len(errors):
        return flask.jsonify(errors=errors), 400

    database_summary = pham.db.summary(server, database_id)

    # create database record
    database_record = models.Database(display_name=name,
                                      name_slug=models.Database.phamerator_name_for(name),
                                      description=description,
                                      locked=False,
                                      visible=True,
                                      number_of_organisms=database_summary.number_of_organisms,
                                      number_of_orphams=database_summary.number_of_orphams,
                                      number_of_phams=database_summary.number_of_phams,
                                      cdd_search=database_summary.number_of_conserved_domain_hits > 0)
    sqlext.db.session.add(database_record)
    sqlext.db.session.commit()

    # export database dump
    path = os.path.join(current_app.config['DATABASE_DUMP_DIR'], database_record.name_slug)
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

    pham.db.export(server, database_record.mysql_name(), path + '.sql')

    return flask.jsonify(errors=[], database_id=database_record.id), 201


@bp.route('/api/database/<int:database_id>', methods=['POST'])
def modify_database(database_id):
    """
    expected POST data:
        {
            file_ids: [],
            phages_from_other_databases: [], // {database: mydb, id: 42}
            phages_to_delete: [],
            description: "" // optional,
            test: true // optional
        }


    status codes:
        201: success, job queued
        400: validation error occurred
            response object will contain an 'errors' array.
        412: POST data missing a required property
    """
    database_farmer = tasks.database_farmer

    errors = []

    json_data = request.get_json()
    if 'file_ids' not in json_data:
        return 'Missing property \'file_ids\'.', 412
    if 'phages_to_delete' not in json_data:
        return 'Missing property \'phages_to_delete\'.', 412
    if 'phages_from_other_databases' not in json_data:
        return 'Missing property: \'phages_from_other_databases\'.', 412

    file_ids = json_data.get('file_ids', [])
    phage_ids = json_data.get('phages_to_delete', [])
    phages_from_other_databases = json_data.get('phages_from_other_databases', [])
    description = json_data.get('description')
    test = json_data.get('test', False)

    database_record = (sqlext.db.session.query(models.Database)
                       .filter(models.Database.id == database_id)
                       .first())
    if database_record is None:
        errors.append('Unable to locate database.')
    elif database_record.locked is True:
        errors.append('This database already has a queued job.')

    server = pham.db.DatabaseServer.from_url(
                                current_app.config['SQLALCHEMY_DATABASE_URI'])
    file_ids, err = _prepare_genbank_files(server, file_ids,
                                           phages_from_other_databases)
    errors += err

    if len(errors):
        return flask.jsonify(errors=errors), 400

    file_records = []
    if len(file_ids):
        file_records = (sqlext.db.session.query(models.GenbankFile)
                        .filter(models.GenbankFile.id.in_(file_ids))
                        .all())

    genbank_filepaths = [x.filename for x in file_records]

    # check database transaction for errors
    database_id = database_record.mysql_name()
    success, errors = pham.db.check_rebuild(server, database_id,
                                            organism_ids=phage_ids,
                                            genbank_files=genbank_filepaths)

    if not success:
        return flask.jsonify(errors=errors,
                             job_id=None), 400

    job_record = models.Job(database_id=database_record.id,
                            status_code='queued',
                            status_message='Waiting to run.',
                            database_name=database_record.display_name,
                            seen=False)
    sqlext.db.session.add(job_record)
    sqlext.db.session.commit()
    job_id = job_record.id

    for phage_id in phage_ids:
        record = models.JobOrganismToDelete(organism_id=phage_id,
                                            job_id=job_id)
        sqlext.db.session.add(record)
    if len(phage_ids):
        sqlext.db.session.commit()

    if len(file_ids):
        (sqlext.db.session.query(models.GenbankFile)
            .filter(models.GenbankFile.id.in_(file_ids))
            .update({models.GenbankFile.job_id: job_id},
                    synchronize_session='fetch')
         )
        sqlext.db.session.commit()

    if not test:
        if description is not None:
            database_record.description = description
        database_record.locked = True
        sqlext.db.session.commit()

        database_farmer.modify.delay(job_id)

    return flask.jsonify(errors=[],
                         job_id=job_id), 200


def _prepare_genbank_files(server, file_ids, phages_from_other_databases):
    """Checks uploaded genbank files and exports phages from existing databases.

    Returns (file_ids, errors):
        file_ids - a list of file_ids of genbank files to add. Includes newly
            exported files from `phages_from_other_databases`.
        errors - a list of error messages
    """
    errors = []
    if len(file_ids):
        file_record_count = (sqlext.db.session.query(models.GenbankFile)
                             .filter(models.GenbankFile.id.in_(file_ids))
                             .count())
        if len(file_ids) != file_record_count:
            errors.append('{} genbank files failed to upload.'.format(len(file_ids) - file_record_count))

    # copy phages from other databases
    if len(phages_from_other_databases):
        for phage in phages_from_other_databases:
            phage_id = phage['id']
            database_id = phage['database']

            db_record = (sqlext.db.session.query(models.Database)
                         .filter(models.Database.id == database_id)
                         .first())
            if db_record is None:
                errors.append('Error importing phage `{}` from database `{}`: Database does not exist.'.format(phage_id, database_id))
                continue

            # export genbank file
            with tempfile.NamedTemporaryFile(dir=current_app.config['GENBANK_FILE_DIR'],
                                             delete=False) as local_handle:
                local_filename = local_handle.name
                try:
                    phage = pham.db.export_to_genbank(server, db_record.mysql_name(), phage_id, local_handle)
                    file_record = models.GenbankFile(filename=local_filename,
                                                     phage_name=phage.name,
                                                     genes=len(phage.genes),
                                                     gc_content=phage.gc)
                except pham.db.DatabaseDoesNotExistError as e:
                    errors.append('Error importing phage `{}` from database `{}`: Database does not exist.'.format(phage_id, database_id))
                except pham.db.PhageNotFoundError as e:
                    errors.append('Error importing phage `{}` from database `{}`: Phage does not exist.'.format(phage_id, database_id))
            
            # validate exported file
            phage = pham.genbank.read_file(local_filename)
            if len(phage.errors):
                try:
                    os.remove(local_filename)
                except OSError as e:
                    pass
                errors.append('Error importing phage `{}` from database `{}`: Phage data is corrupt.'.format(phage_id, database_id))
                for error in phage.errors:
                    errors.append('Line: {} - {}'.format(error.line_number, error.message()))
            else:
                sqlext.db.session.add(file_record)
                sqlext.db.session.commit()
                file_ids.append(file_record.id)

    return file_ids, errors


@bp.route('/api/database', methods=['GET'])
def list_databases():
    """
    expected response data:
        {
            databases: [
                {
                    name: 'mydb',
                    id: 5,
                    phages: 12
                },
                {
                    name: 'New Database',
                    id: 3,
                    phages: 7
                }
            ]
        }
    """
    databases = (sqlext.db.session.query(models.Database)
                 .filter(models.Database.visible is True)
                 .all())
    database_dictionaries = []
    for database in databases:
        database_dictionaries.append({
                                     'name': database.display_name,
                                     'id': database.id,
                                     'phages': database.number_of_organisms
                                     })

    return flask.jsonify(databases=database_dictionaries), 200


@bp.route('/api/database/<int:database_id>/phages', methods=['GET'])
def list_phages(database_id):
    """
    expected response data:
        {
            phages: [
                {
                    name: 'Anaya',
                    id: '2324axb',
                    genes: 23
                },
                {
                    name: 'myPhage',
                    id: 'myPhage',
                    genes: 284
                }
            ]
        }

    status codes:
        200: success
        500: database error
        404: database does not exist
    """
    errors = list()

    database_record = (sqlext.db.session.query(models.Database)
                       .filter(models.Database.id == database_id)
                       .first())
    if database_record is None:
        return 'Database with id {} not found.'.format(database_id), 404

    server = pham.db.DatabaseServer.from_url(current_app.config['SQLALCHEMY_DATABASE_URI'])
    try:
        phages = pham.db.list_organisms(server, database_record.mysql_name())
    except pham.db.DatabaseDoesNotExistError as e:
        return 'Database with id {} not found.'.format(database_id), 500

    phage_dictionaries = []
    for phage in phages:
        phage_dictionaries.append({
                                    'name': phage.name,
                                    'id': phage.id,
                                    'genes': phage.genes
                                  })

    return flask.jsonify(phages=phage_dictionaries), 200


@bp.route('/api/database-name-taken', methods=['GET'])
def database_name_taken():
    """

    status codes:
        200: name is available
        409: name is not available
    """
    name = request.args.get('name')
    if name is None:
        return abort(400)

    name_slug = models.Database.phamerator_name_for(name)

    count = (sqlext.db.session.query(models.Database)
             .filter(models.Database.name_slug == name_slug)
             .count()
             )
    if count:
        return abort(409)
    return '', 200


@bp.route('/api/genbankfiles/<int:file_id>', methods=['DELETE'])
def delete_genbank_file(file_id):
    """

    status codes:
        200: file deleted
        404: file not found
    """
    file_record = sqlext.db.session.query(models.GenbankFile).filter(models.GenbankFile.id == file_id).first()
    if file_record is None:
        abort(404)

    path = file_record.filename
    try:
        os.remove(path)
    except OSError:
        pass
    sqlext.db.session.delete(file_record)
    sqlext.db.session.commit()
    return '', 200


@bp.route('/api/genbankfiles', methods=['POST'])
def new_genbank_file():
    """

    status codes:
        201: success, file was saved
        400: invalid genbank file
            response object will contain an 'errors' array.
    """
    errors = []

    # get the uploaded data
    file_handle = request.files['file']
    if file_handle is None:
        errors.append('No file uploaded.')
        return flask.jsonify(errors=errors), 400

    local_filename = None
    try:
        # save it to a file
        with tempfile.NamedTemporaryFile(dir=current_app.config['GENBANK_FILE_DIR'],
                                         delete=False) as local_handle:
            local_filename = local_handle.name
            shutil.copyfileobj(file_handle, local_handle)

        # validate it
        phage = pham.genbank.read_file(local_filename)

        if not phage.is_valid():
            os.remove(local_filename)
            local_filename = None

            for error in phage.errors:
                if not error.is_warning():
                    errors.append({
                                  'line': error.line_number,
                                  'message': error.message()
                                  })

            return flask.jsonify(errors=errors), 400

    except:
        if local_filename is not None:
            os.remove(local_filename)
        raise

    # create a database entry for the file
    file_record = models.GenbankFile(filename=local_filename,
                                     phage_name=phage.name,
                                     length=phage.sequence_length,
                                     genes=len(phage.genes),
                                     gc_content=phage.gc
                                     )
    sqlext.db.session.add(file_record)
    sqlext.db.session.commit()

    phage_data = {
        'file_id': file_record.id,
        'name': phage.name,
        'phage_id': phage.id,
        'number_of_genes': len(phage.genes),
        'length': phage.sequence_length, 
        'gc_content': phage.gc
    }
    
    return flask.jsonify(phage=phage_data), 201


@bp.route('/api/file', methods=['POST'])
def upload_file():
    """Upload a file. Used when importing .sql files.

    Response: {
      id: "aaljfalk49tsfasd" // file id
    }

    status codes:
        201: sucess, file was saved
        400: invalid request
    """
    # get the uploaded data
    file_handle = request.files['file']
    if file_handle is None:
        return 'No file uploaded.', 400

    local_filename = None
    try:
        # save it to a file
        with tempfile.NamedTemporaryFile(dir=current_app.config['GENBANK_FILE_DIR'],
                                         delete=False) as local_handle:
            local_filename = local_handle.name
            shutil.copyfileobj(file_handle, local_handle)

    except:
        if local_filename is not None:
            os.remove(local_filename)
        raise

    return flask.jsonify(id=local_filename)


@bp.route('/api/jobs/<int:job_id>', methods=['GET'])
def job_status(job_id):
    job = sqlext.db.session.query(models.Job).filter(
                                            models.Job.id == job_id).first()
    if job is None:
        abort(404)

    elapsed_ms = None
    if job.runtime is not None:
        elapsed_ms = job.runtime.total_seconds() * 1000

    start_time = job.start_time
    if start_time is None:
        start_time = job.modified

    database_url = None
    if job.status_code == 'success':
        database_record = (sqlext.db.session.query(models.Database)
                           .filter(models.Database.id == job.database_id)
                           .first()
                           )
        if database_record is not None:
            database_url = database_record.url()

    return flask.jsonify(
                         statusCode=job.status_code,
                         statusMessage=job.status_message,
                         startTime=filters.isodate(start_time),
                         endTime=filters.isodate(job.modified),
                         elapsedTime=elapsed_ms,
                         databaseUrl=database_url
                         ), 200


@bp.route('/api/jobs/<int:job_id>', methods=['POST'])
def mark_job_as_seen(job_id):
    job = sqlext.db.session.query(models.Job).filter(models.Job.id == job_id).first()
    if job is None:
        abort(404)

    job.seen = True
    sqlext.db.session.commit()

    return '', 200
