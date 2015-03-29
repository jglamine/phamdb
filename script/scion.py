import argparse
import sys
import pham.db

def callback(code, *args, **kwargs):
    if code == pham.db.CallbackCode.genbank_format_error:
        error = args[0]
        sys.stderr.write('invalid genbank file: {}\n'.format(error))

parser = argparse.ArgumentParser(description='Create and manage Phamerator databases.')
parser.add_argument('--host', help='Connect to MYSQL server on given host.', default='localhost')
parser.add_argument('--user', help='MySQL user name to use when connecting to server.', default='root')
parser.add_argument('--password', help='Password to use when connecting to server.', default='')
subparsers = parser.add_subparsers(dest='command')

create_command = subparsers.add_parser('create', help='Create a database.')
create_command.add_argument('name', help='Database name.')
create_command.add_argument('phages', nargs='*', help='A list of genbank files containing phages to add to the database.')
create_command.add_argument('--no-cdd', dest='cdd_search', default=True, action='store_false', help='Do not search for conserved domains. Saves a lot of time.')

delete_command = subparsers.add_parser('delete', help='Delete a database.')
delete_command.add_argument('name', help='Database name.')

export_command = subparsers.add_parser('export', help='Export a database to a .sql file.')
export_command.add_argument('name', help='Database name.')
export_command.add_argument('-o', '--filename', help='Filename for SQL dump. Default is <name>.sql', default=None)

add_command = subparsers.add_parser('add', help='Add phages to a database.')
add_command.add_argument('name', help='Database name.')
add_command.add_argument('phages', nargs='*', help='A list of genbank files containing phages to add to the database.')

args = parser.parse_args()

server = pham.db.DatabaseServer(args.host, args.user, args.password)

if args.command == 'create':
    try:
        pham.db.create(server, args.name, genbank_files=args.phages,
                       cdd_search=args.cdd_search, callback=callback)
    except pham.db.DatabaseAlreadyExistsError:
        sys.stderr.write('error: database \'{}\' already exists\n'.format(args.name))

elif args.command == 'delete':
    pham.db.delete(server, args.name)

elif args.command == 'export':
    if args.filename is None:
        args.filename = '{}.sql'.format(args.name)
    try:
        pham.db.export(server, args.name, args.filename)
    except pham.db.DatabaseDoesNotExistError as err:
        sys.stderr.write('error: no such database \'{}\'\n'.format(args.name))

elif args.command == 'add':
    try:
        pham.db.rebuild(server, args.name, genbank_files_to_add=args.phages, callback=callback)
    except pham.db.DatabaseDoesNotExistError as err:
        sys.stderr.write('error: no such database \'{}\'\n'.format(args.name))
