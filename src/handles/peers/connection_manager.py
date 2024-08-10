import ast
import time
import os
import threading
import socket
import select

from models import Data, DataType, DataMP3, PlayerInfo, PlayerStates
from utils import (
    AUDIO_CHUNK_SIZE,
    get_chunks_num,
    singleton,
)
from constants import CHUNK_SIZE_RECV, ROOM_SIZE
from typing import List
from pydantic_core._pydantic_core import ValidationError
from pydub import AudioSegment
from io import BytesIO
from ..audio.player import Player


MAX_DELAY = 1000


@singleton
class ConnectionManager:
    def __init__(self, ip: str, port: int, player: Player) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((ip, port))

        # _, self.external_ip, self.external_port = stun.get_ip_info(
        #     ip, port, stun_host="stun.l.google.com", stun_port=19302
        # )

        self.external_ip = "127.0.0.1"
        self.external_port = port

        self.active_connections: dict[socket.socket, float] = {}
        self.addrs: list[tuple[str, int]] = []

        self.Player = player

    def is_active(self, sock: socket.socket) -> bool:
        return time.time() - self.active_connections[socket.socket] > MAX_DELAY

    def update(self, sock: socket.socket) -> None:
        self.active_connections[sock] = time.time()

    def host(self) -> None:
        threading.Thread(target=self.__handle_host).start()
        threading.Thread(target=self.__handle_peers).start()

    def __handle_host(self) -> None:
        while True:
            self.sock.listen(ROOM_SIZE)

            try:
                sock, addr = self.sock.accept()
            except Exception as e:
                print(f"Could not accept connection\nRaised exception: {e}")
                break

            self.active_connections[sock] = time.time()
            ip, port = addr

            print(f"host connected {ip, port}")

    def connect(self, ip: str, port: int) -> None:
        self.__connect_host(ip, port)
        threading.Thread(target=self.__handle_connect).start()
        threading.Thread(target=self.__handle_peers).start()

    def __handle_connect(self) -> None:
        while True:
            self.sock.listen(ROOM_SIZE)
            try:
                sock, addr = self.sock.accept()
            except Exception as e:
                print(e)
                break

            self.active_connections[sock] = time.time()
            ip, port = addr
            self.addrs.append(f"{ip}:{port}")

            print(f"accepted connection from {addr[0]}:{str(addr[1])}")

    def __connect_host(self, ip: str, port: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))

        self.active_connections[sock] = time.time()
        self.addrs.append(f"{ip}:{port}")

        print(f"connected to {ip}:{port}")

        query = Data(
            type=DataType.GET_ADDRS, data=f"{self.external_ip}:{self.external_port}"
        )
        query = query.model_dump_json().encode()
        sock.send(query)

    def __connect_peer(self, ip: str, port: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))

        self.active_connections[sock] = time.time()

    def __handle_peers(self) -> None:
        while True:
            # self.ping()
            self.__handle_recv()
            time.sleep(0.1)

    def __handle_recv(self) -> None:
        if len(self.active_connections) == 0:
            return
        r, _, _ = select.select(self.active_connections.keys(), [], [], 0.1)
        for peer in r:
            try:
                data = peer.recv(CHUNK_SIZE_RECV).decode()
            except Exception:
                continue

            print(f"App received {data[:50]} from {peer}")

            try:
                data = Data.model_validate_json(data)
            except ValidationError:
                print("App received invalid data")
                continue
            self.__handle_commands(peer, data)

    def __handle_commands(self, peer: socket.socket, data: Data) -> None:
        data_type = data.type
        if data_type == DataType.GET_ADDRS:
            addr = data.data
            ip, port = addr.split(":")
            port = int(port)
            self.addrs.append(f"{ip}:{port}")

            if len(self.addrs) > 0:
                self.__notify_about_new_peer(addr)

            reply = Data(type=DataType.ADDRS, data=self.addrs[:-1])
            reply_json = reply.model_dump_json()
            reply_json = reply_json.encode()
            peer.sendall(reply_json)

            if self.Player.get_num_of_audio_files() > 0:
                self.send_all_audio(peer)

        elif data_type == DataType.ADDRS:
            new_addrs = data.data
            self.addrs.extend(new_addrs)

        elif data_type == DataType.CONNECT:
            ip, port = data.data.split(":")
            port = int(port)
            self.__connect_peer(ip, port)
            self.addrs.append(f"{ip}:{port}")

        elif data_type == DataType.DISCONNECT:
            ip, port = data.data.split(":")
            port = int(port)
            self.__disconnect_peer(peer, ip, port)

        elif data_type == DataType.CHUNKS_INFO:
            chunk_info = data.data
            self.get_chunks(peer, chunk_info)

        elif data_type == DataType.PLAYER_INFO:
            player_info = data.data
            self.set_player_info(player_info)

        elif data_type == DataType.PLAY:
            song_idx = data.data
            self.Player.play(song_idx)

        elif data_type == DataType.PAUSE:
            self.Player.pause()

        elif data_type == DataType.RESUME:
            self.Player.resume()

        elif data_type == DataType.PLAY_NEXT:
            song_idx = data.data
            self.Player.play(song_idx)

        elif data_type == DataType.STOP:
            self.Player.stop()

    def disconnect(self) -> None:
        data = Data(
            type=DataType.DISCONNECT, data=f"{self.external_ip}:{self.external_port}"
        )
        data = data.model_dump_json()
        data = data.encode()

        for peer in self.active_connections:
            print(f"sent {data[:50]} to {peer}")
            peer.sendall(data)

        for peer in self.active_connections:
            peer.close()
        self.active_connections.clear()

        self.sock.close()

        os._exit(0)

    def __notify_about_new_peer(self, addr: str) -> None:
        data = Data(type=DataType.CONNECT, data=addr)
        data = data.model_dump_json()
        data = data.encode()
        for sock in list(self.active_connections.keys())[:-1]:
            sock.send(data)

    def __disconnect_peer(self, sock: socket.socket, ip: str, port: int) -> None:
        idx = self.addrs.index(f"{ip}:{port}")
        self.addrs.pop(idx)

        del self.active_connections[sock]

    def notify_play(self, idx: int) -> None:
        data = Data(type=DataType.PLAY, data=idx)
        data_json = data.model_dump_json()
        data_json = data_json.encode()
        for peer in self.active_connections:
            peer.sendall(data_json)

    def notify_pause(self) -> None:
        data = Data(type=DataType.PAUSE, data="")
        data_json = data.model_dump_json()
        data_json = data_json.encode()
        for peer in self.active_connections:
            peer.sendall(data_json)

    def notify_resume(self) -> None:
        data = Data(type=DataType.RESUME, data="")
        data_json = data.model_dump_json()
        data_json = data_json.encode()
        for peer in self.active_connections:
            peer.sendall(data_json)

    def notify_play_next(self, idx: int) -> None:
        data = Data(type=DataType.PLAY_NEXT, data=idx)
        data_json = data.model_dump_json()
        data_json = data_json.encode()
        for peer in self.active_connections:
            peer.sendall(data_json)

    def notify_play_prev(self, idx: int) -> None:
        data = Data(type=DataType.PLAY_NEXT, data=idx)
        data_json = data.model_dump_json()
        data_json = data_json.encode()
        for peer in self.active_connections:
            peer.sendall(data_json)

    def notify_stop(self) -> None:
        data = Data(type=DataType.STOP, data="")
        data_json = data.model_dump_json()
        data_json = data_json.encode()
        for peer in self.active_connections:
            peer.sendall(data_json)

    def send_audio(
        self,
        song: str,
        addr: socket.socket | None = None,
    ) -> None:
        export_bytes = BytesIO()
        song.export(export_bytes, format="mp3")
        export_bytes = export_bytes.getvalue()
        song_len = len(export_bytes)
        total_chunks = get_chunks_num(song_len)

        print(f"song len = {song_len}, slice of export bytes {export_bytes[:20]}")

        chunks = []
        for i in range(total_chunks):
            data_mp3 = DataMP3(
                chunk_num=i + 1,
                total_chunks=total_chunks,
                data=str(
                    export_bytes[i * AUDIO_CHUNK_SIZE : (i + 1) * AUDIO_CHUNK_SIZE]
                ),
            )
            chunk = Data(type=DataType.CHUNK_MP3, data=data_mp3)
            chunk_json = chunk.model_dump_json().encode()
            chunks.append(chunk_json)

        chunks_info = Data(
            type=DataType.CHUNKS_INFO, data=[len(chunk) for chunk in chunks]
        )
        chunks_info_json = chunks_info.model_dump_json().encode()

        if addr is None:
            peers = self.active_connections
        else:
            peers = [addr]

        for peer in peers:
            peer.sendall(chunks_info_json)

        time.sleep(0.1)

        for peer in peers:
            for i, chunk in enumerate(chunks):
                try:
                    bytes_sent = peer.send(chunk)
                except ConnectionAbortedError:
                    print("connection aborted")
                    break

                print("", chunk.decode()[2:50])
                if bytes_sent != chunks_info.data[i]:
                    print(
                        f"sent {bytes_sent} expected to send {chunks_info_json[i]}. peer {peer}"
                    )
                    break
                time.sleep(0.01)

    def send_all_audio(self, peer: socket.socket) -> None:
        audio_files = self.Player.get_audio_files()

        for n, song in enumerate(audio_files):
            print(f"sending {n}th audio")

            self.send_audio(song, peer)

            time.sleep(0.1)

        player_state = self.Player.get_state()
        playing_song_idx = self.Player.get_playing_song_idx()
        timestamp = self.Player.get_timestamp()

        self.send_player_info(player_state, playing_song_idx, timestamp, peer)

    def send_player_info(
        self,
        player_state: PlayerStates,
        song_idx: int,
        timestamp: int = 0,
        addr: socket.socket | None = None,
    ) -> None:
        if addr is None:
            peers = self.active_connections
        else:
            peers = [addr]

        for peer in peers:
            data = Data(
                type=DataType.PLAYER_INFO,
                data=PlayerInfo(
                    player_state=player_state,
                    song_idx=song_idx,
                    timestamp=timestamp,
                ),
            )
            data = data.model_dump_json()
            data = data.encode()
            peer.sendall(data)
            print(f"successfully sent player info to {peer}")

    def get_chunks(self, peer: socket.socket, chunk_info: List[Data]) -> bytes | None:
        print(f"received chunk_info {chunk_info}")
        for i, chunk_len in enumerate(chunk_info, 1):
            data = peer.recv(chunk_len).decode()
            print(f"received chunk #{i}")
            print(f"slice of audio chunk in get_audio: {data[:50]}")

            try:
                data = Data.model_validate_json(data)
            except ValidationError:
                print(
                    f"App received invalid audio data on {i}th iteration. {data[:50]}"
                )
                break

            if data.type != DataType.CHUNK_MP3:
                break

            data_mp3 = DataMP3.model_validate(data.data)
            chunk = ast.literal_eval(data_mp3.data)

            if i == 1:
                chunks = chunk
            elif i <= data_mp3.total_chunks:
                chunks += chunk
        else:
            audio_bytes = BytesIO(chunks)
            audio = AudioSegment.from_mp3(audio_bytes)
            self.Player.add_audio_files([audio])

    def set_player_info(self, data: dict) -> None:
        try:
            song_info: PlayerInfo = PlayerInfo.model_validate(data)
        except ValidationError:
            print(f"App received invalid player info {data[:70]}")
            return

        player_state = song_info.player_state
        playing_song_idx = song_info.song_idx
        timestamp = song_info.timestamp

        print(f"received with idx = {playing_song_idx}")

        self.Player.set_state(player_state, playing_song_idx, timestamp)

    def send_user_input(self, data: str) -> None:
        data = Data(type=DataType.USER_INPUT, data=data)
        data = data.model_dump_json()
        data = data.encode()

        for peer in self.active_connections:
            print(f"sent {data[:50]} to {peer}")
            try:
                peer.sendall(data)
            except ConnectionAbortedError:
                print("connection aborted")
                break
