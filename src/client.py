import socket
import stun
from typing import Tuple
from os import getenv
import dotenv


dotenv.load_dotenv()

class ClientStates:
    DISCONNECTED = 0
    CONNECTED = 1
    RECIEVING_FILE = 2


class Client:
    source_addr: Tuple[str, int]
    sock: socket.socket
    state: ClientStates

    def __init__(self):
        self.source_addr = getenv("SOURCE_IP"), getenv("SOURCE_PORT")
        self.state = 0

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.connect((self.source_ip, self.source_port))
        # TODO HANDLE ERRORS

    def __fetchData(self):
        self.sock.send("get_status".encode())
        status = self.sock.recv(1024).decode()
        return status

    # def disconnect(self):


if __name__ == "__main__":
    client = Client()
    client.connect()
    client.__fetchData()
