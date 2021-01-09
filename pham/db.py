"""db.py - create and update phage databases.

Databases are designed to be compatible with Phamerator. Therefore, each
Phamerator database is a separate mysql database running on a mysql server. For
this reason, each database operation requires the same two arguments:

   server - An AlchemyHandler object. Used to manage connections to databases.
   identifier - The name of a mysql database.

When creating or deleting a database, you can supply a callback function which
is used to report status and error messages. This function will be called
during database creation so that status and error messages can be reported
asynchronously.

The first argument to the callback is an instance of the CallbackCode enum.
Subsequent arguments are different depending on the CallbackCode used.
"""

import colorsys
import hashlib
import os
import random
import shlex
import subprocess
from enum import Enum
from pathlib import Path

from pdm_utils.classes.alchemyhandler import AlchemyHandler
from pdm_utils.functions import (fileio, mysqldb, mysqldb_basic, querying)
from pdm_utils.pipelines import export_db
from sqlalchemy.sql import func

from pham import conserveddomain
from pham import genbank
from pham import mmseqs
from pham import query

# GLOBAL VARIABLES
# -----------------------------------------------------------------------------
_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


CallbackCode = Enum("CallbackCode",
                    "status "
                    "genbank_format_error "
                    "duplicate_organism "
                    "duplicate_genbank_files "
                    "file_does_not_exist "
                    "gene_id_already_exists "
                    "out_of_memory_error")


# ERRORS
# -----------------------------------------------------------------------------
class DatabaseError(Exception):
    pass


class InvalidCredentials(DatabaseError):
    pass


class DatabaseAlreadyExistsError(DatabaseError):
    pass


class DatabaseDoesNotExistError(DatabaseError):
    pass


class PhageNotFoundError(DatabaseError):
    pass


# CALLBACK HANDLERS
# -----------------------------------------------------------------------------
class _CallbackObserver(object):
    def __init__(self):
        self.calls = []

    def record_call(self, code, *args, **kwargs):
        self.calls.append((code, args, kwargs))

    def error_messages(self):
        messages = []
        genbank_format_errors = 0
        for code, args, kwargs in self.calls:
            if code == CallbackCode.genbank_format_error:
                genbank_format_errors += 1
            elif code != CallbackCode.status:
                messages.append(message_for_callback(code, *args, **kwargs))

        if genbank_format_errors:
            messages.append(f"{genbank_format_errors} errors occurred "
                            "while validating genbank files.")

        return messages


def message_for_callback(code, *args, **kwargs):
    """Return a human readable string for callback messages from
       'create' and 'rebuild'.
    """
    message = None
    if code == CallbackCode.genbank_format_error:
        phage_error = args[0]
        message = "Error validating genbank file:" + phage_error.message()
    elif code == CallbackCode.duplicate_organism:
        phage_id = args[0]
        message = f"Adding phages resulted in duplicate phage. ID: {phage_id}"
    elif code == CallbackCode.duplicate_genbank_files:
        phage_id = args[0]
        message = "The same genbank file occurs twice. Phage ID: {phage_id}"
    elif code == CallbackCode.file_does_not_exist:
        message = "Unable to find uploaded genbank file."
    elif code == CallbackCode.gene_id_already_exists:
        phage_id = args[0]
        message = (f"Unable to add phage: ID: {phage_id}. "
                   "A gene in this phage occurs elsewhere in the database.")
    elif code == CallbackCode.out_of_memory_error:
        message = ("Insufficient memory: "
                   "This application requires at least 2 GB of RAM.")
    return message


def _default_callback(*args, **kwargs):
    pass


# PROACTIVE DRY-RUN FUNCTIONS
# -----------------------------------------------------------------------------
def check_create(alchemist, identifier, genbank_files=None):
    """Check if a call to create() will result in errors.

    This calls create(), but does not commit changes to the database. Use it
    to catch errors early before running long tasks.

    Returns (success, errors)
    Where success is a boolean and errors is a list of error messages.
    """
    observer = _CallbackObserver()

    try:
        success = create(alchemist, identifier, genbank_files=genbank_files,
                         cdd_search=False, callback=observer.record_call,
                         commit=False)
    except DatabaseAlreadyExistsError:
        errors = list()
        errors.append('Database name is already in use.')
        errors += observer.error_messages()
        return False, errors
    except Exception:
        delete(alchemist, identifier)
        raise

    delete(alchemist, identifier)

    return success, observer.error_messages()


def check_rebuild(alchemist, identifier, organism_ids=None,
                  genbank_files=None):
    """Check if a call to rebuild() will result in errors.

    Calls rebuild() without commiting changes to the database. Use it to catch
    errors early before running long tasks.

    Returns (success, errors)
    Where success is a boolean and errors is a list of error messages.
    """
    observer = _CallbackObserver()

    try:
        success = rebuild(alchemist, identifier,
                          organism_ids_to_delete=organism_ids,
                          genbank_files_to_add=genbank_files,
                          cdd_search=False,
                          callback=observer.record_call,
                          commit=False)
    except DatabaseDoesNotExistError:
        errors = list()
        errors.append('Database does not exist.')
        errors += observer.error_messages()
        return False, errors

    return success, observer.error_messages()


# PIPELINE FUNCTIONS
# creates new database and IMPORTs
def create(alchemist, identifier, genbank_files=None, cdd_search=True,
           commit=True, callback=_default_callback):
    """Create a phamerator database.

    Status and errors are reported to `callback`. The first argument of each
    callback is an instance of the `CallbackCode` enum.

    genbank_files: a list of paths to genbank files.
    cdd_search (boolean): search for genes in NCBI conserved domain database.
    commit (boolean): Commit changes to the database.

    Returns True if the operation succeed, False if it failed.

    Exceptions: DatabaseAlreadyExistsError
    """
    identifier = str(identifier)

    # create a blank database
    callback(CallbackCode.status, 'initializing database', 0, 2)
    if query.database_exists(alchemist, identifier):
        raise DatabaseAlreadyExistsError("No such database: {}".format(
                                                                identifier))

    alchemist.engine.execute(f"CREATE DATABASE `{identifier}`")
    alchemist.get_mysql_dbs()
    alchemist.database = str(identifier)
    alchemist.connect()

    callback(CallbackCode.status, 'initializing database', 1, 2)

    sql_script_path = os.path.join(_DATA_DIR, 'create_database.sql')
    _execute_sql_file(alchemist, sql_script_path)

    try:
        # insert phages and build phams
        success = rebuild(alchemist, identifier, None, genbank_files,
                          cdd_search=cdd_search,
                          callback=callback,
                          commit=commit)
    except Exception:
        delete(alchemist, identifier)
        raise
    if not success:
        delete(alchemist, identifier)

    return success


# drops database
def delete(alchemist, identifier):
    """Delete a Phamerator database.
    """
    alchemist.engine.execute(f"DROP DATABASE IF EXISTS `{identifier}`")


# deletes entries/IMPORTs entries and rePHAMERATEs and sometimes FIND_DOMAINS
def rebuild(alchemist, identifier, organism_ids_to_delete=None,
            genbank_files_to_add=None, cdd_search=True, commit=True,
            callback=_default_callback):
    """Modify an existing Phamerator database, rebuilding phams.

    Status and errors are reported to `callback`. The first argument of each
    callback is an instance of the `CallbackCode` enum.

    organism_ids_to_delete: a list of ids of phages to delete.
    genbank_files_to_add: a list of paths to genbank files.
    cdd_search (boolean): search for each gene in NCBI conserved domain
    database.
    commit (boolean): Commit changes to the database.

    Returns True if the operation succeed, False if it failed.
    """
    if organism_ids_to_delete is None:
        organism_ids_to_delete = []
    if genbank_files_to_add is None:
        genbank_files_to_add = []

    if not query.database_exists(alchemist, identifier):
        raise DatabaseDoesNotExistError('No such database: {}'.format(
                                                                identifier))

    db_alchemist = AlchemyHandler()
    db_alchemist.engine = alchemist.engine
    db_alchemist.database = identifier
    db_alchemist.build_engine()

    if not validate_genbank_files(genbank_files_to_add,
                                  organism_ids_to_delete, callback):
        return False

    # update version number
    mysqldb.change_version(alchemist.engine)

    with db_alchemist.engine.begin() as engine:
        delete_redundant_organisms(db_alchemist, engine,
                                   organism_ids_to_delete, callback)

        new_gene_ids = []
        new_gene_sequences = []
        if not upload_genbank_files(
                                db_alchemist, genbank_files_to_add,
                                callback, new_gene_ids, new_gene_sequences):
            engine.rollback()
            return False

        if not commit:
            engine.rollback()
            return True

        # calculate phams
        if new_gene_ids or organism_ids_to_delete:
            calculate_phams(db_alchemist, engine)

    if cdd_search and len(new_gene_ids):
        callback(CallbackCode.status,
                 'searching conserved domain database', 0, 1)
        # search for genes in conserved domain database
        # only search for new genes
        conserveddomain.find_domains(db_alchemist, new_gene_ids,
                                     new_gene_sequences, num_threads=2)

    return True


# imports whole sql database (GET_DB) and sometimes CONVERT_DB
def load(alchemist, identifier, filepath):
    """Load a Phamerator database from an SQL dump.

    Also migrates to the new schema if needed.

    Raises:
        IOError when input file is not found
        DatabaseAlreadyExistsError
        ValueError when database schema is invalid
    """
    if not os.path.isfile(filepath):
        raise IOError('No such file: {}'.format(filepath))

    if query.database_exists(alchemist, identifier):
        raise DatabaseAlreadyExistsError(
                            "Database {} already exists.".format(identifier))

    alchemist.engine.execute(f"CREATE DATABASE `{identifier}`")

    temp_alchemist = AlchemyHandler()
    temp_alchemist.engine = alchemist.engine
    temp_alchemist.database = identifier
    temp_alchemist.build_engine()

    try:
        mysqldb_basic.install_db(temp_alchemist.engine, Path(filepath))
    except:
        delete(alchemist, identifier)
        raise


# EXPORT sql pipeline
def export(alchemist, identifier, filepath):
    """Saves a SQL dump of the database to the given file.

    Creates three files:
        <filename>.sql
        <filename>.version
        <filename>.md5sum
    """
    directory = filepath.parent
    base_path = filepath.with_suffix("")  # remove extension from filename
    version_filename = base_path.with_suffix(".version")
    checksum_filename = base_path.with_suffix(".md5sum")

    if not query.database_exists(alchemist, identifier):
        raise DatabaseDoesNotExistError("No such database: {}.".format(
                                                                identifier))

    temp_alchemist = AlchemyHandler()
    temp_alchemist.engine = alchemist.engine
    temp_alchemist.database = identifier
    temp_alchemist.build_engine()

    if os.path.exists(filepath):
        raise IOError('File already exists: {}'.format(filepath))
    if os.path.exists(version_filename):
        raise IOError('File already exists: {}'.format(version_filename))
    if os.path.exists(checksum_filename):
        raise IOError('File already exists: {}'.format(checksum_filename))

    directory.mkdir(exist_ok=True)

    version = query.version_number(temp_alchemist)
    fileio.write_database(temp_alchemist, version, directory,
                          db_name=base_path.name)

    # calculate checksum
    m = hashlib.md5()
    with open(filepath, 'rb') as sql_file:
        while True:
            data = sql_file.read(8192)
            if not data:
                break
            m.update(data)

    # write .md5sum file
    checksum = m.hexdigest()
    with checksum_filename.open(mode="w") as out_file:
        out_file.write(f"{checksum}  {filepath}\n")


# EXPORT gb pipeline
def export_to_genbank(alchemist, identifier, organism_id, filehandle):
    """Download a phage from the database to the given file or file handle.

    Returns an instance of `db_object.Phage`.

    Raises: PhageNotFoundError, DatabaseDoesNotExistError
    """
    if not query.database_exists(alchemist, identifier):
        raise DatabaseDoesNotExistError("No such database: {}".format(
                                                            identifier))

    temp_alchemist = AlchemyHandler()
    temp_alchemist.engine = alchemist.engine
    temp_alchemist.database = identifier

    if not query.phage_exists(temp_alchemist, organism_id):
        raise PhageNotFoundError

    gnm = export_db.get_single_genome(temp_alchemist, organism_id,
                                      get_features=True)
    genbank.write_file(gnm, filehandle)

    return gnm


# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
class _PhamIdFinder(object):
    def __init__(self, phams, original_phams):
        """
        phams is a dictionary mapping pham_id to a frozenset of gene ids
        original_phams is a frozenset mapping pham_id to a frozenset of gene
        ids
        """
        # build helper data structures
        self.original_genes = set()
        for genes in original_phams.values():
            self.original_genes.update(genes)

        self.genes = set()
        for genes in phams.values():
            self.genes.update(genes)

        self.original_genes_to_pham_id = {}
        for pham_id, genes in original_phams.items():
            self.original_genes_to_pham_id[genes] = pham_id

        self.original_gene_to_pham_id = {}
        for pham_id, genes in original_phams.items():
            for gene_id in genes:
                self.original_gene_to_pham_id[gene_id] = pham_id

        self.phams = phams
        self.original_phams = original_phams

    def find_original_pham_id(self, genes):
        if genes in self.original_genes_to_pham_id:
            # pham is identical to original pham
            # use the old id
            return self.original_genes_to_pham_id[genes]

        # find the original pham
        old_genes = genes.intersection(self.original_genes)
        if len(old_genes) == 0:
            # this is a new pham with all new genes
            # assign a new id
            return

        # check for a join
        # make sure these genes all come from the same pham
        original_pham_id = None
        for gene_id in old_genes:
            temp_pham_id = self.original_gene_to_pham_id[gene_id]
            if original_pham_id is None:
                original_pham_id = temp_pham_id
            elif original_pham_id != temp_pham_id:
                # these genes come from different phams
                # this means that two phams were joined into one
                # assign a new id
                return

        # check for a split
        # make sure none of the missing genes are in another pham
        original_pham = self.original_phams[original_pham_id]
        missing_genes = original_pham.difference(genes)
        if len(missing_genes):
            for gene in missing_genes:
                if gene in self.genes:
                    # a missing gene is in another pham
                    # this means that the pham was split into two
                    # assign a new id
                    return

        # an original pham was modified by adding or removing genes
        # use the old pham id
        return original_pham_id


def _execute_sql_file(alchemist, filepath):
    file_handle = open(filepath, "r")
    command_string = f"mysql -u {alchemist.username} -p{alchemist.password}"
    if alchemist.database:
        command_string = " ".join([command_string, alchemist.database])

    command_list = shlex.split(command_string)
    subprocess.check_call(command_list, stdin=file_handle)
    file_handle.close()


# REBUILD HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def validate_genbank_files(db_alchemist, genbank_files_to_add,
                           organism_ids_to_delete, callback):
    valid = True

    phage_id_to_filenames = {}
    duplicate_phage_ids = set()
    duplicate_phage_ids_on_server = set()
    if genbank_files_to_add is not None:
        for index, path in enumerate(genbank_files_to_add):
            callback(CallbackCode.status, 'validating genbank files',
                     index, len(genbank_files_to_add))
            try:
                phage = genbank.read_file(path)
            except IOError:
                valid = False
                callback(CallbackCode.file_does_not_exist, path)
                continue

            # May be redundant, parse genbank records cover??
            if phage.is_valid():
                # check for duplicate phages
                if phage.id in phage_id_to_filenames.keys():
                    duplicate_phage_ids.add(phage.id)

                filenames = phage_id_to_filenames.get(phage.id, list())
                filenames.append(phage.filename)

                phage_id_to_filenames[phage.id] = filenames
            else:
                valid = False
                for error in phage.errors:
                    callback(CallbackCode.genbank_format_error, error)

    if not valid:
        return False

    callback(CallbackCode.status, 'checking for conflicts', 0, 1)

    for phage_id in phage_id_to_filenames:
        if query.phage_exists(db_alchemist, phage_id):
            if phage_id not in organism_ids_to_delete:
                duplicate_phage_ids_on_server.add(phage_id)

    if len(duplicate_phage_ids_on_server) or len(duplicate_phage_ids):
        # duplicate phages were found, report them to the callback
        valid = False
        for phage_id in duplicate_phage_ids_on_server:
            filename = phage_id_to_filenames[phage_id][0]
            callback(CallbackCode.duplicate_organism, phage_id,
                     filename)
        for phage_id in duplicate_phage_ids:
            filenames = phage_id_to_filenames[phage_id]
            callback(CallbackCode.duplicate_genbank_files, phage_id,
                     filenames)

    return valid


def delete_redundant_organisms(db_alchemist, engine, organism_ids_to_delete,
                               callback):
    for index, phage_id in enumerate(organism_ids_to_delete):
        callback(CallbackCode.status, 'deleting organisms', index,
                 len(organism_ids_to_delete))
        query.delete_phage(db_alchemist.metadata, engine, phage_id)


def upload_genbank_files(engine, genbank_files_to_add, callback,
                         new_gene_ids, new_gene_sequences):
    if genbank_files_to_add is not None:
        for index, path in enumerate(genbank_files_to_add):
            callback(CallbackCode.status, 'uploading organisms', index,
                     len(genbank_files_to_add))
            phage = genbank.read_file(path)
            if not phage.is_valid():
                for error in phage.errors:
                    callback(CallbackCode.genbank_format_error, error)
                return False
            # upload phage
            try:
                phage.upload(engine)
            except:
                callback(CallbackCode.gene_id_already_exists, phage.id)
                return False
            for gene in phage.genes:
                new_gene_ids.append(gene.gene_id)
                new_gene_sequences.append(gene.translation)


def calculate_phams(db_alchemist, engine, callback):
    callback(CallbackCode.status, 'calculating phams', 0, 2)
    sequences, gene_ids = query.retrieve_gene_sequences_and_geneids(
                                        db_alchemist.metadata, engine)

    # cluster genes into phams
    if len(gene_ids):
        try:
            pham_id_to_gene_ids = mmseqs.cluster(
                sequences, gene_ids,
                on_first_iteration_done=lambda: callback(
                                        CallbackCode.status,
                                        'calculating phams',
                                        1, 2))
        except MemoryError:
            # not enough ram
            callback(CallbackCode.out_of_memory_error)
            engine.rollback()
            return False

        original_phams = query.get_pham_geneids(
                                        db_alchemist.metadata, engine)
        pham_id_to_gene_ids = _assign_pham_ids(
                                        pham_id_to_gene_ids,
                                        original_phams)

        # assign colors to the phams
        original_colors = query.get_pham_colors(
                                        db_alchemist, engine)
        pham_id_to_color = _assign_pham_colors(
                                        pham_id_to_gene_ids,
                                        original_colors)

        # clear old phams and colors from database
        # write new phams and colors to database
        engine.execute('DELETE FROM pham')

        for pham_id, color in pham_id_to_color.items():
            engine.execute("INSERT INTO pham (PhamID, Color) "
                           f"VALUES ({pham_id}, '{color}')")

        for pham_id, gene_ids in pham_id_to_gene_ids.items():
            for gene_id in gene_ids:
                engine.execute(
                        f"UPDATE gene SET PhamID = {pham_id} "
                        f"WHERE GeneID = '{gene_id}'")

    else:
        # there are no genes in the database
        # clear all phams and colors from database
        engine.execute('DELETE FROM pham')


def _assign_pham_ids(phams, original_phams):
    """Re-assigns pham ids to match the original pham ids.

    If a pham contains all new genes, use a new id.
    If a pham was created by joining old phams, use a new id.
    If a pham was created by splitting an old pham, use a new id.
    Otherwise, use the old id of the original pham.

    Returns a dictionary mapping pham_id to a frozenset of gene ids.
    """
    # convert to frozen sets
    for key, value in phams.items():
        phams[key] = frozenset(value)
    for key, value in original_phams.items():
        original_phams[key] = frozenset(value)

    final_phams = {}
    next_id = 1
    if len(original_phams):
        next_id = max(original_phams.keys()) + 1

    id_finder = _PhamIdFinder(phams, original_phams)

    for genes in phams.values():
        original_pham_id = id_finder.find_original_pham_id(genes)
        if original_pham_id is None:
            original_pham_id = next_id
            next_id += 1
        final_phams[original_pham_id] = genes

    return final_phams


def _assign_pham_colors(phams, original_colors):
    """Returns a dictionary mapping pham_id to color.

    phams is a dictionary mapping pham_id to a list of gene ids.
    original_colors is a dictionary mapping pham_id to color.
    """
    pham_colors = {}
    for pham_id, genes in phams.items():
        pham_colors[pham_id] = original_colors.get(pham_id, _make_color(genes))
    return pham_colors


def _make_color(gene_ids):
    """Return a color to use for the given pham.

    Returns a hex string. ex: '#FFFFFF'

    Phams with only one gene are white.
    All other phams are given a random color.
    """
    if len(gene_ids) == 1:
        return '#FFFFFF'

    hue = random.uniform(0, 1)
    sat = random.uniform(0.5, 1)
    val = random.uniform(0.8, 1)

    red, green, blue = colorsys.hsv_to_rgb(hue, sat, val)
    hexcode = '#%02x%02x%02x' % (int(red) * 255,
                                 int(green) * 255,
                                 int(blue) * 255)
    return hexcode


# API DATA RETRIEVAL
# -----------------------------------------------------------------------------
class DatabaseSummaryModel(object):
    def __init__(self, organism_count, pham_count, orpham_count,
                 conserved_domain_hit_count):
        self.number_of_organisms = organism_count
        self.number_of_phams = pham_count
        self.number_of_orphams = orpham_count
        self.number_of_conserved_domain_hits = conserved_domain_hit_count


def summary(alchemist, identifier):
    """Returns a DatabaseSummaryModel with information on the database.
    """
    if not query.database_exists(alchemist, identifier):
        raise DatabaseDoesNotExistError(f"No such database: {identifier}")

    temp_alchemist = AlchemyHandler()
    temp_alchemist.engine = alchemist.engine
    temp_alchemist.database = identifier

    phage_count = query.count_phages(temp_alchemist)
    pham_count = query.count_phams(temp_alchemist)
    orpham_count = query.count_orphan_genes(temp_alchemist)
    domain_hits = query.count_domains(temp_alchemist)

    return DatabaseSummaryModel(phage_count, pham_count, orpham_count,
                                domain_hits)


class OrganismSummaryModel(object):
    def __init__(self, name, identifier, gene_count):
        self.name = name
        self.id = identifier
        self.genes = gene_count


def list_organisms(alchemist, identifier):
    """Returns a list of organisms in the database.

    Each organisms is an instance of OrganismSummaryModel.

    Raises: DatabaseDoesNotExistError
    """
    if not query.database_exists(alchemist, identifier):
        raise DatabaseDoesNotExistError(f"No such database: {id}")

    temp_alchemist = AlchemyHandler()
    temp_alchemist.engine = alchemist.engine
    temp_alchemist.database = identifier

    phage_obj = temp_alchemist.metadata.tables["phage"]
    gene_obj = temp_alchemist.metadata.tables["gene"]
    phageid_obj = phage_obj.c.PhageID
    name_obj = phage_obj.c.Name
    geneid_obj = gene_obj.c.GeneID

    columns = [name_obj, phageid_obj, func.count(geneid_obj)]
    q = querying.build_select(temp_alchemist.graph, columns)
    q = q.group_by(phageid_obj)

    organism_data = querying.execute(temp_alchemist.engine, q)

    organisms = []
    for data_dict in organism_data:
        organisms.append(OrganismSummaryModel(data_dict["Name"],
                                              data_dict["PhageID"],
                                              data_dict["count_1"]))

    return organisms
