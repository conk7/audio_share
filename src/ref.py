import stun
import socket
import threading
 
source_ip = "0.0.0.0"
source_port = 8547
 
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((source_ip, source_port))
# nat_type, nat = stun.get_nat_type(sock, source_ip, source_port)
 
nat_type, nat = stun.get_nat_type(sock,
    source_ip, source_port,
    stun_host='stun.l.google.com', stun_port=19302 )
 
external_ip = nat['ExternalIP']
external_port = nat['ExternalPort']
 
print("Мой адрес: %s:%s" % (external_ip,external_port))
 
def read_chat(sock):
    while True:
       data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
       print('\r', addr,"<", data.decode())
 
reader = threading.Thread(target=read_chat,args=(sock,))
reader.start()
 
remote_ip, remote_port = input(
    "Введите `адрес:порт` другого компьютера >"
    ).split(':')
remote_port = int(remote_port)
remote = remote_ip, remote_port
 
while True:
    line = input(">")
    if line == '/exit':
        break
    sock.sendto(line.encode(), remote)