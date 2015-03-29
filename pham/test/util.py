from contextlib import closing

def import_database(server, database_id, filename):
    with closing(server.get_connection()) as cnx:
        with closing(cnx.cursor()) as cursor:
            cursor.execute('DROP DATABASE IF EXISTS {}'.format(database_id))
            cursor.execute('CREATE DATABASE {}'.format(database_id))
        cnx.commit()

    with closing(server.get_connection(database=database_id)) as cnx:
        with closing(cnx.cursor()) as cursor:
            _execute_sql_file(cursor, filename)
        cnx.commit()

def _execute_sql_file(cursor, filepath):
    with open(filepath, 'r') as sql_script_file:
        cursors = cursor.execute(sql_script_file.read(), multi=True)
        for result_cursor in cursors:
            for row in result_cursor:
                pass
