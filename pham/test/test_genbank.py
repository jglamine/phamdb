import os
from nose.tools import ok_, eq_
import unittest
import pham.genbank

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
_TEMP_FILENAME = os.path.join(_DATA_DIR, 'temp-test.gb')

class TestGenbank(unittest.TestCase):

    def setUp(self):
        pass

    def test_import(self):
        # read a file
        filename = os.path.join(_DATA_DIR, 'Anaya.gb')
        phage = pham.genbank.read_file(filename)
        self.assertTrue(phage.is_valid())

        self.assertEqual(phage.id, '1034152')
        self.assertEqual(phage.name, 'Anaya')
        self.assertEqual(phage.host_strain, 'Mycobacterium smegmatis mc2 155')
        self.assertEqual(phage.isolated, 'soil')
        expected_note = 'Phage isolation, DNA preparation, and annotation analysis performed\nat Calvin College, Grand Rapids, MI\nSequencing performed at Joint Genome Institute, Los Alamos, NM\nSupported by Science Education Alliance, Howard Hughes Medical\nInstitute, Chevy Chase, MD.'
        self.assertEqual(phage.notes, expected_note)

    def test_export_import(self):
        # read a file
        filename = os.path.join(_DATA_DIR, 'D29.gb')
        phage1 = pham.genbank.read_file(filename)
        self.assertTrue(phage1.is_valid())

        # export the file
        pham.genbank.write_file(phage1, _TEMP_FILENAME)

        # re-import the file
        phage2 = pham.genbank.read_file(_TEMP_FILENAME)
        self.assertTrue(phage1.is_valid())

        # compare the new and old phages
        self.assertEqual(phage1.name, phage2.name)
        self.assertEqual(phage1.id, phage2.id)
        self.assertEqual(len(phage1.genes), len(phage2.genes))
        self.assertEqual(phage1.notes, phage2.notes)
        self.assertEqual(phage1.isolated, phage2.isolated)
        self.assertEqual(phage1.host_strain, phage2.host_strain)

        for gene1, gene2 in zip(phage1.genes, phage2.genes):
            self.assertEqual(gene1.gene_id, gene2.gene_id)
            self.assertEqual(gene1.notes, gene2.notes)
            self.assertEqual(gene1.start, gene2.start)
            self.assertEqual(gene1.stop, gene2.stop)
            self.assertEqual(gene1.orientation, gene2.orientation)
            self.assertEqual(gene1.translation, gene2.translation)

        # check genbank file
        translation_table = 11
        reader = pham.genbank._PhageReader(_TEMP_FILENAME, translation_table)
        record = reader._record
        self.assertIsNotNone(record.id)
        self.assertNotEqual(record.id, '<unknown id>')

    def test_validation(self):
        # read file without errors
        filename = os.path.join(_DATA_DIR, 'Filichino.gb')
        phage = pham.genbank.read_file(filename)

        error_messages = '\n'.join((str(error) for error in phage.errors if not error.is_warning()))
        self.assertTrue(phage.is_valid(),
                        '{}\n{} validation errors'.format(error_messages,
                                                          len(phage.errors)))
        self.assertEqual(phage.name, "Filichino")
        for gene in phage.genes:
            self.assertFalse(gene.gene_id is None)

        # check left-neighbor and right-neighbor fields
        for index in xrange(len(phage.genes)):
            if index == 0:
                expected_left = None
            else:
                expected_left = phage.genes[index - 1].gene_id
            if index + 1 == len(phage.genes):
                expected_right = None
            else:
                expected_right = phage.genes[index + 1].gene_id
            self.assertEqual(expected_right, phage.genes[index].right_neighbor_id,
                             'Gene {} has the wrong right_neighbor_id: expected: {}, found: {}'.format(phage.genes[index].gene_id, expected_right, phage.genes[index].right_neighbor_id))
            self.assertEqual(expected_left, phage.genes[index].left_neighbor_id,
                             'Gene {} has the wrong left_neighbor_id: expected: {}, found: {}'.format(phage.genes[index].gene_id, expected_left, phage.genes[index].left_neighbor_id))

        # read file with errors
        filename = os.path.join(_DATA_DIR, 'errorfull_phage.gb')
        phage = pham.genbank.read_file(filename)
        self.assertFalse(phage.is_valid(), 'Phage should be invalid.')

        expected_errors = [pham.genbank.ErrorCode.no_phage_id, pham.genbank.ErrorCode.no_gene_id]
        for error_code in expected_errors:
            self.assertTrue(self._has_error(phage, error_code),
                            'Phage should have error {}'.format(error_code))

    def _has_error(self, phage, error_code):
        for error in phage.errors:
            if error == error_code:
                return True
        return False

    def tearDown(self):
        if os.path.isfile(_TEMP_FILENAME):
            os.remove(_TEMP_FILENAME)
