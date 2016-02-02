from ConfigParser import ConfigParser
from hashlib import sha512
import os.path
from random import choice, randrange
import socket
import string

from flask.ext.sqlalchemy import SQLAlchemy

from .client import SockClient
from .srcds_client import SRCDSClient


SALT_CHARACTERS = string.ascii_letters + string.digits
SALT_LENGTH = 64

AUTH_BY_SRCDS = 1
AUTH_BY_WEB = 2

MOTDPLAYER_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
SECRET_SALT_FILE = os.path.join(MOTDPLAYER_DATA_PATH, "secret_salt.dat")
CONFIG_FILE = os.path.join(MOTDPLAYER_DATA_PATH, "config.ini")

if os.path.isfile(SECRET_SALT_FILE):
    with open(SECRET_SALT_FILE, 'rb') as f:
        SECRET_SALT = f.read()
else:
    SECRET_SALT = bytes([randrange(256) for x in range(32)])
    with open(SECRET_SALT_FILE, 'wb') as f:
        f.write(SECRET_SALT)

config = ConfigParser()
config.read(CONFIG_FILE)


db = None
User = None


def init_database(app):
    global db, User
    db = SQLAlchemy(app)

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
                auth_token2 = self.get_auth_token(page_id, session_id)
            elif method == AUTH_BY_WEB:
                auth_token2 = self.get_web_auth_token(page_id, session_id)
            else:
                return False

            return auth_token2 == auth_token

        @staticmethod
        def get_new_salt():
            return ''.join(
                [choice(SALT_CHARACTERS) for x in range(SALT_LENGTH)])


class CustomDataExchanger(object):
    def __init__(self, srcds_client):
        self._srcds_client = srcds_client

    def exchange(self, custom_data):
        return self._srcds_client.exchange_custom_data(custom_data)


def get_route(page_id):
    return config.get('application', 'route').format(page_id=page_id)


def srcds_request(app, page_id, *args, **kwargs):
    route = get_route(page_id)

    def decorator(f):
        def new_func(steamid, auth_method, auth_token, session_id):
            steamid = str(steamid)
            user = User.query.filter_by(steamid=steamid).first()
            if user is None:
                user = User(steamid)
                db.session.add(user)

            if not user.authenticate(
                    auth_method, page_id, auth_token, session_id):

                db.session.rollback()
                return f(
                    steamid=None,
                    web_auth_token=None,
                    session_id=-1,
                    data_exchanger=None,
                    error="INVALID_AUTH",
                )

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((
                config.get('srcds', 'host'), int(config.get('srcds', 'port'))
            ))
            client = SockClient(sock)
            srcds_client = SRCDSClient(client)

            if auth_method == AUTH_BY_SRCDS:
                new_salt = user.get_new_salt()

                if not srcds_client.set_identity(
                        steamid, new_salt, session_id):

                    return f(
                        steamid=steamid,
                        web_auth_token=None,
                        session_id=session_id,
                        data_exchanger=None,
                        error="IDENTITY_REJECTED",
                    )

                user.salt = new_salt

            else:
                if not srcds_client.set_identity(steamid, None, session_id):
                    return f(
                        steamid=steamid,
                        web_auth_token=None,
                        session_id=session_id,
                        data_exchanger=None,
                        error="IDENTITY_REJECTED",
                    )

                user.web_salt = user.get_new_salt()

            db.session.commit()

            custom_data_exchanger = CustomDataExchanger(srcds_client)
            result = f(
                steamid=steamid,
                web_auth_token=user.get_web_auth_token(page_id, session_id),
                session_id=session_id,
                data_exchanger=custom_data_exchanger,
                error=None,
            )
            srcds_client.end_communication(send_action=True)
            return result

        return app.route(route, *args, **kwargs)(new_func)

    return decorator
