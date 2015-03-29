import unittest
import os.path
from contextlib import closing
import pham.db
import pham.query

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

from webphamerator.app import app, db, celery, models

class TestViews(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root@localhost/webphamerate_test'
        app.config['GENBANK_FILE_DIR'] = os.path.join(_DATA_DIR, 'temp_genbank')
        app.config['DATABASE_DUMP_DIR'] = os.path.join(_DATA_DIR, 'temp_db_dumps')
        app.config['CELERY_ALWAYS_EAGER'] = True
        app.config['CELERY_EAGER_PROPAGATES_EXCEPTIONS'] = True
        self.app = app.test_client()
        self.server = pham.db.DatabaseServer.from_url(app.config['SQLALCHEMY_DATABASE_URI'])
        db.create_all()
        celery.conf.update(app.config)
        self.mysql_name = None

    def test_download_database(self):
        with open(os.path.join(app.config['DATABASE_DUMP_DIR'], 'test_file'), 'w') as f:
            f.write('hello') 

        response = self.app.get('/db/test_file')
        self.assertEqual(response.status_code, 200)

    def test_delete_database(self):
        db_name = 'unit_test_new_db'
        # create a blank database
        db_record = models.Database(display_name=db_name,
                                    name_slug=models.Database.phamerator_name_for(db_name),
                                    locked=True,
                                    cdd_search=False)
        db.session.add(db_record)
        db.session.commit()
        mysql_name = db_record.mysql_name()
        self.mysql_name = mysql_name
        db_record_id = db_record.id
        post_data = {'delete': True}

        success = pham.db.create(self.server, mysql_name, cdd_search=False)
        self.assertTrue(success)
        with closing(self.server.get_connection()) as cnx:
            self.assertTrue(pham.query.database_exists(cnx, mysql_name))

        # try to delete a locked database
        response = self.app.post('/databases/{}'.format(db_record.id),
                                 data=post_data)
        self.assertEqual(response.status_code, 303)
        with closing(self.server.get_connection()) as cnx:
            self.assertTrue(pham.query.database_exists(cnx, mysql_name))

        # unlock database
        db_record.locked = False
        db.session.add(db_record)
        db.session.commit()

        # delete it
        response = self.app.post('/databases/{}'.format(db_record.id),
                                 data=post_data)
        self.assertEqual(response.status_code, 302)

        # check that it worked
        with closing(self.server.get_connection()) as cnx:
            self.assertFalse(pham.query.database_exists(cnx, mysql_name))
        found = (db.session.query(models.Database)
                 .filter(models.Database.id == db_record_id)
                 .count())
        self.assertTrue(found == 0)

    def test_kill_all_jobs(self):
        # add a finished job
        # queue three jobs
        # kill all jobs

        # check that finished job is still there
        # check that killed job is gone
        # check that mysql database does not exist

    def tearDown(self):
        # delete db dump files saved on disk
        folder = app.config['DATABASE_DUMP_DIR']
        for filename in os.listdir(folder):
            path = os.path.join(folder, filename)
            if os.path.isfile(path):
                os.unlink(path)

        if self.mysql_name is not None:
            pham.db.delete(self.server, self.mysql_name)

        db.session.remove()
        db.drop_all()
