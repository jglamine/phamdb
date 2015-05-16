import unittest
import os.path
import datetime
import shutil

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

import json
import pham.db
from webphamerator.app import app, db, celery
from webphamerator.app.models import GenbankFile, Database, Job

class TestAddGenbankFile(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root@localhost/webphamerate_test'
        app.config['GENBANK_FILE_DIR'] = os.path.join(_DATA_DIR, 'temp_genbank')
        app.config['CELERY_ALWAYS_EAGER'] = True
        app.config['CELERY_EAGER_PROPAGATES_EXCEPTIONS'] = True
        self.app = app.test_client()
        self.server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
        self.database_names = ['unit test db 1', 'unit test db 2', 'unit test db 3']
        db.create_all()
        celery.conf.update(app.config)

    def test_job_status(self):
        # create a job
        job = Job(
                  status_code='running',
                  status_message='a',
                  modified=datetime.datetime.utcnow(),
                  start_time=datetime.datetime.utcnow(),
                  runtime=datetime.timedelta(minutes=0, seconds=1),
                  )
        db.session.add(job)
        db.session.commit()

        # get its status
        response = self.app.get('/api/jobs/{}'.format(job.id))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.get_data())
        self.assertIsNotNone(data['startTime'])
        self.assertIsNotNone(data['endTime'])
        self.assertEqual(data['elapsedTime'], 1000.0)
        self.assertEqual(data['statusCode'], 'running')
        self.assertEqual(data['statusMessage'], 'a')

        # create a job with all None
        job = Job(
                  status_code='failed',
                  status_message='b',
                  runtime=None,
                  )
        db.session.add(job)
        db.session.commit()

        # get its status
        response = self.app.get('/api/jobs/{}'.format(job.id))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.get_data())
        self.assertIsNone(data['elapsedTime'])
        self.assertEqual(data['statusCode'], 'failed')
        self.assertEqual(data['statusMessage'], 'b')

        # get a nonexistent job
        response = self.app.get('/api/jobs/{}'.format(9000))
        # check for 404
        self.assertEqual(response.status_code, 404)

    def test_create_database(self):
        # create a database with errors
        phage_with_error_path = os.path.join(_DATA_DIR, 'errorfull_phage.gb')
        file_record = GenbankFile(filename=phage_with_error_path)
        db.session.add(file_record)
        db.session.commit()

        post_data = {
            'name': self.database_names[0],
            'description': 'A database.',
            'file_ids': [file_record.id],
            'template': None,
            'cdd_search': False,
            'phages_to_delete': [],
            'phages_from_other_databases': [],
            'test': True
        }
        response = self.app.post('/api/databases',
                                 data=json.dumps(post_data),
                                 content_type='application/json')

        # check response code
        self.assertEqual(response.status_code, 400, response.get_data())
        # check for error messages
        response_data = json.loads(response.get_data())
        self.assertTrue(len(response_data['errors']) > 0)
        # check that no database was created
        databases_found = db.session.query(Database).filter(Database.display_name == post_data['name']).count()
        self.assertEqual(databases_found, 0)

        # create a blank database
        post_data = {
            'name': self.database_names[1],
            'description': 'A blank database.',
            'file_ids': [],
            'template': None,
            'cdd_search': False,
            'phages_to_delete': [],
            'phages_from_other_databases': [],
            'test': True
        }
        response = self.app.post('/api/databases',
                                 data=json.dumps(post_data),
                                 content_type='application/json')
        # check response code
        self.assertEqual(response.status_code, 201, response.get_data())
        # check that database record was created
        databases_found = db.session.query(Database).filter(Database.display_name == post_data['name']).count()
        self.assertEqual(databases_found, 1)
        database_record = db.session.query(Database).filter(Database.display_name == post_data['name']).first()
        self.assertIsNotNone(database_record.name_slug)
        # check for job id
        data = json.loads(response.get_data())
        self.assertIsNotNone(data['job_id'])

        # create a database with phages
        phage_path = os.path.join(_DATA_DIR, 'Filichino-small.gb')
        temp_phage_path = os.path.join(_DATA_DIR, 'temp.gb')
        shutil.copyfile(phage_path, temp_phage_path)
        file_record = GenbankFile(filename=temp_phage_path)
        db.session.add(file_record)
        db.session.commit()
        self.assertIsNone(file_record.job_id)
        file_record_id = file_record.id

        post_data = {
            'name': self.database_names[0],
            'description': 'A database.',
            'file_ids': [file_record.id],
            'template': None,
            'cdd_search': False,
            'phages_to_delete': [],
            'phages_from_other_databases': [],
            'test': False
        }
        response = self.app.post('/api/databases',
                                 data=json.dumps(post_data),
                                 content_type='application/json')
        # check response code
        self.assertEqual(response.status_code, 201, response.get_data())
        # check that database was created
        databases_found = db.session.query(Database).filter(Database.display_name == post_data['name']).count()
        self.assertEqual(databases_found, 1)
        # check that the job_id was set correctly in genbank file
        file_record = db.session.query(GenbankFile).filter(GenbankFile.id == file_record_id).first()
        self.assertIsNotNone(file_record.job_id)

        # create a database with a phage from another database
        db_record = (db.session.query(Database)
                     .filter(Database.display_name == post_data['name'])
                     .first())

        phage_info = {
            'database': db_record.id,
            'id': 'Filichino'
        }
        post_data = {
            'name': self.database_names[2],
            'description': 'A database.',
            'file_ids': [],
            'template': None,
            'cdd_search': False,
            'phages_to_delete': [],
            'phages_from_other_databases': [phage_info],
            'test': False
        }
        response = self.app.post('/api/databases',
                                 data=json.dumps(post_data),
                                 content_type='application/json')

        # check response code
        self.assertEqual(response.status_code, 201, response.get_data())
        # check that database was created
        db_record = db.session.query(Database).filter(Database.display_name == post_data['name']).first()
        self.assertIsNotNone(db_record)
        # check that it contains a phage
        self.assertEqual(1, db_record.number_of_organisms)

        # create a database which already exists
        post_data = {
            'name': self.database_names[0],
            'description': 'A database.',
            'file_ids': [],
            'template': None,
            'cdd_search': False,
            'phages_to_delete': [],
            'phages_from_other_databases': [],
            'test': True
        }
        response = self.app.post('/api/databases',
                                 data=json.dumps(post_data),
                                 content_type='application/json')

        self.assertEqual(response.status_code, 400, response.get_data())

    def test_modify_database(self):
        phage_path = os.path.join(_DATA_DIR, 'Filichino-small.gb')
        temp_phage_path = os.path.join(_DATA_DIR, 'temp.gb')
        shutil.copyfile(phage_path, temp_phage_path)
        file_record = GenbankFile(filename=temp_phage_path)
        db.session.add(file_record)
        db.session.commit()
        self.assertIsNone(file_record.job_id)
        file_record_id = file_record.id

        # modify a database which does not exist
        post_data = {
            'file_ids': [file_record.id],
            'phages_to_delete': [],
            'phages_from_other_databases': [],
            'test': True
        }
        response = self.app.post('/api/database/24601',
                                 data=json.dumps(post_data),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.get_data())
        self.assertTrue(len(response_data['errors']) > 0)

        # create a blank database
        post_data = {
            'name': self.database_names[0],
            'description': 'A database.',
            'file_ids': [],
            'template': None,
            'phages_from_other_databases': [],
            'cdd_search': False,
        }
        response = self.app.post('/api/databases',
                                 data=json.dumps(post_data),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 201)
        database_record = (db.session.query(Database)
                           .filter(Database.display_name == self.database_names[0])
                           .first())
        self.assertIsNotNone(database_record)

        # add a phage
        post_data = {
            'file_ids': [file_record.id],
            'phages_from_other_databases': [],
            'phages_to_delete': []
        }
        response = self.app.post('/api/database/{}'.format(database_record.id),
                                 data=json.dumps(post_data),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.get_data())
        self.assertTrue(len(response_data['errors']) == 0)
        # check number of phages in database record
        database_record = (db.session.query(Database)
                           .filter(Database.display_name == self.database_names[0])
                           .first())
        self.assertIsNotNone(database_record)
        self.assertEqual(database_record.number_of_organisms, 1)

        # import existing phage
        phage_data = {
            'database': database_record.id,
            'id': 'Filichino'
        }
        post_data = {
            'name': self.database_names[2],
            'description': 'A database.',
            'file_ids': [],
            'template': None,
            'phages_from_other_databases': [phage_data],
            'cdd_search': False,
        }
        response = self.app.post('/api/databases',
                                 data=json.dumps(post_data),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 201, response.get_data())
        database_record = (db.session.query(Database)
                           .filter(Database.display_name == self.database_names[2])
                           .first())
        self.assertIsNotNone(database_record)
        self.assertEqual(database_record.number_of_organisms, 1)

        # remove a phage
        post_data = {
            'file_ids': [],
            'phages_from_other_databases': [],
            'phages_to_delete': ['Filichino']
        }
        response = self.app.post('/api/database/{}'.format(database_record.id),
                                 data=json.dumps(post_data),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.get_data())
        self.assertTrue(len(response_data['errors']) == 0)
        # check number of phages in database record
        database_record = (db.session.query(Database)
                           .filter(Database.display_name == self.database_names[2])
                           .first())
        self.assertIsNotNone(database_record)
        self.assertEqual(database_record.number_of_organisms, 0)

    def test_delete_genbank_file(self):
        # create a file
        path = os.path.join(app.config['GENBANK_FILE_DIR'], 'delete-me.gb')
        with open(path, 'w') as handel:
            handel.write('delete me\n')
        file_record = GenbankFile(filename=path)
        db.session.add(file_record)
        db.session.commit()
        id = file_record.id
        self.assertTrue(os.path.exists(path))

        # delete file
        response = self.app.delete('/api/genbankfiles/{}'.format(id))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(os.path.exists(path))
        count = db.session.query(GenbankFile).filter(GenbankFile.id == id).count()
        self.assertEqual(count, 0)

        # delete nonexistant file
        response = self.app.delete('/api/genbankfiles/{}'.format(id))
        self.assertEqual(response.status_code, 404)

        file_record = GenbankFile(filename='/tmp/thispathdoesnotexist.fake')
        db.session.add(file_record)
        db.session.commit()
        id = file_record.id
        response = self.app.delete('/api/genbankfiles/{}'.format(id))
        self.assertEqual(response.status_code, 200)

    def test_database_name_availible(self):
        # add a database to the database
        new_db = Database(display_name='test db',
                          name_slug=Database.phamerator_name_for('test db'))
        db.session.add(new_db)
        db.session.commit()

        # check if free name is taken
        response = self.app.get('/api/database-name-taken',
                                 query_string={
                                 'name': 'test db'
                                 })
        self.assertEqual(response.status_code, 409)

        # check if taken name is taken
        response = self.app.get('/api/database-name-taken',
                                 query_string={
                                 'name': 'another test db'
                                 })
        self.assertEqual(response.status_code, 200)

    def test_add_valid_file(self):
        # upload a valid file
        response = self.upload_file('Filichino-small.gb')

        # make sure it validates
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.get_data())
        phage_data = response_data['phage']
        file_id = phage_data['file_id']
        self.assertIsNotNone(file_id)

        # make sure it creates an entry in the GenbankFile table
        file_record = db.session.query(GenbankFile).filter(GenbankFile.id == file_id).first()
        self.assertIsNotNone(file_record)
        self.assertEqual(file_record.phage_name, phage_data['name'])

        # make sure the file referenced by GenbankFile exists
        self.assertTrue(os.path.exists(file_record.filename))

        # upload an invalid file
        response = self.upload_file('errorfull_phage.gb')

        # make sure it returns errors
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.get_data())
        self.assertTrue(len(data['errors']))
        for error in data['errors']:
            self.assertTrue('line' in error)
            self.assertTrue('message' in error)

        # upload without a file
        response = self.app.post('/api/genbankfiles')
        self.assertEqual(response.status_code, 400)

    def upload_file(self, filename):
        path = os.path.join(_DATA_DIR, filename)
        with open(path, 'r') as handel:
            data = {}
            data['file'] = (handel, filename)
            response = self.app.post('/api/genbankfiles', data=data)
        return response

    def tearDown(self):
        # delete databases
        for name in self.database_names:
            pham.db.delete(self.server, Database.mysql_name_for(name))

        # delete genbank files saved on disk
        folder = app.config['GENBANK_FILE_DIR']
        for filename in os.listdir(folder):
            path = os.path.join(folder, filename)
            if os.path.isfile(path):
                os.unlink(path)

        db.session.remove()
        db.drop_all()
