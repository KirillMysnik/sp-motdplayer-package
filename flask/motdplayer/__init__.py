from ConfigParser import ConfigParser
import os.path
import socket

from .client import SockClient
from .srcds_client import SRCDSClient


AUTH_BY_SRCDS = 1
AUTH_BY_WEB = 2

MOTDPLAYER_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
CONFIG_FILE = os.path.join(MOTDPLAYER_DATA_PATH, "config.ini")

config = ConfigParser()
config.read(CONFIG_FILE)


db = None
User = None


def init(app, db_):
    global db, User
    db = db_

    from .models import init_database
    init_database(app, db)
    from .models import User

    from .views import init_views
    init_views(app, db)


class CustomDataExchanger(object):
    def __init__(self, srcds_client):
        self._srcds_client = srcds_client

    def exchange(self, custom_data):
        return self._srcds_client.exchange_custom_data(custom_data)


def get_srcds_request_route(page_id):
    return config.get('application', 'route').format(page_id=page_id)


def get_consequent_request_route(page_id):
    return config.get('application', 'route_with_auth_method').format(
        page_id=page_id,
        auth_method=AUTH_BY_WEB,
    )


def srcds_request(app, page_id, *args, **kwargs):
    route = get_srcds_request_route(page_id)

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
                        steamid=None,
                        web_auth_token=None,
                        session_id=-1,
                        data_exchanger=None,
                        error="IDENTITY_REJECTED",
                    )

                user.salt = new_salt

            else:
                if not srcds_client.set_identity(steamid, None, session_id):
                    return f(
                        steamid=None,
                        web_auth_token=None,
                        session_id=-1,
                        data_exchanger=None,
                        error="IDENTITY_REJECTED",
                    )

                web_salt = user.get_new_salt()
                user.web_salt = web_salt

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


def consequent_request(app, page_id, *args, **kwargs):
    route = get_consequent_request_route(page_id)

    def decorator(f):
        def new_func(steamid, auth_token, session_id):
            steamid = str(steamid)
            user = User.query.filter_by(steamid=steamid).first()
            if user is None:
                return f(
                    steamid=None,
                    web_auth_token=None,
                    session_id=-1,
                    error="USER_DOES_NOT_EXIST"
                )

            if not user.authenticate(
                    AUTH_BY_WEB, page_id, auth_token, session_id):

                return f(
                    steamid=None,
                    web_auth_token=None,
                    session_id=-1,
                    error="INVALID_AUTH",
                )

            user.web_salt = user.get_new_salt()
            db.session.commit()

            return f(
                steamid=steamid,
                web_auth_token=user.get_web_auth_token(page_id, session_id),
                session_id=session_id,
                error=None,
            )

        return app.route(route, *args, **kwargs)(new_func)

    return decorator
