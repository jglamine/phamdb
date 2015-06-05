import unittest
import os
import shutil

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

import pham.db
import pham.query
from contextlib import closing
from webphamerator.app import app, db, celery, tasks
from webphamerator.app.models import GenbankFile, Database, Job

class TestDatabaseTasks(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root@localhost/webphamerate_test'
        app.config['GENBANK_FILE_DIR'] = os.path.join(_DATA_DIR, 'temp_genbank')
        app.config['DATABASE_DUMP_DIR'] = os.path.join(_DATA_DIR, 'temp_db_dumps')
        app.config['CELERY_ALWAYS_EAGER'] = True
        app.config['CELERY_EAGER_PROPAGATES_EXCEPTIONS'] = True

        if not os.path.exists(app.config['GENBANK_FILE_DIR']):
            os.makedirs(app.config['GENBANK_FILE_DIR'])
        if not os.path.exists(app.config['DATABASE_DUMP_DIR']):
            os.makedirs(app.config['DATABASE_DUMP_DIR'])

        self.server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
        self.database_names = ['unit test db 1', 'unit test db 2', 'unit test db 3']
        db.create_all()
        celery.conf.update(app.config)

    def _database_exists(self, db_mysql_name):
        with closing(self.server.get_connection()) as cnx:
            return pham.query.database_exists(cnx, db_mysql_name)

    def _ignore_celery_exceptions(self):
        celery.conf.update({'CELERY_EAGER_PROPAGATES_EXCEPTIONS': False})

    def test_modify_database_task(self):
        # create a blank database
        database_record = Database(display_name=self.database_names[0],
                                   name_slug=Database.phamerator_name_for(self.database_names[0]),
                                   description='',
                                   locked=True,
                                   visible=False,
                                   cdd_search=False)
        db.session.add(database_record)
        db.session.commit()
        job_record = Job(database_id=database_record.id,
                         database_name=database_record.display_name,
                         seen=False)
        db.session.add(job_record)
        db.session.commit()

        db_record_id = database_record.id
        job_record_id = job_record.id

        result = tasks.CreateDatabase().delay(job_record.id)

        database_record = db.session.query(Database).filter(Database.id == db_record_id).first()
        job_record = db.session.query(Job).filter(Job.id == job_record_id).first()

        # run the modify job
        job_record = Job(database_id=database_record.id,
                         database_name=database_record.display_name,
                         seen=False)
        db.session.add(job_record)
        db.session.commit()

        # run the task
        result = tasks.ModifyDatabase().delay(job_record.id)

        # check that the job passed
        job_record = db.session.query(Job).filter(Job.id == job_record_id).first()
        database_record = db.session.query(Database).filter(Database.id == db_record_id).first()
        self.assertEqual(job_record.status_code, 'success')
        self.assertTrue(self._database_exists(database_record.mysql_name()))

    def test_create_database_task(self):
        # put a job in the database
        database_record = Database(display_name=self.database_names[0],
                                   name_slug=Database.phamerator_name_for(self.database_names[0]),
                                   description='',
                                   locked=True,
                                   visible=False,
                                   cdd_search=False)
        db.session.add(database_record)
        db.session.commit()
        job_record = Job(database_id=database_record.id,
                         database_name=database_record.display_name,
                         seen=False)
        db.session.add(job_record)
        db.session.commit()

        db_record_id = database_record.id
        job_record_id = job_record.id

        # run the task
        result = tasks.CreateDatabase().delay(job_record.id)

        database_record = db.session.query(Database).filter(Database.id == db_record_id).first()
        job_record = db.session.query(Job).filter(Job.id == job_record_id).first()

        self.assertFalse(database_record.locked)
        self.assertTrue(database_record.visible)
        self.assertIsNotNone(job_record.start_time)
        self.assertIsNotNone(job_record.runtime)
        self.assertIsNotNone(job_record.modified)
        self.assertEqual(job_record.status_code, 'success')
        self.assertTrue(self._database_exists(database_record.mysql_name()))

        # check that the database was exported
        base_path = os.path.join(app.config['DATABASE_DUMP_DIR'], database_record.name_slug)
        self.assertTrue(os.path.exists(base_path + '.sql'))
        self.assertTrue(os.path.exists(base_path + '.version'))
        self.assertTrue(os.path.exists(base_path + '.md5sum'))

        db.session.delete(database_record)
        db.session.commit()

        # test a failing job - database already exists
        self._ignore_celery_exceptions()
        database_record = Database(display_name=self.database_names[0],
                                   name_slug=Database.phamerator_name_for(self.database_names[0]),
                                   description='',
                                   locked=True,
                                   visible=False,
                                   cdd_search=False)
        db.session.add(database_record)
        db.session.commit()
        db_mysql_name = database_record.mysql_name()
        job_record = Job(database_id=database_record.id,
                         database_name=database_record.display_name,
                         seen=False)
        db.session.add(job_record)
        db.session.commit()

        db_record_id = database_record.id
        job_record_id = job_record.id

        result = tasks.CreateDatabase().delay(job_record.id)

        db_count = db.session.query(Database).filter(Database.id == db_record_id).count()
        self.assertEqual(db_count, 0)
        job_record = db.session.query(Job).filter(Job.id == job_record_id).first()

        self.assertIsNotNone(job_record.start_time)
        self.assertIsNotNone(job_record.runtime)
        self.assertIsNotNone(job_record.modified)
        self.assertTrue(self._database_exists(db_mysql_name))
        self.assertEqual(job_record.status_code, 'failed')
        
    def tearDown(self):
        # delete databases
        for name in self.database_names:
            pham.db.delete(self.server, Database.mysql_name_for(name))

        # delete temporary genbank files and database dumps saved on disk
        shutil.rmtree(app.config['GENBANK_FILE_DIR'])
        shutil.rmtree(app.config['DATABASE_DUMP_DIR'])

        db.session.remove()
        db.drop_all()
