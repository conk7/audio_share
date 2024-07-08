import socket
from typing import Tuple
import stun
import threading


class ServerStates:
    IDLE = 0
    PLAYING = 1


class Server:
    state: ServerStates
    addr: Tuple[str, int]
    sock: socket.socket

    def __init__(self) -> None:
        source_ip = "0.0.0.0"
        source_port = 8547
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((source_ip, source_port))

        nat_type, nat = stun.get_nat_type(self.sock,
                                          source_ip, source_port,
                                          stun_host='stun.l.google.com', stun_port=19302)

        external_ip = nat['ExternalIP']
        external_port = nat['ExternalPort']
        self.addr = (external_ip, external_port)

        self.state = ServerStates.IDLE

    def __fetchData(self) -> None:
        while True:
            data, addr = self.sock.recvfrom(1024)
            print('\r', addr, "<", data.decode())

    def start(self) -> None:
        threading.Thread(target=self.__fetchData).start()
        print("stated server")

    def getLink(self) -> str:
        return ""

if __name__ == '__main__':
    server = Server()
    server.start()
