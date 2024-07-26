import time

from time import sleep
from utils import DataType, Data, PlayerStates
from pydub import playback


class AudioPlayback:
    def play_audio(self, idx: int) -> None:
        if (
            self.state == PlayerStates.PLAYING or idx >= len(self.audio_files) or idx < 0
        ):  # 0 <= idx <= len()
            return

        data = Data(type=DataType.PLAY, data=idx)
        data_json = data.model_dump_json()
        data_json = data_json.encode()
        for peer in self.peers:
            peer.sendall(data_json)

        self.playing_song = playback._play_with_simpleaudio(self.audio_files[idx])
        self.playing_song_idx = idx
        self.state = PlayerStates.PLAYING

    def pause_audio(self) -> None:
        if self.playing_song is not None and self.state == PlayerStates.PLAYING:
            data = Data(type=DataType.PAUSE, data="")
            data_json = data.model_dump_json()
            data_json = data_json.encode()

            for peer in self.peers:
                peer.sendall(data_json)

            self.playing_song.pause()
            self.state = PlayerStates.PAUSED

    def resume_audio(self) -> None:
        print(
            f"resuming audio with playingsong is None = {self.playing_song is None} and PlayerState = {self.state}"
        )
        if self.playing_song is not None and self.state == PlayerStates.PAUSED:
            for peer in self.peers:
                data = Data(type=DataType.RESUME, data="")
                data_json = data.model_dump_json()
                data_json = data_json.encode()
                peer.sendall(data_json)
            self.playing_song.resume()
            self.state = PlayerStates.PLAYING

    def play_next_song(self) -> None:
        if len(self.audio_files) <= self.playing_song_idx + 1:
            self.playing_song_idx = 0
        else:
            self.playing_song_idx += 1

        data = Data(type=DataType.PLAY_NEXT, data=self.playing_song_idx)
        data_json = data.model_dump_json()
        data_json = data_json.encode()
        for peer in self.peers:
            peer.sendall(data_json)

        if self.playing_song is not None:
            self.playing_song.stop()
        self.playing_song = playback._play_with_simpleaudio(
            self.audio_files[self.playing_song_idx]
        )

        self.song_played_time = 0

    def handle_playback(self) -> None:
        prev_playing_song_idx: int = -1
        prev_time = 0

        while True:
            if (
                prev_playing_song_idx != self.playing_song_idx
                and self.playing_song_idx != -1
            ):
                prev_playing_song_idx = self.playing_song_idx

            if self.state == PlayerStates.PLAYING:
                self.song_played_time += int((time.monotonic() - prev_time) * 1000)


            if self.playing_song_idx != -1 and self.song_played_time >= len(
                self.audio_files[self.playing_song_idx]
            ):
                self.play_next_song()
                prev_playing_song_idx = -1
                self.song_played_time = 0

            prev_time = time.monotonic()
            sleep(0.1)
