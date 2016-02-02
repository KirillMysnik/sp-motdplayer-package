from select import select

from .spthread import SPThread


CHUNK_SIZE = 4096


class ConnectionClose(Exception):
    pass


class SockClient(SPThread):
    def __init__(self, sock_server, sock, on_message_received=None):
        super().__init__()

        self._sock_server = sock_server
        self.sock = sock
        self.on_message_received = on_message_received

        self.running = False
        self.callbacks = []

    def _read_sock(self, length):
        data = b''
        while len(data) < length:
            chunk = self.sock.recv(min(CHUNK_SIZE, length - len(data)))
            if chunk == b'':
                self._sock_server.remove_client(self)
                self.stop()
                return None

            data += chunk

        return data

    def _write_sock(self, data):
        total_sent = 0
        while total_sent < len(data):
            sent = self.sock.send(data[total_sent:])
            if sent == 0:
                self._sock_server.remove_client(self)
                self.stop()
                raise ConnectionClose("Sent zero bytes")

            total_sent += sent

    def receive_message(self):
        # Parse message length - first 2 bytes
        length_bytes = self._read_sock(2)
        length = int.from_bytes(length_bytes, byteorder='big')

        # Receive the message
        message = self._read_sock(length)
        return message

    def send_message(self, message):
        length = len(message)
        length_bytes = length.to_bytes(2, byteorder='big')
        self._write_sock(length_bytes + message)

    def run(self):
        self.running = True

        r, w, e = select([self.sock], [], [])
        while self.running:
            if self.sock in r:
                message = self.receive_message()
                if message is None:
                    continue

                if self.on_message_received is not None:
                    self.on_message_received(message)

            if self.running:
                r, w, e = select([self.sock], [], [])
            else:
                break

    def stop(self):
        super().stop()

        if not self.running:
            return

        self.running = False

        self.sock.close()
