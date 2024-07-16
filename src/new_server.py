import socket
import select
import threading
import os
import stun

from typing import List
from time import sleep
from utils import DataType, Data, DataMP3
from mp3_handles import path_to_ffmpeg
from pathlib import Path
from pydub import AudioSegment, playback
from io import BytesIO


class ServerStates:
    IDLE = 0
    PLAYING = 1


USER_INPUT = None
IS_RUNNING = True


CHUNK_SIZE_SEND = 500 * 1024
CHUNK_SIZE_RECV = 1024


class App:
    def __init__(self, ip: str, port: int) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((ip, port))

        # _, self.external_ip, self.external_port = stun.get_ip_info(
        #     ip, port, stun_host="stun.l.google.com", stun_port=19302
        # )

        self.external_ip = "127.0.0.1"
        self.external_port = port

        self.conns: List[socket.socket] = []
        self.addrs: List[str] = []
        self.state = ServerStates.IDLE

        AudioSegment.ffmpeg = path_to_ffmpeg()
        os.environ["PATH"] += os.pathsep + str(Path(path_to_ffmpeg()).parent)

    def __handle_commands(self, conn: socket.socket, data: Data) -> None:
        data_type = data.type
        if data_type == DataType.GET_DATA:
            addr = data.data
            if len(self.conns) > 0:
                self.__notify_about_new_peer(addr)

            self.addrs.append(addr)

            print(f"self addrs: {self.addrs}")

            reply = Data(type=DataType.ADDRS, data=self.addrs[:-1])
            reply_json = reply.model_dump_json()

            print(f"handle_comms with type {data_type} sent\n {reply_json} to {conn}")

            conn.send(reply_json.encode())
        elif data_type == DataType.DISCONNECT:
            addr = data.data
            idx = self.addrs.index(addr)
            self.addrs.pop(idx)
            self.conns.pop(idx)
        elif data_type == DataType.USER_INPUT:
            reply = Data(type=DataType.INFO, data="server received user input")
            reply_json = reply.model_dump_json()

            print(f"handle_comms with type {data_type} sent\n {reply_json} to {conn}")

            conn.send(reply_json.encode())

    def __stream_audio(self, song: AudioSegment) -> None:
        export_bytes = BytesIO()
        song.export(export_bytes, format="wav")  # to mp3
        export_bytes = export_bytes.getvalue()
        song_len = len(export_bytes)

        # print("SONG LEN", song_len)

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

        for conn in self.conns:
            conn.sendall(chunks_info_json)

        for conn in self.conns:
            for i, chunk in enumerate(chunks):
                bytes_sent = conn.send(chunk)
                print("", chunk.decode()[2:50])
                if bytes_sent != chunks_info.data[i]:
                    # print(f"sent {bytes_sent} expected to send {chunks_info_json[i]}")
                    break
                sleep(0.001)

    def __handle_recv(self) -> None:
        if len(self.conns) == 0:
            return
        r, _, _ = select.select(self.conns, [], [], 0.1)
        for conn in r:
            data = conn.recv(1024).decode()

            print(f"server received {data} from {conn}")

            data = Data.model_validate_json(data)
            self.__handle_commands(conn, data)

    def __handle_send(self, data: str = "") -> None:
        if data == "dc":
            addr = f"{self.external_ip}:{self.external_port}"
            data = Data(type=DataType.DISCONNECT, data=addr)
            data = data.model_dump_json()
            for conn in self.conns:
                print(f"sent {data} to {conn}")
                conn.sendall(data.encode())
            self.__disconnect()
        elif data[:4] == "play":
            song_name = data[5:]
            SCRIPT_DIR = Path(__file__).parent.parent
            song_path = str(Path(SCRIPT_DIR, song_name))

            print(song_path)

            song = AudioSegment.from_mp3(song_path)
            song -= 30
            self.__stream_audio(song)

            # playback.play(song)

        elif data != "":
            data = Data(type=DataType.USER_INPUT, data=data)
            data = data.model_dump_json()
            for conn in self.conns:
                print(f"sent {data} to {conn}")
                conn.sendall(data.encode())

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
        for conn in self.conns[:-1]:
            data = Data(type=DataType.CONNECT, data=addr)
            data = data.model_dump_json()
            conn.send(data.encode())

    def __handle_user_input(self) -> None:
        global USER_INPUT, IS_RUNNING
        while IS_RUNNING:
            USER_INPUT = input().strip().lower()

    def __disconnect(self) -> None:
        global IS_RUNNING
        IS_RUNNING = False

        for conn in self.conns:
            conn.close()
        self.conns.clear()

        self.sock.close()

        os._exit(0)

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

            self.conns.append(conn)

            print(self.conns)


if __name__ == "__main__":
    BASE_PORT = 8765
    server = App("0.0.0.0", BASE_PORT)
    server.host()
