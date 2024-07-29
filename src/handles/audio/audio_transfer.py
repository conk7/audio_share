import ast
import socket

from typing import List
from time import sleep
from utils import (
    DataType,
    Data,
    DataMP3,
    SongInfo,
    CHUNK_SIZE_SEND,
    CHUNK_SIZE_RECV,
    PlayerStates,
    get_chunks_num,
)
from pydantic_core import _pydantic_core
from pydub import AudioSegment, playback
from io import BytesIO
from .audio_utils import AudioUtils


class AudioTransfer(AudioUtils):
    def send_audio(
        self,
        song: str,
        song_idx: int,
        is_playing: bool,
        timestamp: int = 0,
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
                data=str(export_bytes[i * CHUNK_SIZE_SEND : (i + 1) * CHUNK_SIZE_SEND]),
            )
            chunk = Data(type=DataType.CHUNK_MP3, data=data_mp3)
            chunk_json = chunk.model_dump_json().encode()
            chunks.append(chunk_json)

        chunks_info = Data(
            type=DataType.CHUNKS_INFO, data=[len(chunk) for chunk in chunks]
        )
        chunks_info_json = chunks_info.model_dump_json().encode()

        if addr is None:
            peers = self.peers
            if self.state == PlayerStates.PLAYING:
                is_playing = True
            else:
                is_playing = False
        else:
            peers = [addr]

        for peer in peers:
            peer.sendall(chunks_info_json)

        sleep(0.1)

        for peer in peers:
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
                    data=SongInfo(
                        song_idx=song_idx,
                        is_playing=is_playing,
                        timestamp=timestamp,
                    ),
                )
                data = data.model_dump_json()
                data = data.encode()
                peer.sendall(data)
                print(f"successfully sent audio to {peer}")

    def sync_audio(self, peer: socket.socket) -> None:
        for n, song in enumerate(self.audio_files):
            if n == self.playing_song_idx and self.state == PlayerStates.PLAYING:
                is_playing = True
                timestamp = (
                    self.song_played_time + 900
                )  # add some ms to compensate latency
                self.send_audio(song, n, is_playing, timestamp, peer)
            else:
                is_playing = False
                timestamp = 0
                self.send_audio(song, n, is_playing, timestamp, peer)

            sleep(0.1)

    def get_audio(self, conn: socket.socket, chunk_info: List[Data]) -> None:
        self.get_chunks(conn, chunk_info)
        self.get_audio_info(conn)

    def get_chunks(self, conn: socket.socket, chunk_info: List[Data]) -> None:
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

    def get_audio_info(self, conn: socket.socket) -> None:
        data = conn.recv(CHUNK_SIZE_RECV).decode()

        try:
            data = Data.model_validate_json(data)
        except _pydantic_core.ValidationError:
            print(f"App received invalid audio data {data[:70]}")
            self.audio_file_per_peer.pop(conn)
            return

        if data.type != DataType.SONG_INFO:
            print(f"App received audio data of wrong type {data[:50]}")
            self.audio_file_per_peer.pop(conn)
            return

        song_info: SongInfo = SongInfo.model_validate(data.data)
        playing_song_idx = song_info.song_idx
        is_playing = song_info.is_playing
        timestamp = song_info.timestamp

        print(f"received with is_playing = {is_playing} and idx = {playing_song_idx}")

        audio_bytes = BytesIO(self.audio_file_per_peer[conn])
        song = AudioSegment.from_mp3(audio_bytes)
        self.add_to_queue(song)

        if is_playing:
            self.playing_song_idx = playing_song_idx

        if self.playing_song is None and self.playing_song_idx != -1:
            self.playing_song = playback._play_with_simpleaudio(
                self.audio_files[self.playing_song_idx][timestamp:]
            )
            if is_playing:
                self.state = PlayerStates.PLAYING
            else:
                self.playing_song.pause()
                self.state = PlayerStates.PAUSED

        self.audio_file_per_peer.pop(conn)

        print(f"FINISHED RECEIVING AUDIO from {conn.getpeername()}")
