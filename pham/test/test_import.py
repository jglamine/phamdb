import os
import shutil
import tempfile
from contextlib import closing
from nose.tools import ok_, eq_
import unittest
import pham.db
import pham.query
import pham.db_object
import pham.test.util as util

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
_DB_ID = 'test_database'
_DB_ID_2 = 'test_database_2'

class TestDb(unittest.TestCase):

    def setUp(self):
        self.server = pham.db.DatabaseServer('localhost', 'root')
        server = pham.db.DatabaseServer('localhost', 'root')
        with closing(server.get_connection()) as cnx:
            with closing(cnx.cursor()) as cursor:
                cursor.execute('DROP DATABASE IF EXISTS {};'.format(_DB_ID))
                cursor.execute('DROP DATABASE IF EXISTS {};'.format(_DB_ID_2))
                cnx.commit()
        self.callbacks = []

    def test_import_sql(self):
        # import file which does not exist
        self.assertRaises(IOError, pham.db.load, self.server, _DB_ID, 'no such path')
        self.assertFalse(self.database_exists(_DB_ID))

        # import file which is not valid sql
        gb_file = os.path.join(_DATA_DIR, 'Anaya.gb')
        self.assertRaises(ValueError, pham.db.load, self.server, _DB_ID, gb_file)
        self.assertFalse(self.database_exists(_DB_ID))

        # import sql file with wrong schema
        sql_file = os.path.join(_DATA_DIR, 'sql-test-data.sql')
        self.assertRaises(ValueError, pham.db.load, self.server, _DB_ID, sql_file)
        self.assertFalse(self.database_exists(_DB_ID))

        # import valid file with old schema
        sql_file = os.path.join(_DATA_DIR, 'anaya-no-cdd.sql')
        pham.db.load(self.server, _DB_ID, sql_file)

        # check that the gene.cdd_status column was added
        with closing(self.server.get_connection(database=_DB_ID)) as cnx:
            with closing(cnx.cursor()) as cursor:
                cursor.execute('''
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                    AND table_name = 'gene'
                    AND column_name = 'cdd_status'
                            ''')
                self.assertEqual(cursor.fetchall()[0][0], 1)

    def database_exists(self, id):
        with closing(self.server.get_connection()) as cnx:
            return pham.query.database_exists(cnx, id)