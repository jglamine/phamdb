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

class TestDb(unittest.TestCase):

    def setUp(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        with closing(server.get_connection()) as cnx:
            with closing(cnx.cursor()) as cursor:
                cursor.execute('DROP DATABASE IF EXISTS {};'.format(_DB_ID))
                cursor.execute('DROP DATABASE IF EXISTS {};'.format(_DB_ID_2))
                cnx.commit()
        self.callbacks = []

    def test_database_server(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        for _ in range(2):
            with closing(server.get_connection()) as cnx:
                with closing(cnx.cursor()) as cursor:
                    cursor.execute('SHOW DATABASES;')
                    cursor.fetchall()

    def test_load(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        sql_dump = os.path.join(_DATA_DIR, 'anaya-with-cdd.sql')
        pham.db.load(server, _DB_ID, sql_dump)

        with closing(server.get_connection(database=_DB_ID)) as cnx:
            with closing(cnx.cursor()) as cursor:
                cursor.execute('''
                               SELECT COUNT(delete_rule)
                               FROM information_schema.referential_constraints
                               WHERE constraint_schema IN (SELECT database())
                                AND delete_rule = 'CASCADE'
                               ''')
                self.assertEqual(cursor.fetchall()[0][0], 6)

    def test_create(self):
        server = pham.db.DatabaseServer('localhost', 'root')

        genbank_filenames = ['Anaya.gb']
        paths = [os.path.join(_DATA_DIR, filename) for filename in genbank_filenames]
        pham.db.create(server, _DB_ID, cdd_search=False, genbank_files=paths,
                       callback=_no_errors_callback)

        phage_ids = ['1034152']
        gene_counts = [98]
        with closing(server.get_connection(database=_DB_ID)) as cnx:
            phages = pham.query.list_organisms(cnx)
            eq_(len(paths), len(phages))

            for phage in phages:
                ok_(phage[0] in phage_ids, 'Unexpected phage id: {}'.format(phage[0]))
            for phage_id, gene_count in zip(phage_ids, gene_counts):
                genes = pham.query.list_genes(cnx, phage_id)
                eq_(len(genes), gene_count,
                    'Unexpected number of genes for phage {}: expected: {}, found: {}'.format(phage_id, gene_count, len(genes))
                    )

            with closing(cnx.cursor()) as cursor:
                # check for phams in database
                cursor.execute('SELECT COUNT(*) FROM pham')
                count = cursor.fetchall()[0][0]
                eq_(sum(gene_counts), count,
                    'Unexpected number of entries in `pham` table: expected: {}, found: {}'.format(count, sum(gene_counts))
                    )

                # check for the correct number of pham_colors in database
                cursor.execute('SELECT COUNT(*) FROM pham_color')
                color_count = cursor.fetchall()[0][0]

                cursor.execute('SELECT COUNT(DISTINCT name) FROM pham')
                pham_count = cursor.fetchall()[0][0]

                eq_(color_count, pham_count, 
                    'Unexpected number of entries in `pham_color` table: expected {}, found: {}'.format(pham_count, color_count)
                    )

                # ensure colors are unique
                cursor.execute('''
                               SELECT color
                               FROM pham_color
                               WHERE color NOT LIKE '#FFFFFF'
                               ''')
                colors = set()
                for row in cursor.fetchall():
                    color = row[0]
                    if color not in colors:
                        colors.add(color)
                    else:
                        ok_(False, 'Duplicate color: {}'.format(color))

        # export database
        directory = tempfile.mkdtemp(suffix='-export')
        try:
            filename = os.path.join(directory, '{}.sql'.format(_DB_ID))
            pham.db.export(server, _DB_ID, filename)

            version_filename = os.path.join(directory, '{}.version'.format(_DB_ID))
            checksum_filename = os.path.join(directory, '{}.md5sum'.format(_DB_ID))
            self.assertTrue(os.path.exists(filename))
            self.assertTrue(os.path.exists(version_filename))
            self.assertTrue(os.path.exists(checksum_filename))
        finally:
            shutil.rmtree(directory)

    def test_add_invalid_path(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        phage_filename = os.path.join(_DATA_DIR, 'no_such_file.gb')
        status = pham.db.create(server, _DB_ID, genbank_files=[phage_filename],
                       callback=self.store_callback)

        self.assertFalse(status, 'db.create should have returned False')
        found = False
        for code, args, kwargs in self.callbacks:
            if code == pham.db.CallbackCode.file_does_not_exist:
                if args[0] == phage_filename:
                    found = True
                    break
        self.assertTrue(found, 'File does not exist not detected.')

    def test_duplicate_phage(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        db_filename = os.path.join(_DATA_DIR, 'anaya-no-cdd.sql')
        util.import_database(server, _DB_ID, db_filename)

        # try to add a phage which already exists
        phage_filename = os.path.join(_DATA_DIR, 'Anaya.gb')
        status = pham.db.rebuild(server, _DB_ID,
                                 genbank_files_to_add=[phage_filename],
                                 cdd_search=False,
                                 callback=self.store_callback)

        message_found = False
        for message_code, args, kwargs in self.callbacks:
            if message_code == pham.db.CallbackCode.duplicate_organism:
                message_found = True
                break

        self.assertTrue(message_found, 'Duplicate phage not detected')
        self.assertFalse(status, 'db.rebuild should have returned False')
        self.callbacks = []

        # try to add a phage twice
        pham.db.create(server, _DB_ID_2,
                       genbank_files=[phage_filename, phage_filename],
                       cdd_search=False,
                       callback=self.store_callback)

        message_found = False
        for message_code, args, kwargs in self.callbacks:
            if message_code == pham.db.CallbackCode.duplicate_genbank_files:
                message_found = True
                break

        self.assertTrue(message_found, 'Duplicate input files not detected')

    def test_duplicate_gene(self):
        server = pham.db.DatabaseServer('localhost', 'root')

        # add two phages with auto-generated gene ids
        filepaths = []
        filepaths.append(os.path.join(_DATA_DIR, 'Filichino-small.gb'))
        filepaths.append(os.path.join(_DATA_DIR, 'Filichino-small-2.gb'))
        result = pham.db.create(server, _DB_ID,
                                genbank_files=filepaths,
                                cdd_search=False)
        self.assertTrue(result, 'create should have returned True')

        # add two phages with the same gene id
        pham.db.create(server, _DB_ID_2)
        filepaths = []
        filepaths.append(os.path.join(_DATA_DIR, 'Anaya.gb'))
        filepaths.append(os.path.join(_DATA_DIR, 'Anaya2.gb'))
        result = pham.db.rebuild(server, _DB_ID_2,
                                cdd_search=False,
                                genbank_files_to_add=filepaths,
                                callback=self.store_callback)

        self.assertFalse(result, 'rebuild should have returned False')
        with closing(server.get_connection(database=_DB_ID_2)) as cnx:
            phages = pham.query.list_organisms(cnx)
        self.assertEqual(len(phages), 0, 'rebuild should not have changed the database')
        found = False
        for code, args, kwargs in self.callbacks:
            if code == pham.db.CallbackCode.gene_id_already_exists:
                found = True
                break
        self.assertTrue(found, 'rebuild should have made a callback with `gene_id_already_exists`')

    def test_delete_during_rebuild(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        sql_dump = os.path.join(_DATA_DIR, 'anaya-with-cdd.sql')
        pham.db.load(server, _DB_ID, sql_dump)
        genbank_paths = [os.path.join(_DATA_DIR, 'Anaya.gb')]
        phages_to_delete = ['1034152']

        with closing(server.get_connection(database=_DB_ID)) as cnx:
            phages = pham.query.list_organisms(cnx)
            self.assertEqual(len(phages), 1, 'The database should start with one phage.')

        # add and delete a phage at the same time
        status = pham.db.rebuild(server, _DB_ID,
                        genbank_files_to_add=genbank_paths,
                        organism_ids_to_delete=phages_to_delete,
                        cdd_search=False)

        self.assertTrue(status, 'rebuild should have returned True')
        with closing(server.get_connection(database=_DB_ID)) as cnx:
            phages = pham.query.list_organisms(cnx)
            self.assertEqual(len(phages), 1, 'The database should still have one phage.')

    def test_version_update(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        pham.db.create(server, _DB_ID)

        # test that version is updated on rebuild
        with closing(server.get_connection(database=_DB_ID)) as cnx:
            initial_version = pham.query.version_number(cnx)

        pham.db.rebuild(server, _DB_ID)

        with closing(server.get_connection(database=_DB_ID)) as cnx:
            final_version = pham.query.version_number(cnx)

        ok_(initial_version < final_version,
            'Database version number did not update: initial: {}, final: {}'.format(initial_version, final_version)
            )

    def test_delete(self):
        server = pham.db.DatabaseServer('localhost', 'root')
        pham.db.delete(server, _DB_ID)
        pham.db.create(server, _DB_ID)
        pham.db.delete(server, _DB_ID)

    def store_callback(self, message_code, *args, **kwargs):
        self.callbacks.append((message_code, args, kwargs))

    def tearDown(self):
        pass

def _table_exists(cursor, table_name):
    cursor.execute('SHOW TABLES LIKE %s;', (table_name,))
    if len(cursor.fetchall()) == 0:
        return False
    return True

def _no_errors_callback(message_code, *args, **kwargs):
    ok_(message_code != pham.db.CallbackCode.genbank_format_error,
        'Error parsing genbank file: {}'.format(args[0]))
