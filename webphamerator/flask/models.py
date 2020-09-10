import hashlib
import datetime
import unicodedata
from slugify import slugify

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Database(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(255), index=True, unique=True)
    name_slug = db.Column(db.String(255), index=True, unique=True)
    description = db.Column(db.String(2048))
    number_of_organisms = db.Column(db.Integer)
    number_of_phams = db.Column(db.Integer)
    number_of_orphams = db.Column(db.Integer)
    created = db.Column(db.DateTime())
    modified = db.Column(db.DateTime(), default=datetime.datetime.utcnow())
    locked = db.Column(db.Boolean())
    visible = db.Column(db.Boolean())
    cdd_search = db.Column(db.Boolean())

    def url(self):
        return '/databases/{}'.format(self.id)

    @classmethod
    def mysql_name_for(cls, name):
        m = hashlib.md5()
        m.update(name.encode("utf-8"))
        return 'PhameratorWeb_{}'.format(m.hexdigest())

    @classmethod
    def phamerator_name_for(cls, name):
        slug = slugify(name)
        slug = slug.replace('-', '_')
        return unicodedata.normalize('NFKD', slug).encode('ascii','ignore')

    def mysql_name(self):
        """The name of the database in MySQL.

        This is the md5 hash of the name prefixed with '_P'.
        """
        return Database.mysql_name_for(self.display_name)

    def __repr__(self):
        return '<Database {} {}>'.format(self.id, self.display_name)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    database_id = db.Column(db.Integer, db.ForeignKey('database.id', ondelete='SET NULL'))
    database_name = db.Column(db.String(255))
    task_id = db.Column(db.String(64))
    status_code = db.Column(db.String(32))
    status_message = db.Column(db.String(255))
    type_code = db.Column(db.String(32))
    modified = db.Column(db.DateTime(), default=datetime.datetime.utcnow()) # used to sort when displaying
    start_time = db.Column(db.DateTime())
    runtime = db.Column(db.Interval())
    seen = db.Column(db.Boolean)
    genbank_files_to_add = db.relationship('GenbankFile', backref='job', lazy='dynamic')
    organism_ids_to_delete = db.relationship('JobOrganismToDelete', backref='job', lazy='dynamic')

    def __repr__(self):
        return '<Job {} "{}"">'.format(self.id, self.status_code)


class JobOrganismToDelete(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organism_id = db.Column(db.String(255))
    job_id = db.Column(db.Integer, db.ForeignKey('job.id', ondelete='CASCADE'))

    def __repr__(self):
        return '<JobOrganismToDelete {} {} {}>'.format(self.id, self.organism_id, self.job_id)


class GenbankFile(db.Model):
    """

    GenbankFiles expire after 7 days.
    If expires is NULL, it will never expire.
    """
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id', ondelete='CASCADE'))
    filename = db.Column(db.String(2048))
    phage_name = db.Column(db.String(255))
    length = db.Column(db.Integer)
    genes = db.Column(db.Integer)
    gc_content = db.Column(db.Float)
    expires = db.Column(db.DateTime, default=datetime.datetime.utcnow() + datetime.timedelta(days=7))

    def __repr__(self):
        return '<GenbankFile {} {}>'.format(self.id, self.name)


class Password(db.Model):
    """Stores the password used for authentication.
    """
    id = db.Column(db.Integer, primary_key=True)
    digest_key = db.Column(db.String(64))
    salt = db.Column(db.String(32))
