import os
import os.path
from nose.tools import ok_, eq_
import unittest
from contextlib import closing
import pham.conserveddomain
import pham.db
import pham.test.util as util

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
_DB_ID = 'test_database'

class TestCddSearch(unittest.TestCase):

    def test_read_xml(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        db_sql_filename = os.path.join(_DATA_DIR, 'anaya-no-cdd.sql')
        util.import_database(server, _DB_ID, db_sql_filename)

        with closing(server.get_connection(database=_DB_ID)) as cnx:
            count = _count_hits(cnx)
            self.assertEqual(count, 0, 'Test database should start without domain hits.')

            xml_filename = os.path.join(_DATA_DIR, 'rpsblast.xml')
            pham.conserveddomain.read_domains_from_xml(cnx, xml_filename)
            cnx.commit()

        with closing(server.get_connection(database=_DB_ID)) as cnx:
            count = _count_hits(cnx)
            self.assertTrue(count > 0, 'No domain hits found.')

def _count_hits(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('''
                       SELECT COUNT(id)
                       FROM gene_domain
                       ''')
        cdd_matches = cursor.fetchall()[0][0]
        return cdd_matches
