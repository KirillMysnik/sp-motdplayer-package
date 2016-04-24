import socket

from flask import jsonify, render_template, request

from . import AUTH_BY_SRCDS, config, User
from .client import SockClient
from .srcds_client import SRCDSClient


def init_views(app, db):
    @app.route(config.get('application', 'csgo_redirect_from'))
    def route_csgo_redirect(
            server_id, plugin_id, page_id, steamid, auth_method, auth_token,
            session_id):

        # TODO: maybe just replace it all with **kwargs?
        redirect_to = config.get('application', 'csgo_redirect_to').format(
            server_id=server_id,
            plugin_id=plugin_id,
            page_id=page_id,
            steamid=steamid,
            auth_method=auth_method,
            auth_token=auth_token,
            session_id=session_id,
        )

        return render_template(
            "motdplayer/csgo_redirect.html", redirect_to=redirect_to)

    @app.route(config.get('application', 'retarget_url'), methods=['POST', ])
    def route_json_retarget(server_id, plugin_id, new_page_id, page_id,
                            steamid, auth_method, auth_token, session_id):

        if request.json['action'] != "retarget":
            return jsonify({
                'status': "ERROR_BAD_REQUEST",
            })

        steamid = str(steamid)
        user = User.query.filter(
            User.steamid == steamid, User.server_id == server_id).first()

        if user is None:
            user = User(server_id, steamid)
            db.session.add(user)

        if not user.authenticate(
                auth_method, plugin_id, page_id, auth_token, session_id):

            db.session.rollback()
            return jsonify({
                'status': "ERROR_INVALID_AUTH",
            })

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((
            config.get('srcds', 'host'), int(config.get('srcds', 'port'))
        ))
        client = SockClient(sock)
        srcds_client = SRCDSClient(client)

        if auth_method == AUTH_BY_SRCDS:
            new_salt = user.get_new_salt()

            if not srcds_client.set_identity(steamid, new_salt, session_id):
                return jsonify({
                    'status': "ERROR_IDENTITY_REJECTED",
                })

            user.salt = new_salt

        else:
            if not srcds_client.set_identity(steamid, None, session_id):
                return jsonify({
                    'status': "ERROR_IDENTITY_REJECTED",
                })

            web_salt = user.get_new_salt()
            user.web_salt = web_salt

        db.session.commit()

        if not srcds_client.request_retargeting(new_page_id):
            return jsonify({
                'status': "ERROR_RETARGETING_REJECTED",
            })

        return jsonify({
            'status': "OK",
            'web_auth_token': user.get_web_auth_token(
                plugin_id, new_page_id, session_id),
        })
