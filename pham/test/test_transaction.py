import os
import shutil
import tempfile
from contextlib import closing
from nose.tools import ok_, eq_
import unittest
import pham.db
import pham.query
import pham.test.util as util

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
_DB_ID = 'test_database'
_DB_ID_2 = 'test_database_2'

class TestTransaction(unittest.TestCase):

    def setUp(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        with closing(server.get_connection()) as cnx:
            with closing(cnx.cursor()) as cursor:
                cursor.execute('DROP DATABASE IF EXISTS {};'.format(_DB_ID))
                cursor.execute('DROP DATABASE IF EXISTS {};'.format(_DB_ID_2))
                cnx.commit()
        self.callbacks = []

    def test_transaction(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        db_filename = os.path.join(_DATA_DIR, 'anaya-no-cdd.sql')
        util.import_database(server, _DB_ID, db_filename)

        with closing(server.get_connection(database=_DB_ID)) as cnx:
            # get version
            version = pham.query.version_number(cnx)

        with closing(server.get_connection(database=_DB_ID)) as cnx:

            with closing(cnx.cursor()) as cursor:
                cursor.execute('''
                               UPDATE version
                               SET version=version+1
                               ''')
            cnx.commit()

        with closing(server.get_connection(database=_DB_ID)) as cnx:
            # get version
            new_version = pham.query.version_number(cnx)
        
        #raise Exception
        self.assertEqual(version, new_version)
