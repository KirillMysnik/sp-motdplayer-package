from ConfigParser import ConfigParser
from functools import wraps
import os.path
import socket

from flask import jsonify, request

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


def get_base_authed_route(server_id, plugin_id, page_id):
    return config.get('application', 'base_route').format(
        server_id=server_id, plugin_id=plugin_id, page_id=page_id)


def get_base_authed_offline_route(server_id, plugin_id, page_id):
    return config.get('application', 'base_route_with_auth_method').format(
        server_id=server_id,
        plugin_id=plugin_id,
        page_id=page_id,
        auth_method=AUTH_BY_WEB,
    )


def get_json_page_id(page_id):
    return config.get('application', 'json_page_id').format(page_id=page_id)


def base_authed_request(app, server_id, plugin_id, page_id, *args, **kwargs):
    route = get_base_authed_route(server_id, plugin_id, page_id)

    def decorator(f):
        @app.route(route, *args, **kwargs)
        @wraps(f)
        def new_func(steamid, auth_method, auth_token, session_id):
            steamid = str(steamid)
            user = User.query.filter(
                User.steamid == steamid, User.server_id == server_id).first()

            if user is None:
                user = User(server_id, steamid)
                db.session.add(user)

            if not user.authenticate(
                    auth_method, plugin_id, page_id, auth_token, session_id):

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
                web_auth_token=user.get_web_auth_token(
                    plugin_id, page_id, session_id),
                session_id=session_id,
                data_exchanger=custom_data_exchanger,
                error=None,
            )
            srcds_client.end_communication(send_action=True)
            return result

        return new_func

    return decorator


def base_authed_offline_request(
        app, server_id, plugin_id, page_id, *args, **kwargs):

    route = get_base_authed_offline_route(server_id, plugin_id, page_id)

    def decorator(f):
        @app.route(route, *args, **kwargs)
        @wraps(f)
        def new_func(steamid, auth_token, session_id):
            steamid = str(steamid)
            user = User.query.filter(
                User.steamid == steamid, User.server_id == server_id).first()

            if user is None:
                return f(
                    steamid=None,
                    web_auth_token=None,
                    session_id=-1,
                    error="USER_DOES_NOT_EXIST"
                )

            if not user.authenticate(
                    AUTH_BY_WEB, plugin_id, page_id, auth_token, session_id):

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
                web_auth_token=user.get_web_auth_token(
                    plugin_id, page_id, session_id),
                session_id=session_id,
                error=None,
            )

        return new_func

    return decorator


def json_authed_request(app, server_id, plugin_id, page_id, *args, **kwargs):
    def decorator(f):
        @base_authed_request(
            app, server_id, plugin_id, page_id, *args,
            methods=["POST", ], **kwargs)
        @wraps(f)
        def base_authed_request_func(
                steamid, web_auth_token, session_id, data_exchanger, error):

            if error is not None:
                return jsonify({
                    'status': error,
                    'web_auth_token': web_auth_token,
                })

            if request.json['action'] != 'receive-custom-data':
                return jsonify({
                    'status': "ERROR_BAD_REQUEST",
                    'web_auth_token': web_auth_token,
                })

            data = f(data_exchanger, request.json['custom_data'])

            if data is None:
                return jsonify({
                    'status': "ERROR_SRCDS_FAILURE",
                    'web_auth_token': web_auth_token,
                })

            return jsonify({
                'status': "OK",
                'web_auth_token': web_auth_token,
                'custom_data': data,
            })

        return base_authed_request_func

    return decorator
