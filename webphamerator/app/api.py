import os
import tempfile
import shutil
import pham.genbank
import pham.db

import flask
from flask import abort, request
from webphamerator.app import app, db, models, tasks, filters

@app.route('/api/databases', methods=['POST'])
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
    errors = []

    json_data = request.get_json()
    if not 'name' in json_data:
        return 'Missing property \'name\'.', 412
    if not 'description' in json_data:
        return 'Missing property \'description\'', 412
    if not 'file_ids' in json_data:
        return 'Missing property \'file_ids\'.', 412
    if not 'cdd_search' in json_data:
        return 'Missing property: \'cdd_search\'.', 412
    if not 'phages_from_other_databases' in json_data:
        return 'Missing property: \'phages_from_other_databases\'.', 412

    name = json_data.get('name')
    description = json_data.get('description')
    phages_from_other_databases = json_data.get('phages_from_other_databases', [])
    file_ids = json_data.get('file_ids', [])
    test = json_data.get('test', False)

    count = db.session.query(models.Database).filter(models.Database.display_name == name).count()
    if count:
        errors.append('Database name \'{}\' is already in use.'.format(name))

    server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
    file_ids, err = _prepare_genbank_files(server, file_ids, phages_from_other_databases)
    errors += err

    if len(errors):
        return flask.jsonify(errors=errors), 400

    file_records = []
    if len(file_ids):
        file_records = (db.session.query(models.GenbankFile)
                        .filter(models.GenbankFile.id.in_(file_ids))
                        .all())

    genbank_filepaths = [x.filename for x in file_records]

    # create database record
    database_record = models.Database(display_name=name,
                                      name_slug=models.Database.phamerator_name_for(name),
                                      description=description,
                                      locked=True,
                                      visible=False,
                                      cdd_search=json_data['cdd_search'])
    db.session.add(database_record)
    db.session.commit()

    # check database creation transaction for errors
    database_id = database_record.mysql_name()
    success, errors = pham.db.check_create(server, database_id,
                                           genbank_files=genbank_filepaths)

    if not success:
        db.session.delete(database_record)
        db.session.commit()
        return flask.jsonify(errors=errors,
                             job_id=None), 400

    job_record = models.Job(database_id=database_record.id,
                            status_code='queued',
                            status_message='Waiting to run.',
                            database_name=database_record.display_name,
                            seen=False)
    db.session.add(job_record)
    db.session.commit()
    job_id = job_record.id

    if len(file_ids):
        (db.session.query(models.GenbankFile)
            .filter(models.GenbankFile.id.in_(file_ids))
            .update({ models.GenbankFile.job_id: job_record.id },
                    synchronize_session='fetch')
        )
        db.session.commit()

    if not test:
        result = tasks.CreateDatabase().delay(job_id)

    return flask.jsonify(errors=[],
                         job_id=job_id), 201

@app.route('/api/database/<int:database_id>', methods=['POST'])
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
    errors = []

    json_data = request.get_json()
    if not 'file_ids' in json_data:
        return 'Missing property \'file_ids\'.', 412
    if not 'phages_to_delete' in json_data:
        return 'Missing property \'phages_to_delete\'.', 412
    if not 'phages_from_other_databases' in json_data:
        return 'Missing property: \'phages_from_other_databases\'.', 412

    file_ids = json_data.get('file_ids', [])
    phage_ids = json_data.get('phages_to_delete', [])
    phages_from_other_databases = json_data.get('phages_from_other_databases', [])
    description = json_data.get('description')
    test = json_data.get('test', False)

    database_record = (db.session.query(models.Database)
                       .filter(models.Database.id == database_id)
                       .first())
    if database_record is None:
        errors.append('Unable to locate database.')
    elif database_record.locked is True:
        errors.append('This database already has a queued job.')

    server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
    file_ids, err = _prepare_genbank_files(server, file_ids, phages_from_other_databases)
    errors += err

    if len(errors):
        return flask.jsonify(errors=errors), 400

    file_records = []
    if len(file_ids):
        file_records = (db.session.query(models.GenbankFile)
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
    db.session.add(job_record)
    db.session.commit()
    job_id = job_record.id

    for phage_id in phage_ids:
        record = models.JobOrganismToDelete(organism_id=phage_id,
                                            job_id=job_id)
        db.session.add(record)
    if len(phage_ids):
        db.session.commit()

    if len(file_ids):
        (db.session.query(models.GenbankFile)
            .filter(models.GenbankFile.id.in_(file_ids))
            .update({ models.GenbankFile.job_id: job_id },
                    synchronize_session='fetch')
        )
        db.session.commit()

    if not test:
        if description is not None:
            database_record.description = description
        database_record.locked = True
        db.session.commit()
        
        result = tasks.ModifyDatabase().delay(job_id)

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
        file_record_count = (db.session.query(models.GenbankFile)
                             .filter(models.GenbankFile.id.in_(file_ids))
                             .count())
        if len(file_ids) != file_record_count:
            errors.append('{} genbank files failed to upload.'.format(len(file_ids) - file_record_count))

    # copy phages from other databases
    if len(phages_from_other_databases):
        for phage in phages_from_other_databases:
            phage_id = phage['id']
            database_id = phage['database']

            db_record = (db.session.query(models.Database)
                         .filter(models.Database.id == database_id)
                         .first())
            if db_record is None:
                errors.append('Error importing phage `{}` from database `{}`: Database does not exist.'.format(phage_id, database_id))
                continue

            # export genbank file
            with tempfile.NamedTemporaryFile(dir=app.config['GENBANK_FILE_DIR'],
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
                db.session.add(file_record)
                db.session.commit()
                file_ids.append(file_record.id)

    return file_ids, errors

@app.route('/api/database', methods=['GET'])
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
    databases = (db.session.query(models.Database)
                 .filter(models.Database.visible == True)
                 .all())
    database_dictionaries = []
    for database in databases:
        database_dictionaries.append({
                                     'name': database.display_name,
                                     'id': database.id,
                                     'phages': database.number_of_organisms
                                     })

    return flask.jsonify(databases=database_dictionaries), 200

@app.route('/api/database/<int:database_id>/phages', methods=['GET'])
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
    errors = []

    database_record = (db.session.query(models.Database)
                       .filter(models.Database.id == database_id)
                       .first())
    if database_record is None:
        return 'Database with id {} not found.'.format(database_id), 404

    server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
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

@app.route('/api/database-name-taken', methods=['GET'])
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

    count = (db.session.query(models.Database)
             .filter(models.Database.name_slug == name_slug)
             .count()
             )
    if count:
        return abort(409)
    return '', 200

@app.route('/api/genbankfiles/<int:file_id>', methods=['DELETE'])
def delete_genbank_file(file_id):
    """

    status codes:
        200: file deleted
        404: file not found
    """
    file_record = db.session.query(models.GenbankFile).filter(models.GenbankFile.id == file_id).first()
    if file_record is None:
        abort(404)

    path = file_record.filename
    try:
        os.remove(path)
    except OSError:
        pass
    db.session.delete(file_record)
    db.session.commit()
    return '', 200

@app.route('/api/genbankfiles', methods=['POST'])
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
        with tempfile.NamedTemporaryFile(dir=app.config['GENBANK_FILE_DIR'],
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
    db.session.add(file_record)
    db.session.commit()

    phage_data = {
        'file_id': file_record.id,
        'name': phage.name,
        'phage_id': phage.id,
        'number_of_genes': len(phage.genes),
        'length': phage.sequence_length, 
        'gc_content': phage.gc
    }
    
    return flask.jsonify(phage=phage_data), 201

@app.route('/api/jobs/<int:job_id>', methods=['GET'])
def job_status(job_id):
    job = db.session.query(models.Job).filter(models.Job.id == job_id).first()
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
        database_record = (db.session.query(models.Database)
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

@app.route('/api/jobs/<int:job_id>', methods=['POST'])
def mark_job_as_seen(job_id):
    job = db.session.query(models.Job).filter(models.Job.id == job_id).first()
    if job is None:
        abort(404)

    job.seen = True
    db.session.commit()

    return '', 200
