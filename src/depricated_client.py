import socket
import select
import os
import ast
import threading
import stun
import queue

from typing import List
from time import sleep
from utils import DataType, Data, DataMP3
from pydantic_core import _pydantic_core
from typing import Dict
from pydub import AudioSegment, playback
from io import BytesIO
from mp3_handles import path_to_ffmpeg
from pathlib import Path


USER_INPUT = None
IS_RUNNING = True

CHUNK_SIZE_SEND = 1024 * 1024
CHUNK_SIZE_RECV = 1024 * 1024


audio_file_per_peer: Dict[socket.socket, bytes] = dict()
chunks_per_peer: Dict[socket.socket, List[Data]] = dict()

audio_queue = queue.Queue()
CURRENTLY_PLAYING = None


class App:
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
        # self.state = ServerStates.IDLE

        AudioSegment.ffmpeg = path_to_ffmpeg()
        os.environ["PATH"] += os.pathsep + str(Path(path_to_ffmpeg()).parent)

    def __handle_commands(self, conn: socket.socket, data: Data) -> None:
        data_type = data.type
        if data_type == DataType.CONNECT:
            addr = data.data
            self.__connect_peer(addr)
        elif data_type == DataType.DISCONNECT:
            addr = data.data
            idx = self.addrs.index(addr)
            self.addrs.pop(idx)
            self.peers.pop(idx)
        elif data_type == DataType.CHUNKS_INFO:
            chunks_per_peer[conn] = data.data
            self.__get_chunks(conn, data.data)

    def __handle_recv(self) -> None:
        if len(self.peers) == 0:
            return
        r, _, _ = select.select(self.peers, [], [], 0.1)
        # print(f"clients potential receivers: {r}")
        for conn in r:
            data = conn.recv(CHUNK_SIZE_RECV).decode()

            print(f"client received {data[:50]} from {conn}")
            try:
                data = Data.model_validate_json(data)
            except _pydantic_core.ValidationError:
                print("Client received invalid data")
                continue
            self.__handle_commands(conn, data)

    def __handle_send(self, data: str = "") -> None:
        if data == "dc":
            addr = f"{self.external_ip}:{self.external_port}"
            data = Data(type=DataType.DISCONNECT, data=addr)
            data = data.model_dump_json()
            for conn in self.peers:
                print(f"sent {data} to {conn}")
                conn.sendall(data.encode())
            self.__disconnect()
        elif data != "":
            data = Data(type=DataType.USER_INPUT, data=data)
            data = data.model_dump_json()
            for conn in self.peers:
                print(f"sent {data} to {conn}")
                conn.sendall(data.encode())

    def __get_chunks(self, conn: socket.socket, chunk_info: List[Data]) -> None:
        for i, chunk_len in enumerate(chunk_info):
            data = conn.recv(chunk_len).decode()
            print(data[:50])
            try:
                data = Data.model_validate_json(data)
            except _pydantic_core.ValidationError:
                print(f"Client received invalid audio data, i = {i}, ")
                continue

            if data.type != DataType.CHUNK_MP3:
                break

            data_mp3 = DataMP3.model_validate(data.data)

            if data_mp3.chunk_num != i:
                break
            chunk = ast.literal_eval(data_mp3.data)

            if i == 0:
                audio_file_per_peer[conn] = chunk
            elif i < data_mp3.total_chunks:
                audio_file_per_peer[conn] += chunk
            elif i == data_mp3.total_chunks:
                audio_bytes = BytesIO(audio_file_per_peer[conn])
                song = AudioSegment.from_mp3(audio_bytes)
                audio_queue.put(song)
                chunks_per_peer.pop(conn)
                print(f"FINISHED RECEIVING AUDIO from {conn.getpeername()}")

    def __handle_peers(self) -> None:
        global USER_INPUT, IS_RUNNING
        while IS_RUNNING:
            self.__handle_recv()
            if USER_INPUT is not None:
                self.__handle_send(USER_INPUT)
                USER_INPUT = None
            else:
                self.__handle_send()
            sleep(0.1)

    def __connect_peer(self, addr: str) -> None:
        ip, port = addr.split(":")
        port = int(port)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))

        self.peers.append(sock)
        self.addrs.append(addr)

    def __disconnect(self) -> None:
        global IS_RUNNING
        IS_RUNNING = False

        for conn in self.peers:
            conn.close()
        self.peers.clear()

        self.sock.close()

        os._exit(0)

    def __handle_user_input(self) -> None:
        global USER_INPUT, IS_RUNNING
        while IS_RUNNING:
            USER_INPUT = input().strip().lower()

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
        sock.send(query)
        data = sock.recv(CHUNK_SIZE_RECV).decode()

        print(f"received addrs: {data}")

        data = Data.model_validate_json(data)

        if data.type == DataType.ADDRS and len(data.data) > 0:
            new_addrs = data.data
            self.addrs.extend(new_addrs)

        threading.Thread(target=self.__handle_peers).start()
        threading.Thread(target=self.__handle_user_input).start()

        while True:
            self.sock.listen(1)
            try:
                conn, addr = self.sock.accept()
            except:
                break

            print(f"accepted connection from {addr[0]}:{str(addr[1])}")

            self.peers.append(conn)
            self.addrs.append(addr)


if __name__ == "__main__":
    BASE_PORT = 8765
    port = BASE_PORT + 1
    server = App("0.0.0.0", port)
    server.connect("127.0.0.1", BASE_PORT)
