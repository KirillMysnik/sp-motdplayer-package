from json import dumps, loads


class SiteClient:
    def __init__(self, client):
        super().__init__()

        self.client = client
        self.motd_player = None
        self.session = None

        client.on_message_received = self._on_message_received

    def end_communication(self):
        if self.client is None:
            return

        self.client.stop()
        self.client = None

    def _on_message_received(self, message):
        from . import player_manager, SessionClosedException

        response = loads(message.decode('utf-8'))

        if response['action'] == "end_communication":
            self.end_communication()
            return

        if response['action'] == "set_identity":
            if self.motd_player is not None:
                self.client.send_message(dumps({
                    'status': "ERROR_ALREADY_SET",
                }).encode('utf-8'))
                self.end_communication()
                raise RuntimeError("Site tried to set identity twice")

            motd_player = player_manager.get_by_communityid(
                response['steamid'])

            if motd_player is None:
                self.client.send_message(dumps({
                    'status': "ERROR_UNKNOWN_STEAMID"
                }).encode('utf-8'))
                self.end_communication()

            else:
                self.motd_player = motd_player

                session = self.motd_player.get_session_for_data_transmission(
                    response['session_id']
                )

                if session is None:
                    self.client.send_message(dumps({
                        'status': "ERROR_SESSION_CLOSED",
                    }).encode('utf-8'))
                    self.end_communication()

                else:
                    self.session = session

                    new_salt = response['new_salt']
                    if (new_salt is None or
                            motd_player.confirm_new_salt(new_salt)):

                        self.client.send_message(dumps({
                            'status': "OK",
                        }).encode('utf-8'))

                    else:
                        self.client.send_message(dumps({
                            'status': "ERROR_SALT_REFUSED",
                        }).encode('utf-8'))

                        try:
                            session.error("SALT_REFUSED")
                        finally:
                            self.end_communication()

            return

        if response['action'] == "retarget":
            if self.motd_player is None:
                self.end_communication()
                raise RuntimeError("Site tried to make retargeting request "
                                   "prior to setting identity")

            try:
                new_callbacks = self.session.request_retargeting(
                    response['new_page_id'])

            except SessionClosedException:
                self.client.send_message(dumps({
                    'status': "ERROR_SESSION_CLOSED2",
                }).encode('utf-8'))
                self.end_communication()
                return

            except Exception as e:
                self.client.send_message(dumps({
                    'status': "ERROR_RETARGETING_CALLBACK_EXCEPTION",
                }).encode('utf-8'))
                self.end_communication()
                raise e

            if new_callbacks is None:
                self.client.send_message(dumps({
                    'status': "ERROR_RETARGETING_REFUSED",
                }).encode('utf-8'))
                self.end_communication()
                return

            try:
                new_callback, new_retargeting_callback = new_callbacks

                if not callable(new_callback):
                    raise ValueError

                if (new_retargeting_callback is not None and
                        not callable(new_retargeting_callback)):

                    raise ValueError

            except (TypeError, ValueError):
                self.client.send_message(dumps({
                    'status': "ERROR_RETARGETING_CALLBACK_INVALID_ANSWER",
                }).encode('utf-8'))
                self.end_communication()
                return

            self.session.callback = new_callback
            self.session.retargeting_callback = new_retargeting_callback

            self.client.send_message(dumps({
                'status': "OK",
            }).encode('utf-8'))
            self.end_communication()
            return

        if response['action'] == "receive_custom_data":
            if self.motd_player is None:
                self.end_communication()
                raise RuntimeError("Site tried to send custom "
                                   "data prior to setting identity")

            try:
                answer = self.session.receive(response['custom_data'])

            except SessionClosedException:
                self.client.send_message(dumps({
                    'status': "ERROR_SESSION_CLOSED2",
                }).encode('utf-8'))
                self.end_communication()
                return

            except Exception as e:
                self.client.send_message(dumps({
                    'status': "ERROR_CALLBACK_EXCEPTION",
                }).encode('utf-8'))
                self.end_communication()
                raise e

            if answer is None:
                answer = {}

            if not isinstance(answer, dict):
                self.client.send_message(dumps({
                    'status': "ERROR_CALLBACK_INVALID_ANSWER",
                }).encode('utf-8'))
                self.end_communication()
                raise TypeError("Excepted type of custom data: 'dict', got "
                                "'{}' instead".format(type(answer)))

            try:
                message = dumps({
                    'status': "OK",
                    'custom_data': answer,
                }).encode('utf-8')

            except Exception as e:
                self.client.send_message(dumps({
                    'status': "ERROR_CALLBACK_INVALID_ANSWER2",
                }).encode('utf-8'))
                self.end_communication()
                raise e

            self.client.send_message(message)
