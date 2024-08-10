import socket
import os

from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Callable
from pydub import AudioSegment
from constants import AUDIO_CHUNK_SIZE

def path_to_ffmpeg():
    SCRIPT_DIR = Path(__file__).parent.parent
    return Path(SCRIPT_DIR, "common", "ffmpeg", "bin", "ffmpeg.exe")


def init_ffmpeg():
    path = path_to_ffmpeg()
    AudioSegment.ffmpeg = str(path)
    os.environ["PATH"] += os.pathsep + str(path.parent)


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


def get_chunks_num(song_len) -> int:
    if song_len <= AUDIO_CHUNK_SIZE:
        return 1
    elif song_len % AUDIO_CHUNK_SIZE == 0:
        return (song_len / AUDIO_CHUNK_SIZE) - 1
    else:
        return (song_len // AUDIO_CHUNK_SIZE) - 1


def singleton(class_: type) -> Callable:
    instances = {}

    def getinstance(*args: tuple[Any], **kwargs: dict[str, Any]) -> object:
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]

    return getinstance
