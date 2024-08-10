from pydantic import BaseModel
from typing import Any
from enum import Enum


class PlayerStates(Enum):
    IDLE = 0
    PLAYING = 1
    PAUSED = 2


class DataType(Enum):
    GET_ADDRS = 0
    CONNECT = 1
    DISCONNECT = 2
    ADDRS = 3
    INFO = 4
    USER_INPUT = 5
    CHUNK_MP3 = 6
    CHUNKS_INFO = 7
    PAUSE = 8
    RESUME = 9
    PLAYER_INFO = 11
    SONG_CHANGE = 10
    PLAY_NEXT = 12
    PLAY = 13
    STOP = 14


class Data(BaseModel):
    type: DataType
    data: Any


class DataMP3(BaseModel):
    chunk_num: int
    total_chunks: int
    data: Any


class PlayerInfo(BaseModel):
    player_state: PlayerStates
    song_idx: int
    timestamp: int
