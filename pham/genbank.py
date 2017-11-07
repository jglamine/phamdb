import re
from Bio import SeqIO
from Bio.Data.CodonTable import TranslationError
import Bio.Seq
import Bio.SeqRecord
import Bio.SeqFeature
from Bio.SeqFeature import FeatureLocation, ExactPosition
from Bio.Alphabet.IUPAC import IUPACAmbiguousDNA
from enum import Enum, EnumValue
import pham.db_object

def read_file(filepath):
    """Reads and validates a genbank file.

    Returns and instance of `db_object.Phage`
    This phage contains a list of errors (phage.errors) as well as a list
    of genes (phage.genes)

    See `ErrorCode` for a list of the errors which can be detected.
    """
    translation_table = 11
    return _PhageReader(filepath, translation_table).to_db_object()

def write_file(phage, filepath):
    """Writes a phage to a genbank file.

    phage: an instance of `db_object.Phage`.
    filepath: name of the file to write to.
    """
    sequence = Bio.Seq.Seq(str(phage.sequence), IUPACAmbiguousDNA())
    features = [] # list of SeqFeatures

    # source feature contains metadata about the phage
    source_feature = Bio.SeqFeature.SeqFeature(
                    type='source',
                    location=FeatureLocation(ExactPosition(0),
                                             ExactPosition(phage.sequence_length)),
                    qualifiers= {
                        'organism': phage.name,
                        'db_xref': phage.id,
                        'lab_host': phage.host_strain,
                        'isolation_source': phage.isolated,
                        'pham_reader': 'SKIP_GENE_SEQUENCE_VALIDATION'
                    })
    features.append(source_feature)

    # each gene is written as a CDS feature
    for gene in phage.genes:
        if gene.orientation == 'F':
            strand = 1
        elif gene.orientation == 'R':
            strand = -1
        else:
            strand = 0

        qualifiers = {
            'gene': gene.name,
            'note': gene.notes,
            'db_xref': gene.gene_id,
            'translation': gene.translation
        }

        if qualifiers['note'] in ('', None):
            del qualifiers['note']

        feature = Bio.SeqFeature.SeqFeature(
                    type='CDS',
                    location=FeatureLocation(ExactPosition(gene.start),
                                             ExactPosition(gene.stop)),
                    strand=strand,
                    qualifiers=qualifiers)
        features.append(feature)

    annotations = {
        'organism': 'Mycobacterium phage {}'.format(phage.name),
        'accessions': [phage.accension],
        'comment': phage.notes
    }

    record = Bio.SeqRecord.SeqRecord(sequence,
                                     id=phage.accension,
                                     description=phage.name,
                                     annotations=annotations,
                                     features=features
                                     )
    SeqIO.write([record], filepath, 'genbank')

class _PhageReader(object):
    """Reads a genbank file.

    Parses, validates, and stores phage data.

    Supports reading genbank files written for use by both the current and
    legacy (pre 2015) versions of Phamerator.

    Call genbank.read_file() rather than using this class directly.
    """
    def __init__(self, filename, translation_table):
        self.phage_id = None
        self.name = None
        self.translation_table = translation_table
        self.host_strain = None
        self.isolation = None
        self.accession = None
        self.notes = None
        self.genes = []
        self.errors = []
        self._validate_gene_sequence = True

        self._record = None
        self._filename = filename
        self._line_numbers = GenbankLineNumbers()

        with open(filename, 'rU') as genbank_file:
            try:
                # read the entire genbank file
                self._record = SeqIO.read(genbank_file, 'genbank')
            except ValueError as err:
                self._record = None
                self._add_error(ErrorCode.invalid_genbank_syntax)
            if self._record is not None:
                # read the file a second time, this time extracting the line
                # number for each feature. This is used when reporting error
                # messages.
                genbank_file.seek(0)
                self._line_numbers.read_file(genbank_file)

        if self._record is not None:
            self._validate_record()

    def to_db_object(self):
        """Convert all data into a `db_object.Phage` instance.

        Genes and errors are also included in the `db_object.Phage` instance.
        """
        phage_id = self.phage_id
        name = self.name
        host_strain = self.host_strain
        isolation = self.isolation
        accession = self.accession
        notes = self.notes

        if self._record is None:
            sequence = None
        else:
            sequence = str(self._record.seq).upper()

        genes = [gene_reader.to_db_object() for gene_reader in self.genes]

        return pham.db_object.Phage(phage_id, accession, name, host_strain, isolation, sequence, notes, genes, self._filename, self.errors)

    def _add_error(self, error, *args, **kwargs):
        line_number = kwargs.get('line_number')
        if line_number is None:
            line_number = self._line_numbers.line_for('source')

            if error == ErrorCode.invalid_genbank_syntax:
                line_number = 0

        self.errors.append(PhageError(error, line_number, self._filename, *args))

    def _validate_record(self):
        """Extract and validate phage and gene data.

        Errors are saved as a list of `PhageError` objects in self.errors.

        See `ErrorCode` for a list of the errors which can be detected.
        """
        if 'organism' in self._record.annotations:
            # read phage name
            name_parts = self._record.annotations['organism'].split()
            name_parts = [x for x in name_parts if x != '.']
            if len(name_parts):
                self.name = name_parts[-1]
                if self.name == 'Unclassified.' and len(name_parts) > 1:
                    self.name = name_parts[-2]

                # read phage host
                if name_parts[0] != self.name:
                    self.host_strain = name_parts[0]

        # read phage accession number
        if 'accessions' in self._record.annotations:
            value = self._record.annotations['accessions'][0]
            if value != '.':
                self.accession = value
        if self.accession is None:
            self.accession = self._record.id

        # read notes
        if 'comment' in self._record.annotations:
            value = self._record.annotations['comment']
            if value != '.':
                self.notes = value
        if self.notes is None:
            self.notes = self._record.description

        self.phage_id = self.name

        for feature in self._record.features:
            if feature.type == 'source':
                self._read_legacy_source_record(feature)

                # The `pham_reader` tag is set when exporting phages.
                # It tells the parser to ignore errors related to
                # gene sequences, as that data does not survive the
                # genbank -> phamerator database -> genbank conversion correctly.
                #
                # Specifically, CDS locations such as
                #    join(11244..11654,11654..12097)
                # are converted into
                #    11244..12097
                # resulting in incorrect sequence length calculations.
                webphamerator_tag = self._read_value(feature, ['pham_reader'])
                if webphamerator_tag is not None:
                    self._validate_gene_sequence = False

            if feature.type == 'CDS':
                self._read_gene_record(feature)

        if self.phage_id is None:
            self._add_error(ErrorCode.no_phage_id)

        if len(self.genes) == 0:
            self._add_error(ErrorCode.no_genes)
        else:
            self._ensure_unique_gene_ids()

        self._set_gene_neighbor_ids()

    def _read_legacy_source_record(self, feature):
        """Read phage data from the 'source' feature.

        Old versions of phamerator expected data here, so old genbank
        files might have data here.
        """
        if self.name is None:
            value = self._read_value(feature, ['organism'])
            if value is not None:
                self.name = value.split()[-1]

        value = self._read_value(feature, ['db_xref'])
        if value is not None:
            self.phage_id = value.split(':')[-1]

        if self.phage_id is None:
            self.phage_id = self.name
        if self.name is None:
            self.name = self.phage_id

        value = self._read_value(feature, ['host', 'lab_host', 'specific_host'])
        if value is not None:
            self.host_strain = value
        if self.isolation is None:
            self.isolation = self._read_value(feature, ['isolation_source'])

    def _read_value(self, feature, qualifiers):
        """Read a value from the qualifier of a feature.

        Qualifiers is a list of qualifiers to look for. Stop at the first
        qualifier from the list which is found.
        """
        for qualifier in qualifiers:
            if qualifier in feature.qualifiers:
                value = feature.qualifiers[qualifier][0]
                if value != '':
                    return value

    def _read_gene_record(self, feature):
        """Read and validate a gene feature.

        Gene features are features named 'CDS'.
        """
        gene_reader = GeneReader(feature,
                                 self._record.seq,
                                 self.translation_table,
                                 self._filename,
                                 self._line_numbers.line_for('CDS', len(self.genes)),
                                 validate_gene_sequence=self._validate_gene_sequence)
        self.genes.append(gene_reader)
        self.errors += gene_reader.errors
        gene_reader.errors = []

    def _ensure_unique_gene_ids(self):
        """Ensure that all the genes in have unique ids and names.

        Prepend the gene id with the phage id.

        If a gene does not have an id, generate one.
        If a gene does not have a name, generate one.
        If a two genes have the same name, assign new names.
        If two genes have the same id, report an error.
        """
        gene_ids = set()
        gene_names = set()
        name_index = 1
        id_index = 1

        for index, gene in enumerate(self.genes):
            if gene.gene_id is None:
                gene.gene_id = 'auto_gp{}'.format(id_index)
                id_index += 1

            if not gene.gene_id.startswith('{}:'.format(self.phage_id)):
                gene.gene_id = '{}:{}'.format(self.phage_id, gene.gene_id)

            if gene.gene_id in gene_ids:
                self._add_error(ErrorCode.duplicate_gene_id,
                                gene.gene_id,
                                line_number=gene.line,
                                )
            gene_ids.add(gene.gene_id)

            if gene.gene_name is None or gene.gene_name in gene_names:
                name_index = max(index + 1, name_index)
                while '{}'.format(name_index) in gene_names:
                    name_index += 1
                gene.gene_name = '{}'.format(name_index)
                gene_names.add(gene.gene_name)
                name_index += 1
            gene_names.add(gene.gene_name)

    def _set_gene_neighbor_ids(self):
        """Each gene must contain the id of its neighbor to the left and right.

        This method goes through all the genes, setting their left and right
        neighbor ids.
        """
        for index, gene in enumerate(self.genes):
            if index != 0:
                prev_gene = self.genes[index - 1]
                prev_gene.right_neighbor_id = gene.gene_id
                gene.left_neighbor_id = prev_gene.gene_id

        for index in xrange(len(self.genes)):
            if index != 0:
                self.genes[index]


class GenbankLineNumbers(object):
    """Extracts the line number of each feature in a genbank file.

    Used to report the line number of validation errors.
    """
    def __init__(self, genbank_file=None):
        self._features = {}
        if genbank_file is not None:
            self.read_file(genbank_file)

    def read_file(self, genbank_file):
        section_re = r'([A-Z-_]+)\s'
        feature_re = r'     (\w+)\s'

        section = None
        for line_number, line in enumerate(genbank_file):
            line_number += 1

            match = re.match(section_re, line)
            if match is not None:
                section = match.group(1)
                continue

            if section == 'FEATURES':
                match = re.match(feature_re, line)
                if match is not None:
                    feature_name = match.group(1)
                    if feature_name not in self._features:
                        self._features[feature_name] = []
                    self._features[feature_name].append(line_number)

    def line_for(self, feature, index=0):
        try:
            line = self._features[feature][index]
        except KeyError:
            line = None
        except IndexError:
            line = None
        return line


class GeneReader(object):
    """Reads and validates a gene from a 'CDS' feature.
    """
    def __init__(self, feature, sequence, translation_table, filename,
                 line_number=None, validate_gene_sequence=True):
        if feature.type != 'CDS':
            raise ValueError('Invalid feature type: not a gene feature')

        self.gene_id = None
        self.notes = None
        self.start = None
        self.stop = None
        self.length = None
        self.translation = None
        self.start_codon = None
        self.stop_codon = None
        self.gene_name = None
        self.type_id = 'CDS'
        self.orientation = None
        self.left_neighbor_id = None
        self.right_neighbor_id = None
        self.errors = []
        
        self._feature = feature
        self._gene_sequence = None
        self._translation_table = translation_table
        self.line = line_number
        self._filename = filename
        self._validate_gene_sequence = validate_gene_sequence

        self._read_gene_id()
        self._read_gene_name()
        self._read_gene_notes()
        self._read_orientation()
        self._read_sequence(sequence)
        self._read_translation()

    def to_db_object(self):
        """Convert to a `db_object.Gene` instance.
        """

        return pham.db_object.Gene(self.gene_id, self.notes, self.start, self.stop,
                    self.length, self._gene_sequence, self.translation, self.start_codon,
                    self.stop_codon, self.gene_name, self.type_id,
                    self.orientation, self.left_neighbor_id,
                    self.right_neighbor_id)

    def _read_gene_id(self):
        if 'locus_tag' in self._feature.qualifiers:
            self.gene_id = self._feature.qualifiers['locus_tag'][0]

        if self.gene_id is None:
            for ref in self._feature.qualifiers.get('db_xref', []):
                if 'GeneID' not in ref:
                    self.gene_id = ref
                    break

        if self.gene_id is None:
            # this error is treated as a warning
            self._add_error(ErrorCode.no_gene_id)

    def _add_error(self, error_code, *args):
        line_number = self.line
        args = list(args)
        
        if error_code == ErrorCode.no_gene_id:
            pass
        elif error_code == ErrorCode.unknown_gene_orientation:
            pass
        elif error_code == ErrorCode.invalid_gene_start_codon:
            args.insert(0, self.start_codon)
        elif error_code == ErrorCode.invalid_gene_stop_codon:
            args.insert(0, self.stop_codon)
        elif error_code == ErrorCode.invalid_gene_sequence:
            args.insert(0, self._gene_sequence)
        elif error_code == ErrorCode.invalid_gene_sequence_length:
            args.insert(0, len(self._gene_sequence))
        elif error_code == ErrorCode.gene_stop_out_of_bounds:
            args = [self.stop]
        elif error_code == ErrorCode.gene_start_out_of_bounds:
            args = [self.start]

        self.errors.append(PhageError(error_code, line_number, self._filename, *args))

    def _read_gene_name(self):
        name = None

        if 'gene' in self._feature.qualifiers:
            name = self._feature.qualifiers['gene'][0]
        if name is None and 'locus_tag' in self._feature.qualifiers:
            name = self._feature.qualifiers['locus_tag'][0]
        if name is None and 'product' in self._feature.qualifiers:
            name = self._feature.qualifiers['product'][0]
        if name is None and 'standard_name' in self._feature.qualifiers:
            name = self._feature.qualifiers['standard_name'][0]
        if name is None and 'protein_id' in self._feature.qualifiers:
            name = self._feature.qualifiers['protein_id'][0]

        if name is not None:
            name = name.split(':')[-1]

        self.gene_name = name

    def _read_gene_notes(self):
        self.notes = None
        if 'note' in self._feature.qualifiers:
            self.notes = self._feature.qualifiers['note'][0]
        elif 'product' in self._feature.qualifiers:
            product = self._feature.qualifiers['product'][0]
            if product.lower() != 'hypothetical protein':
                self.notes = product

    def _read_orientation(self):
        orientation = self._feature.strand
        if orientation == 1:
            self.orientation = 'F'
        elif orientation == -1:
            self.orientation = 'R'
        elif orientation is None:
            # orientation does not matter or it is a single strand
            self.orientation = 'F'
        elif orientation == 0:
            # orientation is important but unknown
            self._add_error(ErrorCode.unknown_gene_orientation)
        else:
            # unexpected orientation code
            self._add_error(ErrorCode.unknown_gene_orientation)

    def _read_sequence(self, sequence):
        gene_sequence = self._feature.extract(sequence)
        self.length = len(gene_sequence)
        self._gene_sequence = str(gene_sequence)
        self.start_codon = self._gene_sequence[:3]
        self.stop_codon = self._gene_sequence[-3:]
        self.start = self._feature.location.start.position
        self.stop = self._feature.location.end.position

        if self._validate_gene_sequence:
            # The sequence location may be invalid, but the translation,
            # first, and last codons should still be correct.
            if len(self._gene_sequence) % 3 != 0 or len(self._gene_sequence) == 0:
                self._add_error(ErrorCode.invalid_gene_sequence_length)

        if self.stop > len(sequence):
            self._add_error(ErrorCode.gene_stop_out_of_bounds)
            return
        if self.start > len(sequence):
            self._add_error(ErrorCode.gene_start_out_of_bounds)
            return

        if self.start_codon not in ['ATG', 'GTG', 'TTG', 'CTG']:
            self._add_error(ErrorCode.invalid_gene_start_codon)
        if self.stop_codon not in ['TAA', 'TAG', 'TGA']:
            self._add_error(ErrorCode.invalid_gene_stop_codon)

    def _read_translation(self):
        # use the calculated translation unless there is a programmed frameshift
        translation = None

        if 'translation' in self._feature.qualifiers:
            translation = self._feature.qualifiers['translation'][0]
            if translation[-1] in '*z':
                translation = translation[:-1]

        if not self._validate_gene_sequence:
            # The gene sequence location might be wrong. Use the translation
            # from the file instead.
            self.translation = translation
            return

        try:
            calculated_translation = Bio.Seq.translate(self._gene_sequence,
                                                       table=self._translation_table,
                                                       to_stop=True,
                                                       cds=True)
        except TranslationError as err:
            self._add_error(ErrorCode.invalid_gene_sequence)
            # use translation from file
            self.translation = translation
            return

        calculated_translation = str(calculated_translation)
        self.translation = calculated_translation

        # if there is a programmed frameshift, use the original.
        if calculated_translation != translation:
            if not ('*' in calculated_translation and '*' in translation):
                # mismatch caused by programmed frameshift.
                self.translation = translation

class PhageError(object):
    """A Phage (or gene) validation error.

    Contains the error code, line number, filename, and any other arguments
    necessary to display in an error message.

    Contains a method to generate a human readable error message string.

    The equals (==) operator is overloaded to work with both `PhageError`
    and `ErrorCode` instances.
    """
    def __init__(self, error_code, line_number, filename, *args):
        self.filename = filename
        self.code = error_code
        self.line_number = line_number
        self.args = args

    def is_warning(self):
        if self.code in (ErrorCode.no_gene_id,):
            return True

    def __repr__(self):
        items = []
        items.append(self.filename)
        items.append('line: {}'.format(self.line_number))
        items.append('code: {}'.format(self.code))
        for arg in self.args:
            items.append(str(arg))
        return ', '.join(items)

    def message(self):
        """Return a human readable message for this error.

        Does not include the file name or line number.
        """
        message = None
        if self.code == ErrorCode.no_genes:
            message = 'Phage does not contain any genes.'
        elif self.code == ErrorCode.no_phage_id:
            message = 'Could not find an ID for this phage. Add either a \'db_xref\' or \'organism\' qualifier.'
        elif self.code == ErrorCode.invalid_genbank_syntax:
            message = 'Not a valid genbank file.'
        elif self.code == ErrorCode.no_gene_id:
            message = 'Could not find an ID for this gene. Add a \'db_xref\' qualifier to this CDS.'
        elif self.code == ErrorCode.unknown_gene_orientation:
            message = 'Error reading the orientation for this gene.'
        elif self.code == ErrorCode.invalid_gene_start_codon:
            message = '{} is not a valid start codon.'.format(self.args[0])
        elif self.code == ErrorCode.invalid_gene_stop_codon:
            message = '{} is not a valid stop codon.'.format(self.args[0])
        elif self.code == ErrorCode.duplicate_gene_id:
            message = 'Duplicate gene ID \'{}\'.'.format(self.args[0])
        elif self.code == ErrorCode.invalid_gene_sequence:
            message = 'Invalid gene sequence.'
        elif self.code == ErrorCode.gene_stop_out_of_bounds:
            message = 'Gene stop location \'{}\' is greater than the phage sequence length.'.format(self.args[0])
        elif self.code == ErrorCode.gene_start_out_of_bounds:
            message = 'Gene start location \'{}\' is greater than the phage sequence length.'.format(self.args[0])
        elif self.code == ErrorCode.invalid_gene_sequence_length:
            message = 'Gene sequence length must be a nonzero multiple of 3, but is \'{}\'.'.format(self.args[0])
        return message

    def __str__(self):
        """Return a human readable message for this error.

        Includes the file name and line number.
        """
        return '{} line {} - {}'.format(self.filename, self.line_number, self.message())

    def __eq__(self, other):
        if isinstance(other, PhageError):
            return other.code == self.code
        if isinstance(other, EnumValue):
            return other == self.code
        return NotImplemented

ErrorCode = Enum('no_genes',
                 'no_phage_id',
                 'invalid_genbank_syntax',
                 'no_gene_id',
                 'unknown_gene_orientation',
                 'invalid_gene_start_codon',
                 'invalid_gene_stop_codon',
                 'duplicate_gene_id',
                 'invalid_gene_sequence',
                 'gene_stop_out_of_bounds',
                 'gene_start_out_of_bounds',
                 'invalid_gene_sequence_length'
                 )
