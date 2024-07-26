import socket

from utils import DataType, Data
from pydub import playback
from ..peers.peers_utils import PeerUtils
from ..audio.audio_transfer import AudioTransfer


class HandleCommands(AudioTransfer, PeerUtils):
    def handle_commands(self, conn: socket.socket, data: Data) -> None:
        data_type = data.type
        if data_type == DataType.GET_DATA:
            addr = data.data
            if len(self.peers) > 0:
                self.notify_about_new_peer(addr)

            self.addrs.append(addr)

            reply = Data(type=DataType.ADDRS, data=self.addrs[:-1])
            reply_json = reply.model_dump_json()
            reply_json = reply_json.encode()
            conn.sendall(reply_json)

            if len(self.audio_files) > 0:
                self.send_all_audio(conn)

        elif data_type == DataType.CONNECT:
            addr = data.data
            self.connect_peer(addr)
        elif data_type == DataType.DISCONNECT:
            addr = data.data
            idx = self.addrs.index(addr)
            self.addrs.pop(idx)
            self.peers.pop(idx)
        elif data_type == DataType.CHUNKS_INFO:
            self.chunks_per_peer[conn] = data.data
            self.get_audio(conn, data.data)
        elif data_type == DataType.USER_INPUT:
            reply = Data(type=DataType.INFO, data="server received user input")
            reply_json = reply.model_dump_json()

            # print(f"handle_comms with type {data_type} sent\n {reply_json} to {conn}")

            conn.send(reply_json.encode())
        elif data_type == DataType.PLAY:
            if self.playing_song is not None and self.is_playing:
                self.playing_song.stop()

            self.playing_song_idx = data.data
            self.playing_song = playback._play_with_simpleaudio(
                self.audio_files[self.playing_song_idx]
            )
            self.is_playing = True
        elif data_type == DataType.PAUSE:
            if self.playing_song is not None and self.is_playing:
                self.playing_song.pause()
                self.is_playing = False
        elif data_type == DataType.RESUME:
            if self.playing_song is not None and not self.is_playing:
                self.playing_song.resume()
                self.is_playing = True
        elif data_type == DataType.PLAY_NEXT:
            if self.playing_song is not None:
                self.playing_song.stop()
            self.playing_song_idx = data.data
            self.playing_song = playback._play_with_simpleaudio(
                self.audio_files[self.playing_song_idx]
            )
            self.is_playing = True
