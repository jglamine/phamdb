import os
from contextlib import closing
import unittest
import pham.db
import pham.query

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
_TEMP_FILENAME = os.path.join(_DATA_DIR, 'temp-test.gb')
_DB_ID = 'test_database'
_DB_ID_2 = 'test_database_2'

class TestSEAPhageSchema(unittest.TestCase):

    def setUp(self):
        self.server = pham.db.DatabaseServer('localhost', 'root')
        server = pham.db.DatabaseServer('localhost', 'root')
        with closing(server.get_connection()) as cnx:
            with closing(cnx.cursor()) as cursor:
                cursor.execute('DROP DATABASE IF EXISTS {};'.format(_DB_ID))
                cursor.execute('DROP DATABASE IF EXISTS {};'.format(_DB_ID_2))
                cnx.commit()
        self.callbacks = []

    def test_sea_phage_schema(self):
        # import a database distributed by SEA phage
        # From http://phamerator.csm.jmu.edu/sea/
        self.assertFalse(self.database_exists(_DB_ID))
        sql_file = os.path.join(_DATA_DIR, 'Jumbo.sql')
        pham.db.load(self.server, _DB_ID, sql_file)
        self.assertTrue(self.database_exists(_DB_ID))

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

        # export a phage
        organism_id = 'Bellamy-DRAFT'
        phage = pham.db.export_to_genbank(self.server, _DB_ID, organism_id, _TEMP_FILENAME)
        self.assertIsNotNone(phage)
        self.assertTrue(os.path.isfile(_TEMP_FILENAME))

        # read and validate genbank file

        # create databse with phage
        self.assertFalse(self.database_exists(_DB_ID_2))
        pham.db.create(self.server, _DB_ID_2, genbank_files=[_TEMP_FILENAME], cdd_search=False, commit=True,
            callback=self.store_callback)
        self.assertTrue(self.database_exists(_DB_ID_2), self.callbacks)

    def store_callback(self, message_code, *args, **kwargs):
        self.callbacks.append((message_code, args, kwargs))

    def database_exists(self, id):
        with closing(self.server.get_connection()) as cnx:
            return pham.query.database_exists(cnx, id)

    def tearDown(self):
        if os.path.isfile(_TEMP_FILENAME):
            os.remove(_TEMP_FILENAME)