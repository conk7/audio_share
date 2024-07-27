from utils import AUDIO_QUEUE_SIZE

class AudioUtils:
    def add_to_queue(self, song) -> None:
            self.audio_files.append(song)
            if len(self.audio_files) > AUDIO_QUEUE_SIZE:
                self.audio_files.pop(0)