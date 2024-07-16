import socket
from typing import Tuple
from pathlib import Path


def send_mp3(sock: socket.socket, remote: Tuple[str, int]):
    with open("../audio.mp3", "rb") as f:
        while bytes := f.read(2**10):
            sock.sendto(bytes, remote)
            yield


def path_to_ffmpeg():
    SCRIPT_DIR = Path(__file__).parent.parent
    return str(Path(SCRIPT_DIR, "common", "ffmpeg", "bin", "ffmpeg.exe"))
