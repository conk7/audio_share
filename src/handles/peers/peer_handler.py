import select

from time import sleep
from utils import Data, CHUNK_SIZE_RECV
from pydantic_core._pydantic_core import ValidationError
from ..input.commands import HandleCommands
from ..audio.audio_playback import AudioPlayback
from ..input.userinput import UserInput


class PeerHandler(HandleCommands, AudioPlayback, UserInput):
    def handle_peers(self) -> None:
        while True:
            self.handle_recv()
            if self.user_input is not None:
                self.handle_send(self.user_input)
                self.user_input = None
            else:
                self.handle_send()
            sleep(0.1)

    def handle_recv(self) -> None:
        if len(self.peers) == 0:
            return
        r, _, _ = select.select(self.peers, [], [], 0.1)
        for conn in r:
            data = conn.recv(CHUNK_SIZE_RECV).decode()

            print(f"App received {data[:50]} from {conn}")

            try:
                data = Data.model_validate_json(data)
            except ValidationError:
                print("App received invalid data")
                continue
            self.handle_commands(conn, data)

    def handle_send(self, data: str = "") -> None:
        if data == "dc":
            self.disconnect()

        elif data[:3] == "add":
            song_name = data[4:]
            if song_name != "":
                song = self.add_audio(song_name)
                self.send_audio(song, len(self.audio_files) - 1, False)

        elif data[:4] == "play":
            song_idx = data[5:]
            if song_idx == "":
                return
            song_idx = int(song_idx)
            self.play_audio(song_idx)

        elif data == "pause":
            self.pause_audio()

        elif data == "resume":
            self.resume_audio()

        elif data == "next":
            self.play_next_audio()

        elif data == "prev":
            self.play_prev_audio()

        elif data == "stop":
            self.stop_audio()

        elif data != "":
            self.send_user_input(data)
