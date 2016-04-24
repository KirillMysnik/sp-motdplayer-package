from . import (
    base_authed_offline_request, base_authed_request, get_base_authed_route,
    get_base_authed_offline_route, json_authed_request)


class PluginInstance:
    def __init__(self, app, server_id, plugin_id):
        self.app = app
        self.server_id = server_id
        self.plugin_id = plugin_id

    def base_authed_offline_request(self, page_id, *args, **kwargs):
        return base_authed_offline_request(
            self.app, self.server_id, self.plugin_id, page_id, *args, **kwargs)

    def base_authed_request(self, page_id, *args, **kwargs):
        return base_authed_request(
            self.app, self.server_id, self.plugin_id, page_id, *args, **kwargs)

    def get_base_authed_route(self, page_id):
        return get_base_authed_route(self.server_id, self.plugin_id, page_id)

    def get_base_authed_offline_route(self, page_id):
        return get_base_authed_offline_route(
            self.server_id, self.plugin_id, page_id)

    def json_authed_request(self, page_id, *args, **kwargs):
        return json_authed_request(
            self.app, self.server_id, self.plugin_id, page_id, *args, **kwargs)

    def json_authed_offline_request(self, page_id, *args, **kwargs):
        raise NotImplementedError
