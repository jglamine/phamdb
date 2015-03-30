import os
from nose.tools import ok_, eq_
import unittest
import pham.genbank

_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

class TestGenbank(unittest.TestCase):

    def setUp(self):
        pass

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
        pass
