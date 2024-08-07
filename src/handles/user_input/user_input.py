import threading

from utils import singleton
from ..peers.connection_manager import ConnectionManager
from ..audio.player import Player


@singleton
class UserInputManager:
    def __init__(self, ConnManager: ConnectionManager, player: Player) -> None:
        self.user_input: str = ""
        self.ConnManager = ConnManager
        self.Player = player

    def __handle_user_input(self) -> None:
        while True:
            self.user_input = input().strip().lower()
            self.__parse_user_input(self.user_input)

    def handle_user_input(self) -> None:
        threading.Thread(target=self.__handle_user_input).start()

    def __parse_user_input(self, user_input: str) -> None:
        if user_input == "":
            return
        elif user_input == "dc":
            self.ConnManager.disconnect()

        elif user_input[:3] == "add":
            audio_name = user_input[4:]
            if audio_name == "" or not audio_name.endswith(".mp3"):
                return

            audio = self.Player.add_audio(audio_name)
            if audio is None:
                return

            self.ConnManager.send_audio(audio)

        elif user_input[:4] == "play":
            song_idx = user_input[5:]
            if song_idx == "":
                print("Incorrect index")
                return
            try:
                song_idx = int(song_idx)
            except ValueError:
                print("Incorrect index")
                return

            self.Player.play(song_idx)
            self.ConnManager.notify_play(song_idx)

        elif user_input == "pause":
            self.Player.pause()
            self.ConnManager.notify_pause()

        elif user_input == "resume":
            self.Player.resume()
            self.ConnManager.notify_resume()

        elif user_input == "next":
            idx = self.Player.play_next()
            self.ConnManager.notify_play_next(idx)

        elif user_input == "prev":
            idx = self.Player.play_prev()
            self.ConnManager.notify_play_prev(idx)

        elif user_input == "stop":
            self.Player.stop()
            self.ConnManager.notify_stop()

        elif user_input != "":
            self.ConnManager.send_user_input(user_input)
