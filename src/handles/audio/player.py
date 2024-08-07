import time
import threading

from pathlib import Path
from typing import List
from simpleaudio import PlayObject
from pydub import AudioSegment, playback
from utils import PlayerStates, singleton, init_ffmpeg, AUDIO_QUEUE_SIZE


@singleton
class Player:
    def __init__(self):
        self.state: PlayerStates = PlayerStates.IDLE
        self.audio_files: List[AudioSegment] = []
        self.playing_song_idx: int = -1
        self.playing_song: PlayObject | None = None
        self.timestamp = 0

        init_ffmpeg()

        threading.Thread(target=self.__handle_playback).start()

    def __add_to_queue(self, song) -> None:
        self.audio_files.append(song)
        if len(self.audio_files) > AUDIO_QUEUE_SIZE:
            self.audio_files.pop(0)

    def add_audio(self, audio_name: str) -> AudioSegment | None:
        SCRIPT_DIR = Path(__file__).parent.parent.parent.parent
        audio_path = str(Path(SCRIPT_DIR, audio_name))

        try:
            audio = AudioSegment.from_mp3(audio_path)
        except FileNotFoundError:
            print(f"Could not find song with path {audio_path}")
            return None

        audio -= 30

        self.__add_to_queue(audio)

        return audio

    def add_audio_files(self, audio_files: List[AudioSegment]) -> None:
        for audio in audio_files:
            # audio -= 30  # might be used to change volume in client
            self.__add_to_queue(audio)

    def set_state(
        self,
        player_state: PlayerStates,
        playing_song_idx: int,
        timestamp: int,
    ) -> None:
        self.playing_song_idx = playing_song_idx
        self.timestamp = timestamp
        self.state = player_state

        if (
            player_state == PlayerStates.PLAYING
            and len(self.audio_files) >= playing_song_idx
        ):
            self.stop()
            self.playing_song = playback._play_with_simpleaudio(
                self.audio_files[self.playing_song_idx][timestamp:]
            )
        # if self.playing_song is None and self.playing_song_idx != -1:
        #     self.playing_song = playback._play_with_simpleaudio(
        #         self.audio_files[self.playing_song_idx][timestamp:]
        #     )
        #     if is_playing:
        #         self.state = PlayerStates.PLAYING
        #     else:
        #         self.playing_song.pause()
        #         self.state = PlayerStates.PAUSED

    def play(self, idx: int) -> None:
        if idx is None or not 0 <= idx < len(self.audio_files):
            return

        if self.state == PlayerStates.PLAYING:
            self.stop()

        self.playing_song = playback._play_with_simpleaudio(self.audio_files[idx])
        self.playing_song_idx = idx
        self.state = PlayerStates.PLAYING

    def pause(self) -> None:
        if self.playing_song is not None and self.state == PlayerStates.PLAYING:
            self.playing_song.pause()
            self.state = PlayerStates.PAUSED

    def resume(self) -> None:
        print(
            f"resuming audio with playingsong is None = {self.playing_song is None} and PlayerState = {self.state}"
        )
        if self.playing_song is not None and self.state == PlayerStates.PAUSED:
            self.playing_song.resume()
            self.state = PlayerStates.PLAYING

    def play_next(self) -> int:
        if len(self.audio_files) == 0:
            return

        self.playing_song_idx += 1
        self.playing_song_idx %= len(self.audio_files)

        if self.playing_song is not None:
            self.playing_song.stop()
        self.playing_song = playback._play_with_simpleaudio(
            self.audio_files[self.playing_song_idx]
        )

        self.timestamp = 0
        self.state = PlayerStates.PLAYING

        return self.playing_song_idx

    def play_prev(self) -> int:
        if len(self.audio_files) == 0:
            return

        self.playing_song_idx -= 1
        self.playing_song_idx %= len(self.audio_files)

        if self.playing_song is not None:
            self.playing_song.stop()
        self.playing_song = playback._play_with_simpleaudio(
            self.audio_files[self.playing_song_idx]
        )

        self.timestamp = 0
        self.state = PlayerStates.PLAYING

        return self.playing_song_idx

    def stop(self) -> None:
        if self.playing_song is not None:
            self.playing_song.stop()
            self.state = PlayerStates.IDLE
            self.timestamp = 0
            self.playing_song_idx = -1

    def get_num_of_audio_files(self) -> int:
        return len(self.audio_files)

    def get_state(self) -> PlayerStates:
        return self.state

    def get_audio_files(self) -> List[AudioSegment]:
        return self.audio_files.copy()

    def get_playing_song_idx(self) -> int:
        return self.playing_song_idx

    def get_timestamp(self) -> int:
        return self.timestamp

    def __handle_playback(self) -> None:
        prev_playing_song_idx: int = -1
        prev_time = 0

        while True:
            if (
                prev_playing_song_idx != self.playing_song_idx
                and self.playing_song_idx != -1
            ):
                prev_playing_song_idx = self.playing_song_idx

            if self.state == PlayerStates.PLAYING:
                self.timestamp += int((time.monotonic() - prev_time) * 1000)

            if 0 <= self.playing_song_idx < len(
                self.audio_files
            ) and self.timestamp >= len(self.audio_files[self.playing_song_idx]):
                self.play_next()
                prev_playing_song_idx = -1
                self.timestamp = 0

            prev_time = time.monotonic()
            time.sleep(0.1)
