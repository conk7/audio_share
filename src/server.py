import socket
from typing import Tuple
import threading


class ServerStates:
    IDLE = 0
    PLAYING = 1


class Server:
    state: ServerStates
    addr: Tuple[str, int]
    sock: socket.socket

    def __init__(self) -> None:
        source_ip = "0.0.0.0"
        source_port = 8765
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((source_ip, source_port))

        self.state = ServerStates.IDLE

    def __serve(self, conn: socket) -> None:
        while True:
            data = conn.recv(1024)
            data = data.decode()
            if data == "stop":
                conn.sendall(b"stopping server")
                conn.close()
                break
            print("\r", "<", data)
            conn.sendall(b"received data")


    def start(self) -> None:
        self.sock.listen(1)
        conn, addr = self.sock.accept()
        print(f"accepted connection from {addr}")
        threading.Thread(target=self.__serve, args=(conn,)).start()
        print(f"started serving for {addr}")

    # def getLink(self) -> str:
    #     return ""


if __name__ == "__main__":
    server = Server()
    server.start()
