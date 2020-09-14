import tempfile
import os
import os.path
import shutil
from contextlib import closing
import mysql.connector
import mysql.connector.errors
from mysql.connector import errorcode
from Bio.Blast.Applications import NcbirpsblastCommandline
from Bio.Blast import NCBIXML

from pham.mmseqs import _write_fasta_record

_OUTPUT_FORMAT_XML = 5  # constant used by rpsblast
_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


def find_domains(cnx, gene_ids, sequences, num_threads=1):
    try:
        # Put all the genes in a fasta file
        fasta_name = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fasta:
            fasta_name = fasta.name
            for gene_id, sequence in zip(gene_ids, sequences):
                _write_fasta_record(fasta, sequence, gene_id)

        output_directory = tempfile.mkdtemp(suffix='-blast')
        try:
            # run rpsblast
            output_name = os.path.join(output_directory, 'rpsblast.xml')
            expectation_value_cutoff = 0.001
            cdd_database = os.path.join(_DATA_DIR, 'conserved-domain-database', 'Cdd', 'Cdd')
            rpsblast_bin = os.path.join(_DATA_DIR, 'ncbi-blast', 'rpsblast')
            cline = NcbirpsblastCommandline(rpsblast_bin,
                                            query=fasta_name,
                                            db=cdd_database,
                                            out=output_name,
                                            outfmt=_OUTPUT_FORMAT_XML,
                                            evalue=expectation_value_cutoff,
                                            num_threads=num_threads)
            # stdout, stderr = cline()
            cline()

            # parse rpsblast output
            read_domains_from_xml(cnx, output_name)

        finally:
            # Delete output directory regardless of rpsblast/reading outcome
            shutil.rmtree(output_directory)
    finally:
        # Delete input file regardless of rpsblast outcome
        if fasta_name is not None:
            try:
                os.remove(fasta_name)
            except IOError:
                pass

    # Mark the now-processed genes as 'searched' for domains
    with closing(cnx.cursor()) as cursor:
        in_clause = "'" + "', '".join(gene_ids) + "'"
        q = f"UPDATE gene SET DomainStatus = 1 WHERE GeneID in ({in_clause})"
        cursor.execute(q)


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


def _upload_domain(cursor, hit_id, domain_id, name, description):
    try:
        q = f"INSERT INTO domain (HitID, DomainID, Name, Description) " \
            f"VALUES ('{hit_id}', '{domain_id}', '{name}', '{description}')"
        cursor.execute(q)
    except mysql.connector.errors.Error as e:
        # ignore inserts which fail because the record already exists
        if e.errno == errorcode.ER_DUP_ENTRY:
            pass
        else:
            raise


def _upload_hit(cursor, gene_id, hit_id, expect, query_start, query_end):
    try:
        q = f"INSERT INTO gene_domain (GeneID, HitID, Expect, QueryStart, " \
            f"QueryEnd) VALUES ('{gene_id}', '{hit_id}', '{expect}', " \
            f"'{query_start}', '{query_end}')"
        cursor.execute(q)
    except mysql.connector.errors.Error as e:
        # ignore inserts which fail because the record already exists
        if e.errno == errorcode.ER_DUP_ENTRY:
            pass
        else:
            raise
