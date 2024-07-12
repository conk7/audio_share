import socket
from pydantic import BaseModel
from typing import Any
from enum import Enum

def find_free_port(host: str, port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        while s.connect_ex((host, port)) == 0:
            port += 1
    return port


class DataType(Enum):
    GET_DATA = 0
    ADDRS = 1
    INFO = 2
    NEW_PEER = 3
    USER_INPUT = 4


class Data(BaseModel):
    type: DataType
    data: Any