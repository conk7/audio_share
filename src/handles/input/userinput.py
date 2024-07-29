from utils import DataType, Data


class UserInput:
    def handle_user_input(self) -> None:
        while True:
            self.user_input = input().strip().lower()

    def send_user_input(self, data: str) -> None:
        data = Data(type=DataType.USER_INPUT, data=data)
        data = data.model_dump_json()
        data = data.encode()

        for peer in self.peers:
            print(f"sent {data[:50]} to {peer}")
            peer.sendall(data)
