from utils import PlayerStates, AUDIO_QUEUE_SIZE


class AudioUtils:
    def add_to_queue(self, song) -> None:
        self.audio_files.append(song)
        if len(self.audio_files) > AUDIO_QUEUE_SIZE:
            self.audio_files.pop(0)

    def stop_audio(self) -> None:
        if self.playing_song is not None:
            self.playing_song.stop()
            self.song_played_time = 0
            self.playing_song_idx = -1
            self.state = PlayerStates.IDLE
