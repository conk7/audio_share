import socket
from typing import Tuple


def send_mp3(sock: socket.socket, remote: Tuple[str, int]):
    with open('../audio.mp3', "rb") as f:
        while (bytes := f.read(2**10)):
            sock.sendto(bytes, remote)
            yield