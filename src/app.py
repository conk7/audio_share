import argparse
import threading

from injectors import get_connection_manager, get_user_input_manager, get_player
from utils import add_CL_args
from handles.peers.connection_manager import ConnectionManager
from src.handles.user_input.user_input import UserInputManager
from handles.audio.player import Player


parser = argparse.ArgumentParser()
parser = add_CL_args(parser)


class App:
    def __init__(self, ip: str, port: int) -> None:
        self.Player: Player = get_player()
        self.ConnectionManager: ConnectionManager = get_connection_manager(ip, port, self.Player)
        self.InputManager: UserInputManager = get_user_input_manager(self.ConnectionManager, self.Player)

    def run_handler_threads(self) -> None:
        threading.Thread(target=self.handle_peers).start()
        threading.Thread(target=self.handle_user_input).start()
        threading.Thread(target=self.handle_playback).start()

    def host(self) -> None:
        self.ConnectionManager.host()
        self.InputManager.handle_user_input()
        # run handlers

    def connect(self, ip: str, port: int) -> None:
        try:
            self.ConnectionManager.connect(ip, port)
        except Exception:
            print("Could not connect to the server")
            return
        
        self.InputManager.handle_user_input()

        # run handlers


if __name__ == "__main__":
    args = parser.parse_args()
    client_type = args.client_type
    if client_type == "host":
        lip, lport = args.lhost.split(":")
        lport = int(lport)
        server = App("0.0.0.0", lport)
        server.host()
    elif client_type == "conn":
        lip, lport = args.lhost.split(":")
        lport = int(lport)
        server = App("0.0.0.0", lport)
        rip, rport = args.rhost.split(":")
        rport = int(rport)
        server.connect(rip, rport)
