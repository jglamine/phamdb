import os
from contextlib import closing
import unittest
import pham.db
import pham.query
import pham.test.util as util

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
_DB_ID = 'test_database'

class TestQuery(unittest.TestCase):

    def setUp(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        pham.db.delete(server, _DB_ID)

    def test_delete_phage(self):
        server = pham.db.DatabaseServer('localhost', 'root')

        # load test test database with cdd
        sql_path = os.path.join(_DATA_DIR, 'anaya-with-cdd.sql')
        pham.db.load(server, _DB_ID, sql_path)

        with closing(server.get_connection(database=_DB_ID)) as cnx:
            self.assertTrue(_has_domains(cnx), 'Test database should start with some cdds.')
            
            phage_id = pham.query.list_organisms(cnx)[0][0]
            pham.query.delete_phage(cnx, phage_id)
            self.assertEqual(len(pham.query.list_organisms(cnx)), 0, 'Test database should not have any phages.')

            hits_count = _count_hits(cnx)
            self.assertEqual(hits_count, 0, 'Test database should have no hits: found {}'.format(hits_count))
            domains_count = _count_domains(cnx)
            self.assertEqual(domains_count, 0, 'Test database should have no domains: found {}'.format(domains_count))
            self.assertFalse(_has_domains(cnx), 'Test database should not have any cdds.')
            pham.query.delete_phage(cnx, phage_id)

def _has_domains(cnx):
    with closing(cnx.cursor()) as cursor:
        count = 0
        cursor.execute('''
                       SELECT COUNT(id)
                       FROM gene_domain
                       ''')
        count += cursor.fetchall()[0][0]

        cursor.execute('''
                       SELECT COUNT(id)
                       FROM domain
                       ''')
        count += cursor.fetchall()[0][0]
        return count > 0

def _count_domains(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('''
                       SELECT COUNT(id)
                       FROM domain
                       ''')
        return cursor.fetchall()[0][0]

def _count_hits(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('''
                       SELECT COUNT(id)
                       FROM gene_domain
                       ''')
        return cursor.fetchall()[0][0]