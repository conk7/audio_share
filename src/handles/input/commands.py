import socket

from utils import DataType, Data, PlayerStates
from pydub import playback
from ..peers.peer_utils import PeerUtils
from ..audio.audio_transfer import AudioTransfer


class HandleCommands(AudioTransfer, PeerUtils):
    def handle_commands(self, peer: socket.socket, data: Data) -> None:
        data_type = data.type
        if data_type == DataType.GET_DATA:
            addr = data.data
            if len(self.peers) > 0:
                self.notify_about_new_peer(addr)

            self.addrs.append(addr)

            reply = Data(type=DataType.ADDRS, data=self.addrs[:-1])
            reply_json = reply.model_dump_json()
            reply_json = reply_json.encode()
            peer.sendall(reply_json)

            if len(self.audio_files) > 0:
                self.get_audio(peer)

        elif data_type == DataType.CONNECT:
            addr = data.data
            self.connect_peer(addr)
        elif data_type == DataType.DISCONNECT:
            addr = data.data
            idx = self.addrs.index(addr)
            self.addrs.pop(idx)
            self.peers.pop(idx)
        elif data_type == DataType.CHUNKS_INFO:
            self.get_all_audio(peer, data.data)
        elif data_type == DataType.PLAY:
            self.stop_playback()
            self.playing_song_idx = data.data
            self.playing_song = playback._play_with_simpleaudio(
                self.audio_files[self.playing_song_idx]
            )
            self.state = PlayerStates.PLAYING
        elif data_type == DataType.PAUSE:
            if self.playing_song is not None and self.state == PlayerStates.PLAYING:
                self.playing_song.pause()
                self.state = PlayerStates.PAUSED
        elif data_type == DataType.RESUME:
            if self.playing_song is not None and self.state == PlayerStates.PAUSED:
                self.playing_song.resume()
                self.state = PlayerStates.PLAYING
        elif data_type == DataType.PLAY_NEXT:
            self.stop_playback()
            self.playing_song_idx = data.data
            self.playing_song = playback._play_with_simpleaudio(
                self.audio_files[self.playing_song_idx]
            )
            self.state = PlayerStates.PLAYING
        elif data_type == DataType.STOP:
            self.stop_playback()
