import tempfile
import os
import os.path
import shutil
from contextlib import closing
from itertools import izip
import mysql.connector
import mysql.connector.errors
from mysql.connector import errorcode
from Bio.Blast.Applications import NcbirpsblastCommandline
from Bio.Blast import NCBIXML

_OUTPUT_FORMAT_XML = 5 # constant used by rpsblast
_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

def find_domains(cnx, gene_ids, sequences, num_threads=1):
    try:
        # build fasta file of all genes
        fasta_filename = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fasta_file:
            fasta_filename = fasta_file.name
            for gene_id, sequence in izip(gene_ids, sequences):
                _write_fasta_record(fasta_file, sequence, gene_id)

        output_directory = tempfile.mkdtemp(suffix='-blast')
        try:
            # run rpsblast
            output_filename = os.path.join(output_directory, 'rpsblast.xml')
            expectation_value_cutoff = 0.001
            cdd_database = os.path.join(_DATA_DIR, 'conserved-domain-database', 'Cdd', 'Cdd')
            rpsblast_bin = os.path.join(_DATA_DIR, 'ncbi-blast', 'rpsblast')
            cline = NcbirpsblastCommandline(rpsblast_bin,
                                            query=fasta_filename,
                                            db=cdd_database,
                                            out=output_filename,
                                            outfmt=_OUTPUT_FORMAT_XML,
                                            evalue=expectation_value_cutoff,
                                            num_threads=num_threads
                                            )
            stdout, stderr = cline()

            # parse rpsblast output
            read_domains_from_xml(cnx, output_filename)

        finally:
            shutil.rmtree(output_directory)
    finally:
        if fasta_filename is not None:
            try:
                os.remove(fasta_filename)
            except IOError:
                pass

def read_domains_from_xml(cnx, xml_filename):
    with open(xml_filename, 'r') as xml_handle:
        with closing(cnx.cursor()) as cursor:
            for record in NCBIXML.parse(xml_handle):
                if not record.alignments:
                    # skip genes with no matches
                    continue

                gene_id = record.query

                for alignment in record.alignments:
                    hit_id = alignment.hit_id
                    domain_id, name, description = _read_hit(alignment.hit_def)

                    _upload_domain(cursor, hit_id, domain_id, name, description)

                    for hsp in alignment.hsps:
                        expect = float(hsp.expect)
                        query_start = int(hsp.query_start)
                        query_end = int(hsp.query_end)

                        _upload_hit(cursor, gene_id, hit_id, expect, query_start, query_end)

def _read_hit(hit):
    items = hit.split(',')

    description = None
    name = None
    domain_id = None

    if len(items) == 1:
        description = items[0].strip()
    elif len(items) == 2:
        domain_id = items[0].strip()
        description = items[1].strip()
    elif len(items) > 2:
        domain_id = items[0].strip()
        name = items[1].strip()
        description = ','.join(items[2:]).strip()

    return domain_id, name, description

def _write_fasta_record(fasta_file, sequence, gene_id):
    sequence = sequence.replace('-', 'M')
    fasta_file.write('>{}\n'.format(gene_id))
    index = 0
    while index < len(sequence):
        fasta_file.write('{}\n'.format(sequence[index:index + 80]))
        index += 80

def _upload_domain(cursor, hit_id, domain_id, name, description):
    try:
        cursor.execute('''
            INSERT INTO domain (hit_id, DomainID, Name, Description)
            VALUES (%s, %s, %s, %s)
            ''', (hit_id, domain_id, name, description))
    except mysql.connector.errors.Error as e:
        # ignore inserts which fail because the record already exists
        if e.errno == errorcode.ER_DUP_ENTRY:
            pass
        else:
            raise

def _upload_hit(cursor, gene_id, hit_id, expect, query_start, query_end):
    try:
        cursor.execute('''
            INSERT INTO gene_domain (GeneID, hit_id, expect, query_start, query_end)
            VALUES (%s, %s, %s, %s, %s)
            ''', (gene_id, hit_id, expect, query_start, query_end))
    except mysql.connector.errors.Error as e:
        # ignore inserts which fail because the record already exists
        if e.errno == errorcode.ER_DUP_ENTRY:
            pass
        else:
            raise
