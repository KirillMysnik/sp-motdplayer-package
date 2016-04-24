from . import send_page


class PluginInstance:
    def __init__(self, plugin_id):
        self.plugin_id = plugin_id

    def send_page(self, player, page_id,
                  callback, retargeting_callback=None, debug=False):

        return send_page(
            player, self.plugin_id, page_id,
            callback, retargeting_callback, debug
        )
