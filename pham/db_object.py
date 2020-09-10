from contextlib import closing


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

        if self.genes is None:
            self.genes = []
        if self.errors is None:
            self.errors = []

    @classmethod
    def from_database(cls, cnx, phage_id):
        """Return a phage loaded from the database.

        Raises PhageNotFoundError
        """
        with closing(cnx.cursor()) as cursor:
            # get phage
            cursor.execute('''
                SELECT PhageID, Accession, Name, HostStrain, Isolated, Sequence, Notes
                FROM phage
                WHERE phage.PhageID = %s
                           ''', (phage_id,))
            rows = cursor.fetchall()
            if len(rows) == 0:
                raise PhageNotFoundError('id: {}'.format(phage_id))
            row = rows[0]
            phage = Phage(row[0], row[1], row[2], row[3], row[4], row[5], str(row[6]), None, None, None)

            # get genes
            cursor.execute('''
                SELECT GeneID, Notes, Start, Stop, Length, Translation, StartCodon, StopCodon, Name, TypeID, Orientation, LeftNeighbor, RightNeighbor, GC, GC1, GC2, GC3
                FROM gene
                WHERE gene.PhageID = %s
                           ''', (phage_id,))
            genes = []
            for row in cursor.fetchall():
                gene = Gene(row[0], str(row[1]), row[2], row[3], row[4], None, row[5], row[6], row[7], row[8], row[9], row[10], row[11], row[12], gc=row[13], gc1=row[14], gc2=row[15], gc3=row[16])
                genes.append(gene)
            phage.genes = genes

        return phage

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
               left_neighbor_id, right_neighbor_id, gc=None, gc1=None, gc2=None, gc3=None):
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
        self.gc = gc
        self.gc1 = gc1
        self.gc2 = gc2
        self.gc3 = gc3

        if sequence is not None:
            if self.gc is None:
                self.gc = _compute_gc_content(sequence)
            if self.gc1 is None:
                self.gc1 = _compute_gc_content_x(sequence, 1)
            if self.gc2 is None:
                self.gc2 = _compute_gc_content_x(sequence, 2)
            if self.gc3 is None:
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
    for index in range(position - 1, len(sequence), 3):
        if sequence[index] in ('G', 'C', 'g', 'c'):
            gc_count += 1
        total += 1
    try:
        return 100 * (gc_count / total)
    except ZeroDivisionError:
        return None

class PhageNotFoundError(Exception):
    pass
