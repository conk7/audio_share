import socket

from argparse import ArgumentParser
from pathlib import Path
from pydantic import BaseModel
from typing import Any
from enum import Enum


CHUNK_SIZE_SEND = 500 * 1024
CHUNK_SIZE_RECV = 500 * 1024
AUDIO_QUEUE_SIZE = 20
ROOM_SIZE = 5


def path_to_ffmpeg():
    SCRIPT_DIR = Path(__file__).parent.parent
    return str(Path(SCRIPT_DIR, "common", "ffmpeg", "bin", "ffmpeg.exe"))


def find_free_port(host: str, port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        while s.connect_ex((host, port)) == 0:
            port += 1
    return port


def add_CL_args(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument(
        "client_type", type=str, help="should be either <host> or <conn>"
    )
    parser.add_argument("--lhost", type=str, help="Local host address e.g. IPv4:PORT")
    parser.add_argument("--rhost", type=str, help="Remote host address e.g. IPv4:PORT")

    return parser


class PlayerStates(Enum):
    IDLE = 0
    PLAYING = 1
    PAUSED = 2


class DataType(Enum):
    GET_DATA = 0
    CONNECT = 1
    DISCONNECT = 2
    ADDRS = 3
    INFO = 4
    USER_INPUT = 5
    CHUNK_MP3 = 6
    CHUNKS_INFO = 7
    PAUSE = 8
    RESUME = 9
    SONG_CHANGE = 10
    SONG_INFO = 11
    PLAY_NEXT = 12
    PLAY = 13


class Data(BaseModel):
    type: DataType
    data: Any


class DataMP3(BaseModel):
    chunk_num: int
    total_chunks: int
    data: Any
