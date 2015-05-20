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

class TestDb(unittest.TestCase):

    def setUp(self):
        self.server = pham.db.DatabaseServer('localhost', 'root')
        with closing(self.server.get_connection()) as cnx:
            with closing(cnx.cursor()) as cursor:
                cursor.execute('DROP DATABASE IF EXISTS {};'.format(_DB_ID))
                cnx.commit()

    def test_assign_pham_ids(self):
        # identical phams should remain identical
        old_phams = {
            1: set([1, 2, 3]),
            2: set([4, 5]),
            3: set([6])
        }
        
        phams = pham.db._assign_pham_ids(old_phams, old_phams)
        self.assertEqual(len(phams), len(old_phams))
        for key, value in phams.iteritems():
            self.assertEqual(value, old_phams[key])

        # identical phams with different ids should remain identical
        new_phams = {}
        for key, value in old_phams.iteritems():
            new_phams[key + 20] = value

        phams = pham.db._assign_pham_ids(new_phams, old_phams)
        self.assertEqual(len(phams), len(old_phams))
        for key, value in phams.iteritems():
            self.assertEqual(value, old_phams[key])

        # phams with only new genes should be given a new id
        new_phams[1] = set([200, 201, 202])
        phams = pham.db._assign_pham_ids(new_phams, old_phams)
        self.assertEqual(phams[4], new_phams[1], phams)
        del new_phams[1]

        # phams with a new gene added should keep the old id
        new_phams[21] = set([1, 2, 3, 200])
        phams = pham.db._assign_pham_ids(new_phams, old_phams)
        self.assertEqual(new_phams[21], phams[1], phams)

        # phams with a gene deleted should keep the old id
        new_phams[21] = set([2, 3])
        phams = pham.db._assign_pham_ids(new_phams, old_phams)
        self.assertTrue(1 in phams, phams)
        self.assertEqual(new_phams[21], phams[1], phams)

        # phams with a gene deleted and a gene added should keep the old id
        new_phams[21] = set([2, 3, 200])
        phams = pham.db._assign_pham_ids(new_phams, old_phams)
        self.assertEqual(new_phams[21], phams[1], phams)

        # phams which have been split should have new ids
        new_phams[21] = set([1, 2])
        new_phams[24] = set([3])
        phams = pham.db._assign_pham_ids(new_phams, old_phams)
        self.assertTrue(1 not in phams, phams)
        self.assertEqual(set([new_phams[21], new_phams[24]]), set([phams[4], phams[5]]), phams)

        # phams with a new gene which have been split should have new ids
        new_phams[21] = set([1, 2])
        new_phams[24] = set([3, 200])
        phams = pham.db._assign_pham_ids(new_phams, old_phams)
        self.assertTrue(1 not in phams, phams)
        self.assertEqual(set([new_phams[21], new_phams[24]]), set([phams[4], phams[5]]), phams)

        # phams which have been combined should nave new ids
        new_phams[21] = set([1, 2, 3, 4, 5])
        del new_phams[22]
        del new_phams[24]
        phams = pham.db._assign_pham_ids(new_phams, old_phams)
        self.assertTrue(1 not in phams, phams)
        self.assertEqual(new_phams[21], phams[4], phams)

        # phams which have been combined and had some genes added and removed
        # should have new ids
        new_phams[21] = set([1, 3, 4, 200])
        phams = pham.db._assign_pham_ids(new_phams, old_phams)
        self.assertTrue(1 not in phams, phams)
        self.assertEqual(new_phams[21], phams[4], phams)

    def test_conserve_phams(self):
        # import database
        server = pham.db.DatabaseServer('localhost', 'root')
        db_filename = os.path.join(_DATA_DIR, 'conserve-phams.sql')
        util.import_database(self.server, _DB_ID, db_filename)

        # check that not all of them are orphams
        summary = pham.db.summary(self.server, _DB_ID)
        self.assertNotEqual(summary.number_of_phams, summary.number_of_orphams)

        # re-assign pham ids
        self._re_assign_pham_ids(_DB_ID)
        
        original_phams = self._read_phams(_DB_ID)
        self.assertTrue(1 not in original_phams)
        self.assertEqual(len(original_phams), summary.number_of_phams)

        # remove a phage
        pham.db.rebuild(self.server, _DB_ID, organism_ids_to_delete=['Filichino'])

        # read phams, compare to original
        phams = self._read_phams(_DB_ID)
        self.assertEqual(len(phams), len(original_phams))

        # they should all be orphams
        for pham_id, genes in phams.iteritems():
            self.assertEqual(len(genes), 1)

        # they should only have pham ids from the original
        for pham_id, genes in phams.iteritems():
            self.assertTrue(pham_id in original_phams)

        # they should all only have genes from the original phams
        for pham_id, genes in phams.iteritems():
            for gene_id in genes:
                self.assertTrue(gene_id in original_phams[pham_id])
        
        # re-add the phage
        genbank_file = os.path.join(_DATA_DIR, 'Filichino-small.gb')
        pham.db.rebuild(self.server, _DB_ID, genbank_files_to_add=[genbank_file])

        # read phams, compare to original
        phams = self._read_phams(_DB_ID)
        self.assertEqual(len(phams), len(original_phams))

        # the phams should match the originals
        for pham_id, genes in phams.iteritems():
            self.assertTrue(pham_id in original_phams)
            self.assertEqual(genes, original_phams[pham_id])

    def _read_phams(self, id):
        # read phams into a hash of id: frozen set of gene ids
        phams = {}
        with closing(self.server.get_connection(database=id)) as cnx:
            with closing(cnx.cursor()) as cursor:
                cursor.execute('''
                    SELECT name, GeneID
                    FROM pham
                               ''')
                
                for pham_id, gene_id in cursor:
                    if pham_id not in phams:
                        phams[pham_id] = set()
                    phams[pham_id].add(gene_id)

        return phams

    def _re_assign_pham_ids(self, id):
        with closing(self.server.get_connection(database=id)) as cnx:
            with closing(cnx.cursor()) as cursor:
                cursor.execute('''
                    UPDATE pham
                    SET name = name * 2 + 200
                               ''')
            cnx.commit()
