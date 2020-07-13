from sqlalchemy.sql import func

from pdm_utils.classes.alchemyhandler import AlchemyHandler
from pdm_utils.functions import mysqldb_basic
from pdm_utils.functions import querying

#GLOBAL VARIABLES
#-----------------------------------------------------------------------------
EXISTS_QUERY_PREFIX = ("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                       "WHERE SCHEMA_NAME =")


def database_exists(alchemist, database):
    query = " ".join([EXISTS_QUERY_PREFIX, f"'{database}'"])
    return len(mysqldb_basic.scalar(alchemist.engine, query))

def count_phages(alchemist):
    phage_obj = alchemist.metadata.tables["phage"]
    phageid_obj = phage_obj.c.PhageID

    query = querying.build_count(alchemist.graph, phageid_obj)
    return mysqldb_basic.scalar(alchemist.engine, query)

def count_phams(alchemist):
    pham_obj = alchemist.metadata.tables["pham"]
    phamid_obj = pham_obj.c.PhamID

    query = querying.build_count(alchemist.graph, phamid_obj)
    return mysqldb_basic.scalar(alchemist.engine, query)

def count_orphan_genes(alchemist):
    """Return the number of phams with only one member.

    These orphan phams are known as orphams :(.
    """
    pham_obj = alchemist.metadata.tables["pham"]
    gene_obj = alchemist.metadata.tables["gene"]
    phamid_obj = pham_obj.c.PhamID
    geneid_obj = gene_obj.c.GeneID

    query = querying.build_select(alchemist.graph, phamid_obj, 
                                                   add_in=geneid_obj)
    query = query.group_by(phamid_obj)
    query = query.having(func.count(geneid_obj) == 1)

    return len(querying.first_column(alchemist.engine, query))

def list_organisms(alchemist):
    phage_obj = alchemist.metadata.tables["phage"]
    phageid_obj = phage_obj.c.PhageID
    name_obj = phage_obj.c.Name
    length_obj = phage_obj.c.Length
    GC_obj = phage_obj.c.GC
    dlm_obj = phage_obj.c.DateLastModified
    
    columns = [phageid_obj, name_obj, length_obj, GC_obj, dlm_obj]

    query = querying.build_select(alchemist.graph, columns)
    return querying.execute(alchemist.engine, query, return_dict=False)

def count_domains(alchemist):
    gene_domain_obj = alchemist.metadata.tables["gene_domain"]
    gene_domain_id_obj = gene_domain_obj.c.ID

    query = querying.build_count(alchemist.graph, gene_domain_id_obj)
    return mysqldb_basic.scalar(alchemist.engine, query)
        
def delete_phage(alchemist, phage_id):
    phage_map = alchemist.mapper.classes["phage"]

    phage_entry = alchemist.session.query(phage_map).\
                                                filter_by(PhageID=phage_id).\
                                                scalar()
    
    if not phage_entry is None:
        alchemist.session.delete(phage_entry)

        try:
            alchemist.session.commit()
        except:
            alchemist.session.rollback()

def list_genes(alchemist, phage_id):
    gene_obj = alchemist.metadata.tables["gene"]
    geneid_obj = gene_obj.c.GeneID
    phageid_obj = gene_obj.c.PhageID
    name_obj = gene_obj.c.Name
    locus_tag_obj = gene_obj.c.LocusTag

    columns = [geneid_obj, phageid_obj, name_obj, locus_tag_obj]

    query = querying.build_select(alchemist.graph, columns, 
                                  where=(phageid_obj==phage_id))

    return querying.execute(alchemist.engine, query, return_dict=False)

def phage_exists(alchemist, phage_id):
    phage_obj = alchemist.metadata.tables["phage"]
    phageid_obj = phage_obj.c.PhageID

    query = querying.build_count(alchemist.graph, phageid_obj, 
                                 where=(phageid_obj==phageid))

    return (mysqldb_basic.scalar(alchemist.engine, query) >= 1)

def list_phams(server, id):
    """What was this supposed to do...?"""
    pass

def version_number(alchemist):
    db_version = mysql_basic.get_first_row_data(alchemist.engine, "version") 

    #Maybe we want to include this?
    #return mysqldb.get_schema_version(alchemist.engine) 
