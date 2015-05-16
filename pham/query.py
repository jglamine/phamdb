from contextlib import closing
import mysql.connector
from mysql.connector import errorcode

def database_exists(cnx, id):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('SHOW DATABASES LIKE %s', (id, ))
        if len(cursor.fetchall()) == 0:
            return False
        return True

def count_phages(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('SELECT COUNT(*) FROM phage')
        return cursor.fetchall()[0][0]

def count_phams(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('SELECT COUNT(*) FROM pham')
        return cursor.fetchall()[0][0]

def list_organisms(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute(
            'SELECT PhageID, Name, SequenceLength, GC, DateLastModified from phage;'
        )
        rows = cursor.fetchall()
    return rows

def count_domains(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute(
            'SELECT COUNT(1) FROM gene_domain'
        )
        rows = cursor.fetchall()
    return rows[0][0]
        
def delete_phage(cnx, phage_id):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('''
                       DELETE FROM phage
                       WHERE PhageID = %s
                       ''', (phage_id,))

        cursor.execute('''
                       DELETE FROM domain
                       WHERE domain.hit_id NOT IN
                        (SELECT hit_id FROM gene_domain)
                       ''')

def list_genes(cnx, phage_id):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('''
            SELECT GeneID, PhageID, Name, id
            FROM gene
            WHERE gene.PhageID = %s
            ''',
            (phage_id,)
        )
        rows = cursor.fetchall()
    return rows

def phage_exists(cnx, phage_id):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('''
            SELECT COUNT(PhageID)
            FROM phage
            WHERE PhageID = %s
                       ''', (phage_id,))
        return cursor.fetchall()[0][0] != 0

def list_phams(server, id):
    pass

def version_number(cnx):
    with closing(cnx.cursor()) as cursor:
        cursor.execute('''
                       SELECT version
                       FROM version
                       LIMIT 1;
                       ''')
        row = cursor.fetchone()
        return row[0]