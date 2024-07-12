import socket
import select
from typing import List
import threading
from time import sleep
from utils import DataType, Data
import stun


USER_INPUT = None
IS_RUNNING = True


class App:
    def __init__(self, ip: str, port: int) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((ip, port))

        mock_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        mock_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mock_sock.bind((ip, port))
        _, nat = stun.get_nat_type(
            mock_sock, ip, port, stun_host="stun.l.google.com", stun_port=19302
        )
        mock_sock.close()

        # self.external_ip = nat["ExternalIP"]
        self.external_ip = "127.0.0.1"
        self.external_port = nat["ExternalPort"]

        self.conns: List[socket.socket] = []
        self.addrs: List[str] = []
        # self.state = ServerStates.IDLE

    def __handle_commands(self, conn: socket.socket, data: Data) -> None:
        data_type = data.type
        if data_type == DataType.CONNECT:
            addr = data.data
            self.__connect_peer(addr)

    def __handle_recv(self) -> None:
        if len(self.conns) == 0:
            return
        r, _, _ = select.select(self.conns, [], [], 0.5)
        # print(f"clients potential receivers: {r}")
        for conn in r:
            data = conn.recv(1024).decode()

            print(f"client received {data} from {conn}")

            data = Data.model_validate_json(data)
            self.__handle_commands(conn, data)

    def __handle_send(self, data: str = "") -> None:
        if len(self.conns) == 0:
            return
        
        if data == "dc":
            addr = f"{self.external_ip}:{self.external_port}"
            data = Data(type=DataType.DISCONNECT, data=addr)
            data = data.model_dump_json()
            for conn in self.conns:
                print(f"sent {data} to {conn}")
                conn.sendall(data.encode())
            self.__disconnect()
        elif data != "":
            data = Data(type=DataType.USER_INPUT, data=data)
            data = data.model_dump_json()
            for conn in self.conns:
                print(f"sent {data} to {conn}")
                conn.sendall(data.encode())
        
        # _, w, _ = select.select([], self.conns, [], 0.1)
        # for conn in w:
        #     if data != "":
        #         conn.sendall(data.encode())

    def __handle_peers(self) -> None:
        global USER_INPUT, IS_RUNNING
        while IS_RUNNING:
            self.__handle_recv()
            if USER_INPUT is not None:
                self.__handle_send(USER_INPUT)
                USER_INPUT = None
            else:
                self.__handle_send()
            sleep(0.1)

    def __connect_peer(self, addr: str) -> None:
        ip, port = addr.split(":")
        port = int(port)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))

        self.conns.append(sock)
        self.addrs.append(addr)

    def __disconnect(self) -> None:
        global IS_RUNNING
        IS_RUNNING = False

        for conn in self.conns:
            conn.close()
        self.conns.clear()

        self.sock.close()

        
    # alternative method of connecting new peers
    # def __connect_peers(self, addrs: List[str]) -> None:
    #     for addr in addrs:
    #         ip, port = addr.split(":")
    #         port = int(port)

    #         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #         sock.connect((ip, port))

    #         self.conns.append(sock)
    #     self.addrs.extend(addrs)


    def __handle_user_input(self) -> None:
        global USER_INPUT, IS_RUNNING
        while IS_RUNNING:
            USER_INPUT = input().strip().lower()

    def connect(self, ip: str, port: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))

        self.conns.append(sock)
        self.addrs.append(f"{ip}:{port}")

        print(f"connected to {ip}:{port}")

        query = Data(
            type=DataType.GET_DATA, data=f"{self.external_ip}:{self.external_port}"
        )
        query = query.model_dump_json().encode()
        sock.send(query)
        data = sock.recv(1024).decode()

        print(f"received addrs: {data}")

        data = Data.model_validate_json(data)

        if data.type == DataType.ADDRS and len(data.data) > 0:
            new_addrs = data.data
            self.addrs.extend(new_addrs)

        threading.Thread(target=self.__handle_peers).start()
        threading.Thread(target=self.__handle_user_input).start()

        while True:
            self.sock.listen(1)
            
            try:
                conn, addr = self.sock.accept()
            except:
                break

            print(f"accepted connection from {addr[0]}:{str(addr[1])}")

            self.conns.append(conn)
            self.addrs.append(addr)


if __name__ == "__main__":
    BASE_PORT = 8765
    port = BASE_PORT + 1
    server = App("0.0.0.0", port)
    server.connect("127.0.0.1", BASE_PORT)
