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
import subprocess32
import mysql.connector
from mysql.connector import errorcode
from contextlib import closing
from urlparse import urlparse
from enum import Enum

from pdm_utils.classes.alchemyhandler import AlchemyHandler
from pdm_utils.pipelines import export_db
from pdm_utils.pipelines import import_genome
from pdm_utils.pipelines import phamerate
from pdm_utils.pipelines import convert_db
from pdm_utils.pipelines import find_domains

import pham.conserved_domain
import pham.genbank
import pham.kclust
import pham.query

#GLOBAL VARIABLES
#-----------------------------------------------------------------------------
_DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')

CallbackCode = Enum('status',
                    'genbank_format_error',
                    'duplicate_organism',
                    'duplicate_genbank_files',
                    'file_does_not_exist',
                    'gene_id_already_exists',
                    'out_of_memory_error')

#ERRORS
#-----------------------------------------------------------------------------
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

#CALLBACK HANDLERS
#-----------------------------------------------------------------------------
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

#MYSQL CONNECTION HANDLER
#-----------------------------------------------------------------------------
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
        user =  self._dbconfig['user']
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


#PROACTIVE DRY-RUN FUNCTIONS
#-----------------------------------------------------------------------------

def check_create(server, id, genbank_files=None):
    """Check if a call to create() will result in errors.

    This calls create(), but does not commit changes to the database. Use it
    to catch errors early before running long tasks.

    Returns (success, errors)
    Where success is a boolean and errors is a list of error messages.
    """
    observer = _CallbackObserver()

    try:
        success = create(server, id,
                        genbank_files=genbank_files,
                        cdd_search=False,
                        callback=observer.record_call,
                        commit=False)
    except DatabaseAlreadyExistsError as e:
        errors = []
        errors.append('Database name is already in use.')
        errors += observer.error_messages()
        return False, errors
    except Exception:
        delete(server, id)
        raise

    delete(server, id)

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
    except DatabaseDoesNotExistError as e:
        errors = []
        errors.append('Database does not exist.')
        errors += observer.error_messages()
        return False, errors

    return success, observer.error_messages()

#PIPELINE FUNCTIONS
#-----------------------------------------------------------------------------
#creates new database and IMPORTs
def create(server, id, genbank_files=None, cdd_search=True, commit=True,
           callback=_default_callback):
    """Create a phamerator database.

    Status and errors are reported to `callback`. The first argument of each
    callback is an instance of the `CallbackCode` enum.

    genbank_files: a list of paths to genbank files.
    cdd_search (boolean): search for each gene in NCBI conserved domain database.
    commit (boolean): Commit changes to the database.

    Returns True if the operation succeed, False if it failed.

    Exceptions: DatabaseAlreadyExistsError
    """
    # create a blank database
    callback(CallbackCode.status, 'initializing database', 0, 2)
    if pham.query.database_exists(server.alchemist, id):
        raise DatabaseAlreadyExistsError

    server.alchemist.engine.execute(f"CREATE DATABASE {id}")
    server.alchemist.database = database

    callback(CallbackCode.status, 'initializing database', 1, 2)


    sql_script_path = os.path.join(_DATA_DIR, 'create_database.sql')
    _execute_sql_file(alchemist, sql_script_path)
    try:
        # insert phages and build phams
        success = rebuild(server, id, None, genbank_files,
                          cdd_search=cdd_search,
                          callback=callback,
                          commit=commit)
    except Exception:
        delete(server, id)
        raise
    if not success:
        delete(server, id)

    return success

#drops database
def delete(server, id):
    """Delete a Phamerator database.
    """
    with closing(server.get_connection()) as cnx:
        with closing(cnx.cursor()) as cursor:
            cursor.execute('DROP DATABASE IF EXISTS {};'.format(id))
        cnx.commit()

#deletes entries/IMPORTs entries and rePHAMERATEs and sometimes FIND_DOMAINS
def rebuild(server, id, organism_ids_to_delete=None, genbank_files_to_add=None,
            cdd_search=True, commit=True, callback=_default_callback):
    """Modify an existing Phamerator database, rebuilding phams.

    Status and errors are reported to `callback`. The first argument of each
    callback is an instance of the `CallbackCode` enum.

    organism_ids_to_delete: a list of ids of phages to delete.
    genbank_files_to_add: a list of paths to genbank files.
    cdd_search (boolean): search for each gene in NCBI conserved domain database.
    commit (boolean): Commit changes to the database.

    Returns True if the operation succeed, False if it failed.
    """
    if organism_ids_to_delete is None:
        organism_ids_to_delete = []
    if genbank_files_to_add is None:
        genbank_files_to_add = []

    with closing(server.get_connection()) as cnx:
        if not pham.query.database_exists(cnx, id):
            raise DatabaseDoesNotExistError('No such database: {}'.format(id))

    # open and validate genbank files
    # also detect duplicate phages
    valid = True
    phage_id_to_filenames = {}
    duplicate_phage_ids = set()
    duplicate_phage_ids_on_server = set()
    if genbank_files_to_add is not None:
        for index, path in enumerate(genbank_files_to_add):
            callback(CallbackCode.status, 'validating genbank files', index, len(genbank_files_to_add))
            try:
                phage = pham.genbank.read_file(path)
            except IOError as e:
                valid = False
                callback(CallbackCode.file_does_not_exist, path)
                continue
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

    with closing(server.get_connection(database=id)) as cnx:
        cnx.start_transaction()

        callback(CallbackCode.status, 'checking for conflicts', 0, 1)
        try:
            # check for phages which are already on the server
            for phage_id in phage_id_to_filenames:
                if pham.query.phage_exists(cnx, phage_id):
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
                callback(CallbackCode.status, 'deleting organisms', index, len(organism_ids_to_delete))
                pham.query.delete_phage(cnx, phage_id)

            # validate and upload genbank files
            if genbank_files_to_add is not None:
                for index, path in enumerate(genbank_files_to_add):
                    callback(CallbackCode.status, 'uploading organisms', index, len(genbank_files_to_add))
                    phage = pham.genbank.read_file(path)
                    if not phage.is_valid():
                        for error in phage.errors:
                            callback(CallbackCode.genbank_format_error, error)
                        cnx.rollback()
                        return False
                    # upload phage
                    try:
                        phage.upload(cnx)
                    except mysql.connector.errors.IntegrityError as e:
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
                            pham_id_to_gene_ids = pham.kclust.cluster(
                                sequences, gene_ids,
                                on_first_iteration_done=lambda: callback(CallbackCode.status, 'calculating phams', 1, 2))
                        except MemoryError as e:
                            # not enough ram
                            callback(CallbackCode.out_of_memory_error)
                            cnx.rollback()
                            return False

                        original_phams = _read_phams(cursor)
                        pham_id_to_gene_ids = _assign_pham_ids(pham_id_to_gene_ids, original_phams)

                        # assign colors to the phams
                        original_colors = _read_pham_colors(cursor)
                        pham_id_to_color = _assign_pham_colors(pham_id_to_gene_ids, original_colors)

                        # clear old phams and colors from database
                        # write new phams and colors to database
                        cursor.execute('DELETE FROM pham')
                        cursor.execute('DELETE FROM pham_color')

                        for pham_id, gene_ids in pham_id_to_gene_ids.iteritems():
                            for gene_id in gene_ids:
                                cursor.execute('''
                                               INSERT INTO pham(GeneID, name)
                                               VALUES (%s, %s)
                                               ''', (gene_id, pham_id)
                                               )

                        for pham_id, color in pham_id_to_color.iteritems():
                            cursor.execute('''
                                           INSERT INTO pham_color(name, color)
                                           VALUES (%s, %s)
                                           ''', (pham_id, color))
                    else:
                        # there are no genes in the database
                        # clear all phams and colors from database
                        cursor.execute('DELETE FROM pham')
                        cursor.execute('DELETE FROM pham_color')

            if cdd_search and len(new_gene_ids):
                callback(CallbackCode.status, 'searching conserved domain database', 0, 1)
                # search for genes in conserved domain database
                # only search for new genes
                pham.conserveddomain.find_domains(cnx, new_gene_ids, new_gene_sequences, num_threads=2)

        except Exception:
            cnx.rollback()
            raise

        cnx.commit()

    return True

#imports whole sql database (GET_DB) and sometimes CONVERT_DB
def load(server, id, filepath):
    """Load a Phamerator database from an SQL dump.

    Also migrates to the new schema if needed.

    Raises:
        IOError when input file is not found
        DatabaseAlreadyExistsError
        ValueError when database schema is invalid
    """
    if not os.path.isfile(filepath):
        raise IOError('No such file: {}'.format(filepath))

    with closing(server.get_connection()) as cnx:
        if pham.query.database_exists(cnx, id):
            raise DatabaseAlreadyExistsError('Database {} already exists.'.format(id))
        
        with closing(cnx.cursor()) as cursor:
            cursor.execute("CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(id))
        cnx.commit()

    try:
        with closing(server.get_connection(database=id)) as cnx:
            with closing(cnx.cursor()) as cursor:
                try:
                    host, user, password = server.get_credentials()
                    command = ['mysql', '--host', host, '--user', user]
                    if password != '' and password is not None:
                        command += ['--password', password]
                    command.append(id)

                    with open(filepath, 'r') as stdin:
                        with open(os.devnull, 'wb') as DEVNULL:
                            subprocess32.check_call(command, stdin=stdin, stdout=DEVNULL, stderr=DEVNULL)

                except subprocess32.CalledProcessError:
                    raise ValueError('File does not contain valid SQL.')

            if not _is_schema_valid(cnx):
                raise ValueError('Invalid database schema.')
            _update_schema(cnx)
            cnx.commit()
    except:
        delete(server, id)
        raise

#EXPORT sql pipeline
def export(server, id, filepath):
    """Saves a SQL dump of the database to the given file.

    Creates three files:
        <filename>.sql
        <filename>.version
        <filename>.md5sum
    """
    directory = os.path.dirname(filepath)
    base_path = '.'.join(filepath.split('.')[:-1]) # remove extension from filename
    version_filename = '{}.version'.format(base_path)
    checksum_filename = '{}.md5sum'.format(base_path)

    with closing(server.get_connection()) as cnx:
        if not pham.query.database_exists(cnx, id):
            raise DatabaseDoesNotExistError('No such database: {}'.format(id))

    if os.path.exists(filepath):
        raise IOError('File already exists: {}'.format(filepath))
    if os.path.exists(version_filename):
        raise IOError('File already exists: {}'.format(version_filename))
    if os.path.exists(checksum_filename):
        raise IOError('File already exists: {}'.format(checksum_filename))

    if directory != '' and not os.path.exists(directory):
        os.makedirs(directory)

    # export database to sql file using mysqldb command line program
    host, user, password = server.get_credentials()
    command = ['mysqldump', '--host', host, '--user', user]
    if password != '' and password is not None:
        command += ['--password', password]
    command.append(id)

    with open(filepath, 'w') as output_file:
        with open(os.devnull, 'wb') as DEVNULL:
            subprocess32.check_call(command, stdout=output_file, stderr=DEVNULL)

    # write .version file
    with closing(server.get_connection(database=id)) as cnx:
        version_number = pham.query.version_number(cnx)

    with open(version_filename, 'w') as out_file:
        out_file.write('{}\n'.format(version_number))

    # calculate checksum
    m = hashlib.md5()
    with open(filepath, 'rb') as sql_file:
        while True:
            data = sql_file.read(8192)
            if data == '':
                break
            m.update(data)

    # write .md5sum file
    checksum = m.hexdigest()
    with open(checksum_filename, 'w') as out_file:
        out_file.write('{}  {}\n'.format(checksum, filepath))

#EXPORT gb pipeline
def export_to_genbank(server, id, organism_id, filename):
    """Download a phage from the database to the given file or file handle.

    Returns an instance of `db_object.Phage`.

    Raises: PhageNotFoundError, DatabaseDoesNotExistError
    """
    with closing(server.get_connection()) as cnx:
        if not pham.query.database_exists(cnx, id):
            raise DatabaseDoesNotExistError('No such database: {}'.format(id))

    with closing(server.get_connection(database=id)) as cnx:
        try:
            phage = pham.db_object.Phage.from_database(cnx, organism_id)
        except pham.db_object.PhageNotFoundError as e:
            raise PhageNotFoundError

    pham.genbank.write_file(phage, filename)
    return phage

#HELPER FUNCTIONS
#-----------------------------------------------------------------------------
class _PhamIdFinder(object):
    def __init__(self, phams, original_phams):
        """
        phams is a dictionary mapping pham_id to a frozenset of gene ids
        original_phams is a frozenset mapping pham_id to a frozenset of gene ids
        """
        # build helper data structures
        self.original_genes = set()
        for genes in original_phams.itervalues():
            self.original_genes.update(genes)

        self.genes = set()
        for genes in phams.itervalues():
            self.genes.update(genes)

        self.original_genes_to_pham_id = {}
        for pham_id, genes in original_phams.iteritems():
            self.original_genes_to_pham_id[genes] = pham_id

        self.original_gene_to_pham_id = {}
        for pham_id, genes in original_phams.iteritems():
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
    file_handle = open(schema_filepath, "r")
    command_string = f"mysql -u {alchemist.username} -p{alchemist.password}"
    if alchemist.database:
        command_string = " ".join([command_string, alchemist.database])

    command_list = shlex.split(command_string)
    process = subprocess.check_call(command_list, stdin=handle)
    file_handle.close()

#API DATA RETRIEVAL
#-----------------------------------------------------------------------------
def summary(server, id):
    """Returns a DatabaseSummaryModel with information on the database.
    """
    with closing(server.get_connection()) as cnx:
        if not pham.query.database_exists(cnx, id):
            raise DatabaseDoesNotExistError('No such database: {}'.format(id))

    with closing(server.get_connection(database=id)) as cnx:
        phage_count = pham.query.count_phages(cnx)
        pham_count = pham.query.count_phams(cnx)
        orpham_count = pham.query.count_orphan_genes(cnx)
        domain_hits = pham.query.count_domains(cnx)

    return DatabaseSummaryModel(phage_count, pham_count, orpham_count, domain_hits)

class DatabaseSummaryModel(object):
    def __init__(self, organism_count, pham_count, orpham_count, conserved_domain_hit_count):
        self.number_of_organisms = organism_count
        self.number_of_phams = pham_count
        self.number_of_orphams = orpham_count
        self.number_of_conserved_domain_hits = conserved_domain_hit_count

def list_organisms(server, id):
    """Returns a list of organisms in the database.

    Each organisms is an instance of OrganismSummaryModel.

    Raises: DatabaseDoesNotExistError
    """
    with closing(server.get_connection()) as cnx:
        if not pham.query.database_exists(cnx, id):
            raise DatabaseDoesNotExistError('No such database: {}'.format(id))

    organisms = []
    with closing(server.get_connection(database=id)) as cnx:
        with closing(cnx.cursor()) as cursor:
            cursor.execute('''
                SELECT p.PhageID, p.Name, COUNT(*)
                FROM phage as p
                JOIN gene as g
                ON g.PhageID = p.PhageID
                GROUP BY g.PhageID
                           ''')
            for phage_id, name, gene_count in cursor:
                organisms.append(OrganismSummaryModel(name, phage_id, gene_count))

    return organisms

class OrganismSummaryModel(object):
    def __init__(self, name, id, gene_count):
        self.name = name
        self.id = id
        self.genes = gene_count


#REDUNDANT PIPELINE HELPER FUNCTIONS
#-----------------------------------------------------------------------------
#Used to set up pipeline like rebuild or load

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

def _migrate_foreign_key(cursor, this_table, constraint, this_feild, other_table, other_feild):
    """Replace a foreign key constraint with one which specifies to cascade
    on delete and update.
    """
    _drop_foreign_key(cursor, this_table, constraint)

    cursor.execute('''
                   ALTER TABLE {}
                   ADD CONSTRAINT {} FOREIGN KEY ({}) REFERENCES {} ({})
                   ON UPDATE CASCADE
                   ON DELETE CASCADE
                   '''.format(this_table, constraint, this_feild, other_table, other_feild))

def _drop_foreign_key(cursor, table, constraint):
    try:
        cursor.execute('ALTER TABLE {} DROP FOREIGN KEY {}'.format(table, constraint))
    except mysql.connector.errors.Error as e:
        if e.errno == errorcode.ER_ERROR_ON_RENAME:
            # the constraint did not already exist
            pass
        else:
            raise

def _increment_version(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('''
                       UPDATE version
                       SET version=version+1
                       ''')

def _read_phams(cursor):
    """Reads phams from the database.

    Returns a dictionary mapping pham_id to a set of gene ids.
    """
    phams = {}
    cursor.execute('''
        SELECT name, GeneID
        FROM pham
                   ''')
    for pham_id, gene_id in cursor:
        if pham_id not in phams:
            phams[pham_id] = set()
        phams[pham_id].add(gene_id)

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
    for key, value in phams.iteritems():
        phams[key] = frozenset(value)
    for key, value in original_phams.iteritems():
        original_phams[key] = frozenset(value)

    final_phams = {}
    next_id = 1
    if len(original_phams):
        next_id = max(original_phams.iterkeys()) + 1

    id_finder = _PhamIdFinder(phams, original_phams)

    for genes in phams.itervalues():
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
    cursor.execute('''
        SELECT name, color
        FROM pham_color
                   ''')
    for pham_id, color in cursor:
        pham_colors[pham_id] = color
    return pham_colors

def _assign_pham_colors(phams, original_colors):
    """Returns a dictionary mapping pham_id to color.

    phams is a dictionary mapping pham_id to a list of gene ids.
    original_colors is a dictionary mapping pham_id to color.
    """
    pham_colors = {}
    for pham_id, genes in phams.iteritems():
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

    red, green, blue = colorsys.hsv_to_rgb(hue, sat ,val)
    hexcode = '#%02x%02x%02x' % (red * 255, green * 255, blue * 255)
    return hexcode



