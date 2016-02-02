from select import select


CHUNK_SIZE = 4096


class ConnectionClose(Exception):
    pass


class SockClient(object):
    def __init__(self, sock):
        super(SockClient, self).__init__()

        self.sock = sock

    def _read_sock(self, length):
        data = b''
        while len(data) < length:
            chunk = self.sock.recv(min(CHUNK_SIZE, length - len(data)))
            if chunk == b'':
                self.stop()
                return None

            data += chunk

        return data

    def _write_sock(self, data):
        total_sent = 0
        while total_sent < len(data):
            sent = self.sock.send(data[total_sent:])
            if sent == 0:
                self.stop()
                raise ConnectionClose("Sent zero bytes")

            total_sent += sent

    def receive_message(self):
        # Parse message length - first 2 bytes
        length_bytes = bytearray(self._read_sock(2))
        length = length_bytes[0] * 256 + length_bytes[1]

        # Receive the message
        message = self._read_sock(length)
        return message

    def send_message(self, message):
        length = len(message)
        length_bytes = bytes(bytearray((length // 256, length % 256)))
        self._write_sock(length_bytes + message)

    def stop(self):
        self.sock.close()
