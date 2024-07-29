import argparse
import socket
import threading

from typing import List, Dict
from utils import DataType, Data, add_CL_args
from pydantic_core import _pydantic_core
from utils import init_ffmpeg, CHUNK_SIZE_RECV, ROOM_SIZE, PlayerStates
from simpleaudio import PlayObject
from handles.peers.peer_handler import PeerHandler
from pydub import AudioSegment

parser = argparse.ArgumentParser()
parser = add_CL_args(parser)


class App(PeerHandler):
    def __init__(self, ip: str, port: int) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((ip, port))

        # _, self.external_ip, self.external_port = stun.get_ip_info(
        #     ip, port, stun_host="stun.l.google.com", stun_port=19302
        # )

        self.external_ip = "127.0.0.1"
        self.external_port = port

        self.peers: List[socket.socket] = []
        self.addrs: List[str] = []
        self.state: PlayerStates = PlayerStates.IDLE

        init_ffmpeg()

        self.audio_files: List[AudioSegment] = []
        self.playing_song_idx: int = -1
        self.playing_song: PlayObject | None = None
        self.song_played_time = 0

        self.audio_file_per_peer: Dict[socket.socket, bytes] = dict()
        self.chunks_per_peer: Dict[socket.socket, List[Data]] = dict()

        self.user_input = None

    def run_handler_threads(self) -> None:
        threading.Thread(target=self.handle_peers).start()
        threading.Thread(target=self.handle_user_input).start()
        threading.Thread(target=self.handle_playback).start()

    def host(self) -> None:
        self.run_handler_threads()

        while True:
            self.sock.listen(ROOM_SIZE)
            try:
                peer, addr = self.sock.accept()
            except:
                break

            addr = f"{addr[0]}:{str(addr[1])}"
            print(f"accepted connection from {addr}")

            self.peers.append(peer)

    def connect(self, ip: str, port: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((ip, port))
        except:
            print("Could not connect to the server")
            return

        self.peers.append(sock)
        self.addrs.append(f"{ip}:{port}")

        print(f"connected to {ip}:{port}")

        query = Data(
            type=DataType.GET_DATA, data=f"{self.external_ip}:{self.external_port}"
        )
        query = query.model_dump_json().encode()
        sock.sendall(query)
        data = sock.recv(CHUNK_SIZE_RECV).decode()

        print(f"received addrs: {data}")

        try:
            data = Data.model_validate_json(data)
        except _pydantic_core.ValidationError:
            print(f"App received invalid peer data {data[:50]}")
            return

        if data.type != DataType.ADDRS:
            print(f"App received invalid peer data {data[:50]}")
            return

        if len(data.data) > 0:
            new_addrs = data.data
            self.addrs.extend(new_addrs)

        self.run_handler_threads()

        while True:
            self.sock.listen(ROOM_SIZE)
            try:
                peer, addr = self.sock.accept()
            except:
                break

            print(f"accepted connection from {addr[0]}:{str(addr[1])}")

            self.peers.append(peer)
            self.addrs.append(addr)


if __name__ == "__main__":
    args = parser.parse_args()
    client_type = args.client_type
    if client_type == "host":
        lip, lport = args.lhost.split(":")
        lport = int(lport)
        server = App("0.0.0.0", lport)
        server.host()
    elif client_type == "conn":
        lip, lport = args.lhost.split(":")
        lport = int(lport)
        server = App("0.0.0.0", lport)
        rip, rport = args.rhost.split(":")
        rport = int(rport)
        server.connect(rip, rport)
