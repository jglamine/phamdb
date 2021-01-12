import os
import binascii
from flask import Blueprint, request, redirect, session
from webphamerator.app.sqlalchemy_ext import models
from backports.pbkdf2 import pbkdf2_hmac, compare_digest

AUTHENTICATION_NOT_NEEDED = ['/signin', '/db', '/static']

bp = Blueprint("auth", __name__)


@bp.before_request
def require_authentication():
    """Require authentication on most routes.
    """
    for path in AUTHENTICATION_NOT_NEEDED:
        if request.path.startswith(path):
            return

    if not is_authenticated() and is_password_required():
        return redirect('/signin')


def is_authenticated():
    if session.get("authenticated"):
        return True


def is_password_required():
    return models.Password.query.count() > 0


def set_password(password):
    salt = binascii.hexlify(os.urandom(16))
    hex_digest = binascii.hexlify(digest(password, salt))

    passwords = models.Password.query.all()
    for item in passwords:
        models.db.session.delete(item)

    new_item = models.Password(digest_key=hex_digest, salt=salt)
    models.db.session.add(new_item)
    models.db.session.commit()

    session['authenticated'] = True


def delete_password():
    passwords = models.Password.query.all()
    for item in passwords:
        models.db.session.delete(item)
    models.db.session.commit()

    sign_out()


def sign_out():
    if 'authenticated' in session:
        del session['authenticated']


def authenticate(password):
    is_valid = is_password_valid(password)
    session['authenticated'] = is_valid
    session['password_required'] = True
    return is_valid


def is_password_valid(password):
    password_record = models.Password.query.first()
    stored_digest = binascii.unhexlify(password_record.digest_key)
    digest_key = digest(password, password_record.salt)
    return compare_digest(digest_key, stored_digest)


def digest(password, salt):
    password = str(password)
    salt = str(salt)
    return pbkdf2_hmac('sha256', password, salt, 100000)


@bp.context_processor
def template_context():
    return {
        'show_sign_out': show_sign_out_button
    }


def show_sign_out_button():
    if not is_authenticated():
        return False
    return is_password_required()
