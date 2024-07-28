import socket
import os

from utils import DataType, Data


class PeerUtils:
    def notify_about_new_peer(self, addr: str) -> None:
        for conn in self.peers[:-1]:
            data = Data(type=DataType.CONNECT, data=addr)
            data = data.model_dump_json()
            conn.send(data.encode())

    def connect_peer(self, addr: str) -> None:
        ip, port = addr.split(":")
        port = int(port)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))

        self.peers.append(sock)
        self.addrs.append(addr)

    def disconnect(self) -> None:
        addr = f"{self.external_ip}:{self.external_port}"
        data = Data(type=DataType.DISCONNECT, data=addr)
        data = data.model_dump_json()
        data = data.encode()

        for conn in self.peers:
            print(f"sent {data[:50]} to {conn}")
            conn.sendall(data)

        for conn in self.peers:
            conn.close()
        self.peers.clear()

        self.sock.close()

        os._exit(0)
