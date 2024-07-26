import ast
import socket

from typing import List
from time import sleep
from utils import DataType, Data, DataMP3, CHUNK_SIZE_SEND, CHUNK_SIZE_RECV, AUDIO_QUEUE_SIZE
from pydantic_core import _pydantic_core
from pathlib import Path
from pydub import AudioSegment, playback
from io import BytesIO


class AudioTransfer:
    def send_audio(self, song_name: str, timestamp: int) -> None:
        SCRIPT_DIR = Path(__file__).parent.parent.parent.parent
        song_path = str(Path(SCRIPT_DIR, song_name))

        try:
            song = AudioSegment.from_mp3(song_path)
        except FileNotFoundError:
            print(f"Could not find song with path {song_path}")
            return

        song -= 30

        export_bytes = BytesIO()
        song.export(export_bytes, format="mp3")
        export_bytes = export_bytes.getvalue()

        song_len = len(export_bytes)

        print(f"song len = {song_len}, slice of export bytes {export_bytes[:20]}")

        if song_len <= CHUNK_SIZE_SEND:
            total_chunks = 1
        elif song_len % CHUNK_SIZE_SEND == 0:
            total_chunks = (song_len / CHUNK_SIZE_SEND) - 1
        else:
            total_chunks = (song_len // CHUNK_SIZE_SEND) - 1

        chunks = []
        for i in range(total_chunks):
            data_mp3 = DataMP3(
                chunk_num=i + 1,
                total_chunks=total_chunks,
                data=str(export_bytes[i * CHUNK_SIZE_SEND : (i + 1) * CHUNK_SIZE_SEND]),
            )
            chunk = Data(type=DataType.CHUNK_MP3, data=data_mp3)
            chunk_json = chunk.model_dump_json().encode()
            chunks.append(chunk_json)

        chunks_info = Data(
            type=DataType.CHUNKS_INFO, data=[len(chunk) for chunk in chunks]
        )
        chunks_info_json = chunks_info.model_dump_json().encode()

        for peer in self.peers:
            peer.sendall(chunks_info_json)

        sleep(0.1)

        if self.is_playing:
            is_playing = False
        else:
            is_playing = True

        # put it here to minimise playback latency between local host and remote peers
        self.add_audio_to_queue(song)

        for peer in self.peers:
            for i, chunk in enumerate(chunks):
                bytes_sent = peer.send(chunk)
                print("", chunk.decode()[2:50])
                if bytes_sent != chunks_info.data[i]:
                    print(
                        f"sent {bytes_sent} expected to send {chunks_info_json[i]}. conn {peer}"
                    )
                    break
                sleep(0.01)
            else:
                data = Data(
                    type=DataType.SONG_INFO,
                    data=[is_playing, timestamp, self.playing_song_idx],
                )
                data = data.model_dump_json()
                data = data.encode()
                peer.sendall(data)
                print(f"successfully sent audio to {peer}")

    def send_all_audio(self, peer: socket.socket) -> None:
        for n, audio in enumerate(self.audio_files):
            export_bytes = BytesIO()
            audio.export(export_bytes, format="mp3")
            export_bytes = export_bytes.getvalue()
            song_len = len(export_bytes)

            print(f"song len = {song_len}, slice of export bytes {export_bytes[:20]}")

            if song_len <= CHUNK_SIZE_SEND:
                total_chunks = 1
            elif song_len % CHUNK_SIZE_SEND == 0:
                total_chunks = (song_len / CHUNK_SIZE_SEND) - 1
            else:
                total_chunks = (song_len // CHUNK_SIZE_SEND) - 1

            print(f"total num of chunks = {total_chunks}")

            chunks = []
            for i in range(total_chunks):
                data_mp3 = DataMP3(
                    chunk_num=i,
                    total_chunks=total_chunks,
                    data=str(
                        export_bytes[i * CHUNK_SIZE_SEND : (i + 1) * CHUNK_SIZE_SEND]
                    ),
                )
                chunk = Data(type=DataType.CHUNK_MP3, data=data_mp3)
                chunk_json = chunk.model_dump_json().encode()
                chunks.append(chunk_json)

            chunks_info = Data(
                type=DataType.CHUNKS_INFO, data=[len(chunk) for chunk in chunks]
            )
            chunks_info_json = chunks_info.model_dump_json().encode()

            peer.sendall(chunks_info_json)

            sleep(0.1)

            if n == self.playing_song_idx and self.is_playing:
                is_playing = True
            else:
                is_playing = False

            timestamp = self.song_played_time

            for i, chunk in enumerate(chunks):
                bytes_sent = peer.send(chunk)
                print("", chunk.decode()[2:50])
                if bytes_sent != chunks_info.data[i]:
                    print(
                        f"sent {bytes_sent} expected to send {chunks_info_json[i]}. conn {peer}"
                    )
                    break
                sleep(0.01)
            else:
                data = Data(
                    type=DataType.SONG_INFO,
                    data=[is_playing, timestamp, self.playing_song_idx],
                )
                data = data.model_dump_json()
                data = data.encode()
                peer.sendall(data)
                print(f"successfully sent audio to {peer}")

            sleep(0.1)

    def get_audio(self, conn: socket.socket, chunk_info: List[Data]) -> None:
        print(f"received chunk_info {chunk_info}")
        for i, chunk_len in enumerate(chunk_info, 1):
            data = conn.recv(chunk_len).decode()
            print(f"received chunk #{i}")
            print(f"slice of audio chunk in get_audio: {data[:50]}")

            try:
                data = Data.model_validate_json(data)
            except _pydantic_core.ValidationError:
                print(
                    f"App received invalid audio data on {i}th iteration. {data[:50]}"
                )
                continue

            if data.type != DataType.CHUNK_MP3:
                break

            data_mp3 = DataMP3.model_validate(data.data)
            chunk = ast.literal_eval(data_mp3.data)

            if i == 1:
                self.audio_file_per_peer[conn] = chunk
            elif i <= data_mp3.total_chunks:
                self.audio_file_per_peer[conn] += chunk

        data = conn.recv(CHUNK_SIZE_RECV).decode()

        try:
            data = Data.model_validate_json(data)
        except _pydantic_core.ValidationError:
            print(f"App received invalid audio data {data[:70]}")
            self.chunks_per_peer.pop(conn)
            return

        if data.type != DataType.SONG_INFO:
            print(f"App received audio data of wrong type {data[:50]}")
            self.chunks_per_peer.pop(conn)
            return

        is_playing, timestamp, playing_song_idx = data.data

        print(
            f"received with is_playing = {is_playing} and idx = {self.playing_song_idx}"
        )

        audio_bytes = BytesIO(self.audio_file_per_peer[conn])
        # print(f"song len when received {len(audio_bytes.getvalue())}")
        song = AudioSegment.from_mp3(audio_bytes)
        self.add_audio_to_queue(song)
        self.playing_song_idx = playing_song_idx

        # print("audio files", self.audio_files)

        if self.playing_song is None and self.playing_song_idx != -1:
            self.playing_song = playback._play_with_simpleaudio(
                self.audio_files[self.playing_song_idx][timestamp:]
            )
            if is_playing:
                self.is_playing = is_playing
            else:
                self.playing_song.pause()
                self.is_playing = is_playing

        self.chunks_per_peer.pop(conn)

        print(f"FINISHED RECEIVING AUDIO from {conn.getpeername()}")

    def add_audio_to_queue(self, song) -> None:
        self.audio_files.append(song)

        if len(self.audio_files) > AUDIO_QUEUE_SIZE:
            self.audio_files.pop(0)
