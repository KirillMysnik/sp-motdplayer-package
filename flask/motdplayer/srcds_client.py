from json import dumps, loads


class SRCDSClient(object):
    def __init__(self, client):
        self.client = client

    def end_communication(self, send_action=True):
        if self.client is None:
            return

        if send_action:
            self.client.send_message(dumps({
                'action': "end_communication",
            }).encode('utf-8'))

        self.client.stop()
        self.client = None

    def set_identity(self, steamid, salt, session_id):
        self.client.send_message(dumps({
            'action': "set_identity",
            'new_salt': salt,
            'steamid': steamid,
            'session_id': session_id,
        }).encode('utf-8'))
        response = loads(self.client.receive_message().decode('utf-8'))

        if response['status'] == "OK":
            return True

        self.end_communication(send_action=False)
        return False

    def request_retargeting(self, new_page_id):
        self.client.send_message(dumps({
            'action': "retarget",
            'new_page_id': new_page_id,
        }).encode('utf-8'))
        response = loads(self.client.receive_message().decode('utf-8'))

        self.end_communication(send_action=False)

        return response['status'] == "OK"

    def exchange_custom_data(self, data):
        if not isinstance(data, dict):
            self.client.send_message(dumps({
                'action': "receive_custom_data",
                'custom_data': None,
            }))
            raise TypeError("Excepted type of custom data: 'dict', got '{}' "
                            "instead".format(type(data)))

        self.client.send_message(dumps({
            'action': "receive_custom_data",
            'custom_data': data,
        }).encode('utf-8'))

        response = loads(self.client.receive_message().decode('utf-8'))

        if response['status'] == "OK":
            return response['custom_data']

        return None
