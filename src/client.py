import socket
from typing import Tuple
from os import getenv
import dotenv
from time import sleep

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
        self.sock =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.source_addr = getenv("SOURCE_IP"), int(getenv("SOURCE_PORT"))
        print(self.source_addr)
        self.state = 0

    def connect(self):
        self.sock.connect((self.source_addr[0], self.source_addr[1]))
        flag = ""
        while flag != "exit":
            flag = input()
            self.sock.send(flag.encode())
            print(self.sock.recv(1024).decode())
            # sleep(0.3)
        self.sock.close()

        # TODO HANDLE ERRORS

    # def __fetchData(self):
    #     self.sock.send("get_status".encode())
        # status = self.sock.recv(1024).decode()
        # return status

    # def disconnect(self):


if __name__ == "__main__":
    client = Client()
    client.connect()
    # client._Client__fetchData()
