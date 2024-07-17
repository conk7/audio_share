import argparse
import ast
import socket
import select
import threading
import os
import stun

from typing import List, Dict, Any
from time import sleep
from utils import DataType, Data, DataMP3, add_CL_args
from pydantic_core import _pydantic_core
from mp3_handles import path_to_ffmpeg
from pathlib import Path
from pydub import AudioSegment, playback
from io import BytesIO
from simpleaudio import PlayObject


class ServerStates:
    IDLE = 0
    PLAYING = 1


USER_INPUT = None
IS_RUNNING = True

CHUNK_SIZE_SEND = 500 * 1024
CHUNK_SIZE_RECV = 500 * 1024


audio_file_per_peer: Dict[socket.socket, bytes] = dict()
chunks_per_peer: Dict[socket.socket, List[Data]] = dict()


parser = argparse.ArgumentParser()
parser = add_CL_args(parser)


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
        self.state = ServerStates.IDLE

        AudioSegment.ffmpeg = path_to_ffmpeg()
        os.environ["PATH"] += os.pathsep + str(Path(path_to_ffmpeg()).parent)

        self.audio_files: List[Any] = []
        self.playing_song_idx: int = -1
        self.playing_song: PlayObject | None = None

    def __handle_commands(self, conn: socket.socket, data: Data) -> None:
        data_type = data.type
        if data_type == DataType.GET_DATA:
            addr = data.data
            if len(self.peers) > 0:
                self.__notify_about_new_peer(addr)

            self.addrs.append(addr)

            print(f"self addrs: {self.addrs}")

            reply = Data(type=DataType.ADDRS, data=self.addrs[:-1])
            reply_json = reply.model_dump_json()

            print(f"handle_comms with type {data_type} sent\n {reply_json} to {conn}")

            conn.send(reply_json.encode())
        elif data_type == DataType.CONNECT:
            addr = data.data
            self.__connect_peer(addr)
        elif data_type == DataType.DISCONNECT:
            addr = data.data
            idx = self.addrs.index(addr)
            self.addrs.pop(idx)
            self.peers.pop(idx)
        elif data_type == DataType.USER_INPUT:
            reply = Data(type=DataType.INFO, data="server received user input")
            reply_json = reply.model_dump_json()

            print(f"handle_comms with type {data_type} sent\n {reply_json} to {conn}")

            conn.send(reply_json.encode())
        elif data_type == DataType.CHUNKS_INFO:
            chunks_per_peer[conn] = data.data
            self.__get_chunks(conn, data.data)

    def __send_audio(self, song_name: str) -> None:
        SCRIPT_DIR = Path(__file__).parent.parent
        song_path = str(Path(SCRIPT_DIR, song_name))

        print(f"song path: {song_path}")

        song = AudioSegment.from_mp3(song_path)
        song -= 30

        self.__add_audio(song)

        export_bytes = BytesIO()
        song.export(export_bytes, format="mp3")
        export_bytes = export_bytes.getvalue()

        song_len = len(export_bytes)

        if song_len % CHUNK_SIZE_SEND == 0:
            total_chunks = (song_len / CHUNK_SIZE_SEND) - 1
        else:
            total_chunks = (song_len // CHUNK_SIZE_SEND) - 1

        chunks = []
        chunks_info = []
        for i in range(total_chunks):
            data_mp3 = DataMP3(
                chunk_num=i,
                total_chunks=total_chunks - 1,
                data=str(export_bytes[i * CHUNK_SIZE_SEND : (i + 1) * CHUNK_SIZE_SEND]),
            )

            chunk = Data(type=DataType.CHUNK_MP3, data=data_mp3)
            chunk_json = chunk.model_dump_json().encode()
            chunks.append(chunk_json)

        chunks_info = Data(
            type=DataType.CHUNKS_INFO, data=[len(chunk) for chunk in chunks]
        )
        chunks_info_json = chunks_info.model_dump_json().encode()

        for conn in self.peers:
            conn.sendall(chunks_info_json)

        sleep(0.1)

        for conn in self.peers:
            for i, chunk in enumerate(chunks):
                bytes_sent = conn.send(chunk)
                print("", chunk.decode()[2:50])
                if bytes_sent != chunks_info.data[i]:
                    print(
                        f"sent {bytes_sent} expected to send {chunks_info_json[i]}. conn {conn}"
                    )
                    break
                sleep(0.01)
            else:
                print(f"successfully sent audio to {conn}")

    def __add_audio(self, song) -> None:
        self.audio_files.append(song)

        if len(self.audio_files) == 21:
            self.audio_files.pop(0)
        if len(self.audio_files) == 1 and self.playing_song is None:
            self.playing_song_idx = 0
            self.playing_song = playback._play_with_simpleaudio(self.audio_files[0])
            print(f"is_playing {self.playing_song.is_playing()}")

    def __pause_audio(self) -> None:
        if self.playing_song is not None and self.playing_song.is_playing():
            self.playing_song.pause()

    def __resume_audio(self) -> None:
        if self.playing_song is not None and not self.playing_song.is_playing():
            self.playing_song.resume()

    def __handle_recv(self) -> None:
        if len(self.peers) == 0:
            return
        r, _, _ = select.select(self.peers, [], [], 0.1)
        for conn in r:
            data = conn.recv(CHUNK_SIZE_RECV).decode()

            print(f"App received {data[:50]} from {conn}")

            try:
                data = Data.model_validate_json(data)
            except _pydantic_core.ValidationError:
                print("App received invalid data")
                continue
            self.__handle_commands(conn, data)

    def __handle_send(self, data: str = "") -> None:
        if data == "dc":
            self.__disconnect()

        elif data[:4] == "play":
            song_name = data[5:]
            self.__send_audio(song_name)

        elif data != "":
            self.__send_user_input(data)

    def __send_user_input(self, data: str) -> None:
        data = Data(type=DataType.USER_INPUT, data=data)
        data = data.model_dump_json()
        data = data.encode()

        for conn in self.peers:
            print(f"sent {data} to {conn}")
            conn.sendall(data)

    def __get_chunks(self, conn: socket.socket, chunk_info: List[Data]) -> None:
        for i, chunk_len in enumerate(chunk_info):
            data = conn.recv(chunk_len).decode()
            print(f"slice of audio chunk: {data[:50]}")

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
                self.__add_audio(song)
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

    def __notify_about_new_peer(self, addr: str) -> None:
        for conn in self.peers[:-1]:
            data = Data(type=DataType.CONNECT, data=addr)
            data = data.model_dump_json()
            conn.send(data.encode())

    def __connect_peer(self, addr: str) -> None:
        ip, port = addr.split(":")
        port = int(port)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))

        self.peers.append(sock)
        self.addrs.append(addr)

    def __disconnect(self) -> None:
        addr = f"{self.external_ip}:{self.external_port}"
        data = Data(type=DataType.DISCONNECT, data=addr)
        data = data.model_dump_json()
        data = data.encode()

        for conn in self.peers:
            print(f"sent {data} to {conn}")
            conn.sendall(data)

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

    def host(self) -> None:
        threading.Thread(target=self.__handle_peers).start()
        threading.Thread(target=self.__handle_user_input).start()
        while True:
            self.sock.listen(1)
            try:
                conn, addr = self.sock.accept()
            except:
                break

            addr = f"{addr[0]}:{str(addr[1])}"
            print(f"accepted connection from {addr}")

            self.peers.append(conn)

            print(self.peers)

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
