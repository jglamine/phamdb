from contextlib import closing
import mysql.connector
from mysql.connector import errorcode

class Phage(object):
    def __init__(self, phage_id, accension, name, host_strain, isolated,
                 sequence, notes, genes, filename, errors):
        self.id = phage_id
        self.accension = accension
        self.name = name
        self.host_strain = host_strain
        self.isolated = isolated
        self.sequence = sequence
        self.notes = notes

        self.sequence_length = None
        self.gc = None
        if sequence is not None:
            self.sequence_length = len(sequence)
            self.gc = _compute_gc_content(sequence)

        self.genes = genes
        self.errors = errors
        self.filename = filename

    def is_valid(self, strict=False):
        """Return True if the phage is valid.

        Args:
            strict: Do not ignore warnings.
        """
        if strict:
            return len(self.errors) == 0

        for error in self.errors:
            if not error.is_warning():
                return False
        return True

    def upload(self, cnx):
        # make sure phage does not exist

        # upload phage
        with closing(cnx.cursor()) as cursor:
            values = (self.id, self.accension, self.name, self.host_strain, self.isolated, self.sequence, self.notes, self.sequence_length, self.gc)
            cursor.execute('''
                INSERT INTO phage (PhageID, Accession, Name, HostStrain, Isolated, Sequence, Notes, SequenceLength, GC)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                ''', values)

        # upload genes, setting phage_id for each gene
        for gene in self.genes:
            gene.phage_id = self.id
            gene.upload(cnx)

class Gene(object):
    def __init__(self, gene_id, notes, start, stop, length, sequence, translation,
               start_codon, stop_codon, name, type_id, orientation,
               left_neighbor_id, right_neighbor_id):
        self.gene_id = gene_id
        self.phage_id = None
        self.notes = notes
        self.start = start
        self.stop = stop
        self.length = length
        self.translation = translation
        self.start_codon = start_codon
        self.stop_codon = stop_codon
        self.name = name
        self.type_id = type_id
        self.orientation = orientation
        self.left_neighbor_id = left_neighbor_id
        self.right_neighbor_id = right_neighbor_id

        self.gc = _compute_gc_content(sequence)
        self.gc1 = _compute_gc_content_x(sequence, 1)
        self.gc2 = _compute_gc_content_x(sequence, 2)
        self.gc3 = _compute_gc_content_x(sequence, 3)

    def upload(self, cnx):
        # make sure gene id does not exist

        # upload gene
        with closing(cnx.cursor()) as cursor:
            values = (self.gene_id, self.phage_id, self.notes, self.start, self.stop, self.length, self.translation, self.start_codon, self.stop_codon, self.name, self.type_id, self.orientation, self.gc, self.gc1, self.gc2, self.gc3, self.left_neighbor_id, self.right_neighbor_id)
            cursor.execute('''
                INSERT INTO gene (GeneID, PhageID, Notes, Start, Stop, Length, Translation, StartCodon, StopCodon, Name, TypeID, Orientation, GC, GC1, GC2, GC3, LeftNeighbor, RightNeighbor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                ''', values)

def _compute_gc_content(sequence):
    count = sum((1 for char in sequence if char in ('G', 'C', 'g', 'c')))
    try:
        ratio = count / float(len(sequence))
        return 100 * ratio
    except ZeroDivisionError:
        return None

def _compute_gc_content_x(sequence, position=1):
    total = 0.0
    gc_count = 0
    for index in xrange(position - 1, len(sequence), 3):
        if sequence[index] in ('G', 'C', 'g', 'c'):
            gc_count += 1
        total += 1
    try:
        return 100 * (gc_count / total)
    except ZeroDivisionError:
        return None
