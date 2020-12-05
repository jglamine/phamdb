"""db.py - create and update phage databases.

Databases are designed to be compatible with Phamerator. Therefore, each
Phamerator database is a separate mysql database running on a mysql server. For
this reason, each database operation requires the same two arguments:

   server - a DatabaseServer object. Used to get connections to the database.
   id - the name of the mysql database.

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
from contextlib import closing
from enum import Enum
from urllib.parse import urlparse

import mysql.connector
from mysql.connector import errorcode
from pdm_utils.classes.alchemyhandler import AlchemyHandler
from pdm_utils.functions import fileio
from pdm_utils.functions import mysqldb_basic
from pdm_utils.functions import querying
from pdm_utils.pipelines import export_db
from sqlalchemy.sql import func

from pham import conserveddomain
from pham import genbank
from pham import mmseqs
from pham import query

# GLOBAL VARIABLES
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
            messages.append('{} errors occurred while validating genbank files.'.format(genbank_format_errors))
        
        return messages


def message_for_callback(code, *args, **kwargs):
    """Return a human readable string for callback messages from 'create' and 'rebuild'.
    """
    message = None
    if code == CallbackCode.genbank_format_error:
        phage_error = args[0]
        message = 'Error validating genbank file:' + phage_error.message()
    elif code == CallbackCode.duplicate_organism:
        phage_id = args[0]
        message = 'Adding phages resulted in duplicate phage. ID: {}'.format(phage_id)
    elif code == CallbackCode.duplicate_genbank_files:
        phage_id = args[0]
        message = 'The same genbank file occurs twice. Phage ID: {}'.format(phage_id)
    elif code == CallbackCode.file_does_not_exist:
        message = 'Unable to find uploaded genbank file.'
    elif code == CallbackCode.gene_id_already_exists:
        phage_id = args[0]
        message = 'Unable to add phage: ID: {}. A gene in this phage occurs elsewhere in the database.'.format(phage_id)
    elif code == CallbackCode.out_of_memory_error:
        message = 'Insufficient memory: This application requires at least 2 GB of RAM.'
    return message


def _default_callback(*args, **kwargs):
    pass


# MYSQL CONNECTION HANDLER
class DatabaseServer(object):
    """Represents a mysql server.

    Calling get_connection() returns a connection to the server.
    Connections are drawn from a connection pool.
    """
    def __init__(self, host, user, password='', pool_size=2, **kwargs):
        kwargs['host'] = host
        kwargs['user'] = user
        kwargs['password'] = password
        self._dbconfig = kwargs
        self._pool_size = pool_size
        self.alchemist = AlchemyHandler(username=user, password=password)
        self.alchemist.connect()

    @classmethod
    def from_url(cls, url, pool_size=2):
        result = urlparse(url)
        return cls(result.hostname, result.username, result.password, pool_size=pool_size)

    def get_credentials(self):
        host = self._dbconfig['host']
        user = self._dbconfig['user']
        password = self._dbconfig['password']
        return host, user, password

    def get_connection(self, **kwargs):
        """Returns a mysql connection object from the connection pool.

        By default, the connection is not associated with a database.
        Use database='databaseName' to connect to a specific database.
        This is the same as `USE databaseName` in SQL.
        """
        config = self._dbconfig.copy()
        config.update(kwargs)
        return mysql.connector.connect(pool_size=self._pool_size, **config)


# PROACTIVE DRY-RUN FUNCTIONS
def check_create(server, identifier, genbank_files=None):
    """Check if a call to create() will result in errors.

    This calls create(), but does not commit changes to the database. Use it
    to catch errors early before running long tasks.

    Returns (success, errors)
    Where success is a boolean and errors is a list of error messages.
    """
    observer = _CallbackObserver()

    try:
        success = create(server, identifier, genbank_files=genbank_files,
                         cdd_search=False, callback=observer.record_call,
                         commit=False)
    except DatabaseAlreadyExistsError:
        errors = list()
        errors.append('Database name is already in use.')
        errors += observer.error_messages()
        return False, errors
    except Exception:
        delete(server, identifier)
        raise

    delete(server, identifier)

    return success, observer.error_messages()


def check_rebuild(server, id, organism_ids=None, genbank_files=None):
    """Check if a call to rebuild() will result in errors.

    Calls rebuild() without commiting changes to the database. Use it to catch
    errors early before running long tasks.

    Returns (success, errors)
    Where success is a boolean and errors is a list of error messages.
    """
    observer = _CallbackObserver()

    try:
        success = rebuild(server, id,
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
def create(server, identifier, genbank_files=None, cdd_search=True,
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
    if query.database_exists(server.alchemist, identifier):
        raise DatabaseAlreadyExistsError

    server.alchemist.engine.execute(f"CREATE DATABASE `{identifier}`")
    server.alchemist.get_mysql_dbs()
    server.alchemist.database = str(identifier)
    server.alchemist.connect()

    callback(CallbackCode.status, 'initializing database', 1, 2)

    sql_script_path = os.path.join(_DATA_DIR, 'create_database.sql')
    _execute_sql_file(server.alchemist, sql_script_path)

    try:
        # insert phages and build phams
        success = rebuild(server, identifier, None, genbank_files,
                          cdd_search=cdd_search,
                          callback=callback,
                          commit=commit)
    except Exception:
        delete(server, identifier)
        raise
    if not success:
        delete(server, identifier)

    return success


# drops database
def delete(server, identifier):
    """Delete a Phamerator database.
    """
    server.alchemist.engine.execute(f"DROP DATABASE IF EXISTS `{identifier}`")


# deletes entries/IMPORTs entries and rePHAMERATEs and sometimes FIND_DOMAINS
def rebuild(server, identifier, organism_ids_to_delete=None,
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

    with closing(server.get_connection()) as cnx:
        if not query.database_exists(server.alchemist, identifier):
            raise DatabaseDoesNotExistError('No such database: {}'.format(id))

    db_alchemist = AlchemyHandler()
    db_alchemist.engine = server.alchemist.engine
    db_alchemist.database = identifier

    # open and validate genbank files
    # also detect duplicate phages
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
                if phage.id in phage_id_to_filenames:
                    duplicate_phage_ids.add(phage.id)
                else:
                    phage_id_to_filenames[phage.id] = []
                phage_id_to_filenames[phage.id].append(phage.filename)
            else:
                valid = False
                for error in phage.errors:
                    callback(CallbackCode.genbank_format_error, error)

    with closing(server.get_connection(database=identifier)) as cnx:
        cnx.start_transaction()

        callback(CallbackCode.status, 'checking for conflicts', 0, 1)
        try:
            # check for phages which are already on the server
            for phage_id in phage_id_to_filenames:
                if query.phage_exists(db_alchemist, phage_id):
                    if phage_id not in organism_ids_to_delete:
                        duplicate_phage_ids_on_server.add(phage_id)

            if len(duplicate_phage_ids_on_server) or len(duplicate_phage_ids):
                # duplicate phages were found, report them to the callback
                valid = False
                for phage_id in duplicate_phage_ids_on_server:
                    filename = phage_id_to_filenames[phage_id][0]
                    callback(CallbackCode.duplicate_organism, phage_id, filename)
                for phage_id in duplicate_phage_ids:
                    filenames = phage_id_to_filenames[phage_id]
                    callback(CallbackCode.duplicate_genbank_files, phage_id, filenames)

            if not valid:
                cnx.rollback()
                return False

            new_gene_ids = []
            new_gene_sequences = []

            # update version number
            _increment_version(cnx)

            
            # delete organisms
            for index, phage_id in enumerate(organism_ids_to_delete):
                callback(CallbackCode.status, 'deleting organisms', index,
                         len(organism_ids_to_delete))
                query.delete_phage(db_alchemist, phage_id)

            # validate and upload genbank files
            if genbank_files_to_add is not None:
                for index, path in enumerate(genbank_files_to_add):
                    callback(CallbackCode.status, 'uploading organisms', index,
                             len(genbank_files_to_add))
                    phage = genbank.read_file(path)
                    if not phage.is_valid():
                        for error in phage.errors:
                            callback(CallbackCode.genbank_format_error, error)
                        cnx.rollback()
                        return False
                    # upload phage
                    try:
                        phage.upload(cnx)
                    except mysql.connector.errors.IntegrityError:
                        callback(CallbackCode.gene_id_already_exists, phage.id)
                        cnx.rollback()
                        return False
                    for gene in phage.genes:
                        new_gene_ids.append(gene.gene_id)
                        new_gene_sequences.append(gene.translation)

            if not commit:
                cnx.rollback()
                return True

            # calculate phams
            if len(new_gene_ids) or len(organism_ids_to_delete):
                with closing(cnx.cursor()) as cursor:
                    # download all genes
                    sequences = []
                    gene_ids = []

                    callback(CallbackCode.status, 'calculating phams', 0, 2)

                    cursor.execute('SELECT translation, GeneID FROM gene')
                    gene_rows = cursor.fetchall()
                    for sequence, gene_id in gene_rows:
                        sequences.append(sequence)
                        gene_ids.append(gene_id)

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
                            cnx.rollback()
                            return False

                        original_phams = _read_phams(cursor)
                        pham_id_to_gene_ids = _assign_pham_ids(
                                                        pham_id_to_gene_ids,
                                                        original_phams)

                        # assign colors to the phams
                        original_colors = _read_pham_colors(cursor)
                        pham_id_to_color = _assign_pham_colors(
                                                        pham_id_to_gene_ids,
                                                        original_colors)

                        # clear old phams and colors from database
                        # write new phams and colors to database
                        cursor.execute('DELETE FROM pham')

                        for pham_id, color in pham_id_to_color.items():
                            cursor.execute("INSERT INTO pham (PhamID, Color) "
                                           f"VALUES ({pham_id}, '{color}')")

                        for pham_id, gene_ids in pham_id_to_gene_ids.items():
                            for gene_id in gene_ids:
                                cursor.execute(
                                        f"UPDATE gene SET PhamID = {pham_id} "
                                        f"WHERE GeneID = '{gene_id}'")

                    else:
                        # there are no genes in the database
                        # clear all phams and colors from database
                        cursor.execute('DELETE FROM pham')

            if cdd_search and len(new_gene_ids):
                callback(CallbackCode.status, 'searching conserved domain database', 0, 1)
                # search for genes in conserved domain database
                # only search for new genes
                conserveddomain.find_domains(cnx, new_gene_ids,
                                             new_gene_sequences, num_threads=2)

        except Exception:
            cnx.rollback()
            raise

        cnx.commit()

    return True


# imports whole sql database (GET_DB) and sometimes CONVERT_DB
def load(server, identifier, filepath):
    """Load a Phamerator database from an SQL dump.

    Also migrates to the new schema if needed.

    Raises:
        IOError when input file is not found
        DatabaseAlreadyExistsError
        ValueError when database schema is invalid
    """
    if not os.path.isfile(filepath):
        raise IOError('No such file: {}'.format(filepath))

    if query.database_exists(server.alchemist, identifier):
        raise DatabaseAlreadyExistsError(
                            f"Database {identifier} already exists.")

    server.alchemist.engine.execute(f"CREATE DATABASE `{identifier}`")
    server.alchemist.database = identifier

    try:
        mysqldb_basic.install_db(server.alchemist.engine, filepath)
    except:
        delete(server, identifier)
        raise


# EXPORT sql pipeline
def export(server, identifier, filepath):
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

    if not query.database_exists(server.alchemist, identifier):
        raise DatabaseDoesNotExistError(f"No such database {identifier}.")

    if os.path.exists(filepath):
        raise IOError('File already exists: {}'.format(filepath))
    if os.path.exists(version_filename):
        raise IOError('File already exists: {}'.format(version_filename))
    if os.path.exists(checksum_filename):
        raise IOError('File already exists: {}'.format(checksum_filename))

    directory.mkdir(exist_ok=True)

    version = query.version_number(server.alchemist)
    fileio.write_database(server.alchemist, version, directory,
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
def export_to_genbank(server, identifier, organism_id, filename):
    """Download a phage from the database to the given file or file handle.

    Returns an instance of `db_object.Phage`.

    Raises: PhageNotFoundError, DatabaseDoesNotExistError
    """
    if not query.database_exists(server.alchemist, identifier):
        raise DatabaseDoesNotExistError(f"No such database: {identifier}")

    if not query.phage_exists(server.alchemist, organism_id):
        raise PhageNotFoundError

    gnm = export_db.get_single_genome(server.alchemist, organism_id,
                                      get_features=True)
    genbank.write_file(gnm, filename)

    return gnm


# HELPER FUNCTIONS
class _PhamIdFinder(object):
    def __init__(self, phams, original_phams):
        """
        phams is a dictionary mapping pham_id to a frozenset of gene ids
        original_phams is a frozenset mapping pham_id to a frozenset of gene ids
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
    process = subprocess.check_call(command_list, stdin=file_handle)
    file_handle.close()


# API DATA RETRIEVAL
class DatabaseSummaryModel(object):
    def __init__(self, organism_count, pham_count, orpham_count,
                 conserved_domain_hit_count):
        self.number_of_organisms = organism_count
        self.number_of_phams = pham_count
        self.number_of_orphams = orpham_count
        self.number_of_conserved_domain_hits = conserved_domain_hit_count


def summary(server, identifier):
    """Returns a DatabaseSummaryModel with information on the database.
    """
    if not query.database_exists(server.alchemist, identifier):
        raise DatabaseDoesNotExistError(f"No such database: {identifier}")

    temp_alchemist = AlchemyHandler()
    temp_alchemist.engine = server.alchemist.engine
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


def list_organisms(server, identifier):
    """Returns a list of organisms in the database.

    Each organisms is an instance of OrganismSummaryModel.

    Raises: DatabaseDoesNotExistError
    """
    if not query.database_exists(server.alchemist, identifier):
        raise DatabaseDoesNotExistError(f"No such database: {id}")

    temp_alchemist = AlchemyHandler()
    temp_alchemist.engine = server.alchemist.engine
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


# REDUNDANT PIPELINE HELPER FUNCTIONS
# Used to set up pipeline like rebuild or load
def _is_schema_valid(cnx):
    """Return True if the databases has the tables required by a Phamerator database.

    Checks for these tables:
        domain
        gene
        gene_domain
        phage
        pham
        pham_color
    """
    with closing(cnx.cursor()) as cursor:
        cursor.execute('''
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_name IN (
              'domain', 'gene', 'gene_domain', 'phage', 'pham', 'pham_color'
            )
                       ''')
        tables_found = cursor.fetchall()[0][0]

    return tables_found == 6


def _update_schema(cnx):
    """Migrate databases from the old Phamerator schema.

    The new schema is backwards compatible with Phamerator.
    The changes made are as follows:

    Add ON DELETE CASCADE constraints
    Increase VARCHAR length
    DELETE FROM scores_summary, node
    DROP TABLE pham_history, pham_old
    CREATE TABLE version
    """
    with closing(cnx.cursor()) as cursor:
        # add version table
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS version (
                         version int unsigned NOT NULL PRIMARY KEY
                       )''')
        cursor.execute('SELECT * FROM version')
        if len(cursor.fetchall()) == 0:
            cursor.execute('''INSERT INTO version (version)
                              VALUES (0)
                           ''')

        # increase VARCHAR length
        # select character_maximum_length from information_schema.columns where table_schema = 'test_database' and table_name = 'gene' and column_name = 'name';
        cursor.execute('''
                       SELECT character_maximum_length
                       FROM information_schema.columns
                       WHERE table_schema = DATABASE()
                        AND table_name = 'gene'
                        AND column_name = 'Name'
                       ''')
        if cursor.fetchall()[0][0] != 127:
            cursor.execute('ALTER TABLE domain MODIFY hit_id VARCHAR(127)')
            cursor.execute('ALTER TABLE domain MODIFY Name VARCHAR(127)')
            cursor.execute('ALTER TABLE gene MODIFY GeneID VARCHAR(127)')
            cursor.execute('ALTER TABLE gene MODIFY PhageID VARCHAR(127)')
            cursor.execute('ALTER TABLE gene MODIFY Name VARCHAR(127)')
            cursor.execute('ALTER TABLE gene MODIFY LeftNeighbor VARCHAR(127)')
            cursor.execute('ALTER TABLE gene MODIFY RightNeighbor VARCHAR(127)')
            cursor.execute('ALTER TABLE gene_domain MODIFY GeneID VARCHAR(127)')
            cursor.execute('ALTER TABLE gene_domain MODIFY hit_id VARCHAR(127)')
            cursor.execute('ALTER TABLE node MODIFY hostname VARCHAR(127)')
            cursor.execute('ALTER TABLE phage MODIFY PhageID VARCHAR(127)')
            cursor.execute('ALTER TABLE phage MODIFY Name VARCHAR(127)')
            cursor.execute('ALTER TABLE phage MODIFY Isolated VARCHAR(127)')
            cursor.execute('ALTER TABLE phage MODIFY HostStrain VARCHAR(127)')
            cursor.execute('ALTER TABLE pham MODIFY GeneID VARCHAR(127)')
            cursor.execute('ALTER TABLE scores_summary MODIFY query VARCHAR(127)')
            cursor.execute('ALTER TABLE scores_summary MODIFY subject VARCHAR(127)')

        # add ON DELETE CASCADE ON UPDATE CASCADE constraints
        cursor.execute('''
                       SELECT COUNT(delete_rule)
                       FROM information_schema.referential_constraints
                       WHERE constraint_schema = DATABASE()
                        AND delete_rule = 'CASCADE'
                       ''')
        if cursor.fetchall()[0][0] < 6:
            # some tables have the wrong name for `pham_ibfk_1`
            _drop_foreign_key(cursor, 'pham', 'pham_ibfk_2')

            _migrate_foreign_key(cursor, 'gene', 'gene_ibfk_1', 'PhageID', 'phage', 'PhageID')
            _migrate_foreign_key(cursor, 'gene_domain', 'gene_domain_ibfk_1', 'GeneID', 'gene', 'GeneID')
            _migrate_foreign_key(cursor, 'gene_domain', 'gene_domain_ibfk_2', 'hit_id', 'domain', 'hit_id')
            _migrate_foreign_key(cursor, 'pham', 'pham_ibfk_1', 'GeneID', 'gene', 'GeneID')
            _migrate_foreign_key(cursor, 'scores_summary', 'scores_summary_ibfk_1', 'query', 'gene', 'GeneID')
            _migrate_foreign_key(cursor, 'scores_summary', 'scores_summary_ibfk_2', 'subject', 'gene', 'GeneID')

        # clear unnecessary tables
        # to maintain backwards compatibility, the empty tables are kept.
        cursor.execute('DELETE FROM scores_summary')
        cursor.execute('DELETE FROM node')

        # delete unnecessary tables
        cursor.execute('DROP TABLE IF EXISTS pham_old')
        cursor.execute('DROP TABLE IF EXISTS pham_history')

        # Add a column to keep track of which genes have been searched for
        # in the conserved domain database
        # This column is used by the legacy k_phamerate scripts.
        cursor.execute('''
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            AND table_name = 'gene'
            AND column_name = 'cdd_status'
            ''')
        cdd_column_exists = cursor.fetchall()[0][0] == 1
        if not cdd_column_exists:
            cursor.execute('''
                ALTER TABLE `gene`
                ADD COLUMN `cdd_status` TINYINT(1) NOT NULL AFTER `blast_status`
            ''')
            cursor.execute('''
                UPDATE gene
                SET cdd_status = 0
            ''')
    cnx.commit()


def _migrate_foreign_key(cursor, this_table, constraint, this_feild,
                         other_table, other_feild):
    """Replace a foreign key constraint with one which specifies to cascade
    on delete and update.
    """
    _drop_foreign_key(cursor, this_table, constraint)

    cursor.execute('''
                   ALTER TABLE {}
                   ADD CONSTRAINT {} FOREIGN KEY ({}) REFERENCES {} ({})
                   ON UPDATE CASCADE
                   ON DELETE CASCADE
                   '''.format(this_table, constraint, this_feild, other_table,
                              other_feild))


def _drop_foreign_key(cursor, table, constraint):
    try:
        cursor.execute('ALTER TABLE {} DROP FOREIGN KEY {}'.format(
                                                            table, constraint))
    except mysql.connector.errors.Error as e:
        if e.errno == errorcode.ER_ERROR_ON_RENAME:
            # the constraint did not already exist
            pass
        else:
            raise


def _increment_version(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute("UPDATE version SET version=version+1")


def _read_phams(cursor):
    """Reads phams from the database.

    Returns a dictionary mapping pham_id to a set of gene ids.
    """
    phams = {}
    cursor.execute("SELECT PhamID, GeneID FROM gene")
    results = cursor.fetchall()
    for pham_id, gene_id in results:
        pham_set = phams.get(pham_id, set())
        pham_set.add(gene_id)

    return phams


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


def _read_pham_colors(cursor):
    """Return a dictionary mapping pham_id to color
    """
    pham_colors = {}
    cursor.execute("SELECT PhamID, Color FROM pham")
    for pham_id, color in cursor:
        pham_colors[pham_id] = color
    return pham_colors


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
