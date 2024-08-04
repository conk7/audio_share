from handles.peers.connection_manager import ConnectionManager
from src.handles.user_input.user_input import UserInputManager
from handles.audio.player import Player


def get_connection_manager(ip: str, port: int, player: Player) -> ConnectionManager:
    return ConnectionManager(ip, port, player)


def get_user_input_manager(connection_manager: ConnectionManager, player: Player) -> UserInputManager:
    return UserInputManager(connection_manager, player)


def get_player() -> Player:
    return Player()
