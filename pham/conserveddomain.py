import tempfile
import os
import os.path
import shutil

from sqlalchemy import exc
from pymysql import err as pmserr
from Bio.Blast.Applications import NcbirpsblastCommandline
from Bio.Blast import NCBIXML
from pdm_utils.functions import basic

INSERT_INTO_DOMAIN = (
    """INSERT IGNORE INTO domain (HitID, DomainID, Name, Description) """
    """Values ("{}", "{}", "{}", "{}")""")
INSERT_INTO_GENE_DOMAIN = (
    """INSERT IGNORE INTO gene_domain (GeneID, HitID, Expect, QueryStart, """
    """QueryEnd) VALUES ("{}", "{}", {}, {}, {})""")

from pham.mmseqs import _write_fasta_record

_OUTPUT_FORMAT_XML = 5  # constant used by rpsblast
_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


def find_domains(alchemist, gene_ids, sequences, num_threads=1):
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
            cdd_database = os.path.join(_DATA_DIR, 'conserved-domain-database',
                                        'Cdd', 'Cdd')
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
            read_domains_from_xml(alchemist, output_name)

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
    with alchemist.engine.begin() as engine:
        in_clause = "'" + "', '".join(gene_ids) + "'"
        q = f"UPDATE gene SET DomainStatus = 1 WHERE GeneID in ({in_clause})"
        engine.execute(q)


def read_domains_from_xml(alchemist, xml_filename):
    with open(xml_filename, 'r') as xml_handle:
        with alchemist.engine.begin() as engine:
            for record in NCBIXML.parse(xml_handle):
                if not record.alignments:
                    # skip genes with no matches
                    continue

                gene_id = record.query

                for alignment in record.alignments:
                    hit_id = alignment.hit_id
                    domain_id, name, description = _read_hit(alignment.hit_def)

                    _upload_domain(engine, hit_id, domain_id, name,
                                   description)

                    for hsp in alignment.hsps:
                        expect = float(hsp.expect)
                        query_start = int(hsp.query_start)
                        query_end = int(hsp.query_end)

                        _upload_hit(engine, gene_id, hit_id, expect,
                                    query_start, query_end)


def _read_hit(hit):
    hit_def = hit.replace("\"", "\'")
    items = hit_def.split(',')

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
        name = basic.truncate_value(name, 25, "...")
        description = ','.join(items[2:]).strip()

    return domain_id, name, description


def _upload_domain(engine, hit_id, domain_id, name, description):
    try:
        q = INSERT_INTO_DOMAIN.format(hit_id, domain_id, name, description)
        engine.execute(q)
    except exc.IntegrityError or pmserr.IntegrityError as err:
        error_code = err.args[0]
        if error_code == 1062:
            pass
        else:
            raise err


def _upload_hit(engine, gene_id, hit_id, expect, query_start, query_end):
    try:
        q = INSERT_INTO_GENE_DOMAIN.format(gene_id, hit_id, expect,
                                           query_start, query_end)
        engine.execute(q)
    except exc.IntegrityError or pmserr.IntegrityError as err:
        error_code = err.args[0]
        if error_code == 1062:
            pass
        else:
            raise err
