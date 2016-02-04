from flask import render_template

from . import config


def init_views(app):
    @app.route(config.get('application', 'csgo_redirect_from'))
    def route_csgo_redirect(
            page_id, steamid, auth_method, auth_token, session_id):

        # TODO: maybe just replace it all with **kwargs?
        redirect_to = config.get('application', 'csgo_redirect_to').format(
            page_id=page_id,
            steamid=steamid,
            auth_method=auth_method,
            auth_token=auth_token,
            session_id=session_id,
        )

        return render_template(
            "motdplayer/csgo_redirect.html", redirect_to=redirect_to)
