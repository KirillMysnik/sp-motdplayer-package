from hashlib import sha512
import os.path
from random import choice, randrange
import string

from . import AUTH_BY_SRCDS, AUTH_BY_WEB, MOTDPLAYER_DATA_PATH


SALT_CHARACTERS = string.ascii_letters + string.digits
SALT_LENGTH = 64

SECRET_SALT_FILE = os.path.join(MOTDPLAYER_DATA_PATH, "secret_salt.dat")
if os.path.isfile(SECRET_SALT_FILE):
    with open(SECRET_SALT_FILE, 'rb') as f:
        SECRET_SALT = f.read()
else:
    SECRET_SALT = bytes([randrange(256) for x in range(32)])
    with open(SECRET_SALT_FILE, 'wb') as f:
        f.write(SECRET_SALT)


User = None


def init_database(app, db):
    global User

    class User(db.Model):
        __tablename__ = "motdplayer_users"

        id = db.Column(db.Integer, primary_key=True)
        steamid = db.Column(db.String(32))
        salt = db.Column(db.String(64))
        web_salt = db.Column(db.String(64))

        def __init__(self, steamid):
            super(User, self).__init__()

            self.steamid = steamid
            self.salt = ""
            self.web_salt = ""

        def get_auth_token(self, page_id, session_id):
            return sha512(
                (
                    self.salt + self.steamid + page_id + str(session_id)
                ).encode('ascii') + SECRET_SALT
            ).hexdigest()

        def get_web_auth_token(self, page_id, session_id):
            return sha512(
                (
                    self.web_salt + self.steamid + page_id + str(session_id)
                ).encode('ascii') + SECRET_SALT
            ).hexdigest()

        def authenticate(self, method, page_id, auth_token, session_id):
            if method == AUTH_BY_SRCDS:
                return auth_token == self.get_auth_token(page_id, session_id)
            if method == AUTH_BY_WEB:
                return auth_token == self.get_web_auth_token(
                    page_id, session_id)

            return False

        @staticmethod
        def get_new_salt():
            return ''.join(
                [choice(SALT_CHARACTERS) for x in range(SALT_LENGTH)])
